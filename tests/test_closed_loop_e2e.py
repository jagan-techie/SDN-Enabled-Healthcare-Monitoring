# tests/test_closed_loop_e2e.py - End-to-end integration test verifying complete closed-loop workflow
import sys
import time
import json
import threading
from pathlib import Path
from http.server import HTTPServer
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.session import init_db, get_db
from db.models import Patient, Alert, FlowEvent, Prediction
from scripts.controller_service import SDNRESTRequestHandler, ACTIVE_FLOWS
from ml.inference_service import HybridInferenceEngine
from data.synthetic_generator import SyntheticPhysiologicalGenerator
from dashboard.app import app

TEST_RYU_PORT = 8099

@pytest.fixture(scope="module", autouse=True)
def setup_environment():
    init_db()
    with get_db() as db:
        if not db.query(Patient).filter_by(patient_id="P101").first():
            db.add(Patient(
                patient_id="P101",
                name="Sarah Connor",
                age=42,
                gender="F",
                room="Ward-302",
                ip_address="10.0.0.1",
                mac_address="00:00:00:00:00:01",
                status="NORMAL"
            ))

    # Start mock SDN controller server
    server = HTTPServer(("127.0.0.1", TEST_RYU_PORT), SDNRESTRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    yield
    server.shutdown()

def test_closed_loop_alert_and_priority_flow():
    """Validates the complete closed loop:

    Telemetry -> ML Hybrid Inference -> Debounce -> Abnormal Alert -> Ryu Priority Flow Install -> Dashboard API verified
    -> Recovery -> Flow Removal
    """
    engine = HybridInferenceEngine(
        ryu_rest_url=f"http://127.0.0.1:{TEST_RYU_PORT}",
        debounce_windows=2,
        hard_timeout=60
    )
    gen = SyntheticPhysiologicalGenerator(sampling_rate=360, seed=42)

    # 1. Feed baseline normal frame (Window 1)
    norm_frame = gen.generate_vitals_frame(hr_bpm=72.0, spo2=98.0, temp_c=36.8)
    engine._get_patient_state("P101")["ecg_buffer"] = norm_frame["ecg_batch"]
    engine.process_inference_cycle("P101", {
        "timestamp": time.time(),
        "patient_id": "P101",
        "hr": norm_frame["hr"],
        "spo2": norm_frame["spo2"],
        "temp": norm_frame["temp"],
        "leads_off": False
    })
    assert engine.patient_state["P101"]["priority_active"] is False
    assert engine.patient_state["P101"]["abnormal_streak"] == 0

    # 2. Inject Abnormal Anomaly (Window 1 of anomaly: Tachycardia + Fever)
    anom_frame_1 = gen.generate_vitals_frame(hr_bpm=135.0, spo2=94.0, temp_c=39.2)
    engine.process_inference_cycle("P101", {
        "timestamp": time.time(),
        "patient_id": "P101",
        "hr": 135.0,
        "spo2": 94.0,
        "temp": 39.2,
        "leads_off": False
    })
    # Due to debouncer (N=2), streak is 1, alert not fired yet
    assert engine.patient_state["P101"]["abnormal_streak"] == 1
    assert engine.patient_state["P101"]["priority_active"] is False

    # 3. Inject Abnormal Anomaly (Window 2 of anomaly: Debounce threshold satisfied!)
    anom_frame_2 = gen.generate_vitals_frame(hr_bpm=138.0, spo2=93.0, temp_c=39.4)
    engine.process_inference_cycle("P101", {
        "timestamp": time.time() + 1,
        "patient_id": "P101",
        "hr": 138.0,
        "spo2": 93.0,
        "temp": 39.4,
        "leads_off": False
    })

    # Assert priority flow became active
    assert engine.patient_state["P101"]["abnormal_streak"] >= 2
    assert engine.patient_state["P101"]["priority_active"] is True

    # Assert flow registered in active flows
    assert "P101" in ACTIVE_FLOWS
    assert ACTIVE_FLOWS["P101"]["queue_id"] == 1
    assert ACTIVE_FLOWS["P101"]["priority"] == 32768

    # Assert Alert record saved to Database
    with get_db() as db:
        alert = db.query(Alert).filter_by(patient_id="P101").order_by(Alert.id.desc()).first()
        assert alert is not None
        assert alert.severity == "CRITICAL"
        assert "Tachycardia" in alert.message or "Fever" in alert.message

        flow_ev = db.query(FlowEvent).filter_by(patient_id="P101", action="INSTALL").order_by(FlowEvent.id.desc()).first()
        assert flow_ev is not None
        assert flow_ev.queue_id == 1
        assert flow_ev.flow_setup_time_ms > 0.0

    # 4. Verify Dashboard REST API reflects Priority Active state
    app.config["TESTING"] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user"] = "admin"

        res = client.get("/api/patients/P101/live")
        assert res.status_code == 200
        live_data = res.json
        assert live_data["priority_active"] is True
        assert live_data["overall_status"] == "CRITICAL"

    # 5. Normalization Recovery: Patient vitals recover to normal
    recov_frame = gen.generate_vitals_frame(hr_bpm=72.0, spo2=98.0, temp_c=36.8)
    engine.process_inference_cycle("P101", {
        "timestamp": time.time() + 2,
        "patient_id": "P101",
        "hr": 72.0,
        "spo2": 98.0,
        "temp": 36.8,
        "leads_off": False
    })

    # Assert SDN Priority flow reverted
    assert engine.patient_state["P101"]["priority_active"] is False
    assert "P101" not in ACTIVE_FLOWS

    # Verify Dashboard API reflects Normalization
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user"] = "admin"
        res_after = client.get("/api/patients/P101/live")
        assert res_after.json["priority_active"] is False
