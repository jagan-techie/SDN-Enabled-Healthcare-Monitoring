# tests/test_controller_rest.py - Unit tests for SDN controller REST WSGI API and flow persistence
import sys
import time
import threading
import requests
from pathlib import Path
from http.server import HTTPServer
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.controller_service import SDNRESTRequestHandler, ACTIVE_FLOWS
from db.session import init_db, get_db
from db.models import FlowEvent

TEST_PORT = 8089
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

@pytest.fixture(scope="module", autouse=True)
def run_test_controller():
    init_db()
    server = HTTPServer(("127.0.0.1", TEST_PORT), SDNRESTRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield
    server.shutdown()

def test_controller_status_endpoint():
    res = requests.get(f"{BASE_URL}/api/v1/priority/status")
    assert res.status_code == 200
    data = res.json()
    assert "controller" in data
    assert "connected_switches" in data
    assert "active_priority_flows" in data

def test_controller_flow_install_and_persistence():
    payload = {
        "patient_id": "P101",
        "ip_address": "10.0.0.1",
        "port": 1883,
        "queue_id": 1,
        "priority": 32768,
        "hard_timeout": 60,
        "reason": "Ventricular Arrhythmia Emergency"
    }

    res = requests.post(f"{BASE_URL}/api/v1/priority/install", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    flow = data["flow"]
    assert flow["patient_id"] == "P101"
    assert flow["queue_id"] == 1
    assert flow["setup_time_ms"] > 0.0

    # Verify flow event logged in database
    with get_db() as db:
        event = db.query(FlowEvent).filter_by(patient_id="P101").order_by(FlowEvent.id.desc()).first()
        assert event is not None
        assert event.rule_name == "PRIORITY_Q1_P101"
        assert event.queue_id == 1
        assert event.action == "INSTALL"
        assert event.flow_setup_time_ms > 0.0

def test_controller_flow_removal():
    # Remove flow
    res = requests.post(f"{BASE_URL}/api/v1/priority/remove", json={"patient_id": "P101"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"

    # Status should reflect 0 active priority flows
    res_status = requests.get(f"{BASE_URL}/api/v1/priority/status")
    status_data = res_status.json()
    assert "P101" not in status_data["active_priority_flows"]

    # Verify REMOVE action in database
    with get_db() as db:
        event = db.query(FlowEvent).filter_by(patient_id="P101", action="REMOVE").first()
        assert event is not None
        assert event.queue_id == 0
