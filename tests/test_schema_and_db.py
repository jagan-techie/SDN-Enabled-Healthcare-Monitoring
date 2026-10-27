# tests/test_schema_and_db.py - Unit tests for Phase 2 database models, WAL session, and retention
import sys
import time
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.session import init_db, get_db, SessionLocal
from db.models import Patient, VitalReading, Prediction, Alert, FlowEvent, NetworkMetric
from db.seed import seed_database
from db.retention import prune_old_records

@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    init_db()
    seed_database()

def test_patients_seeded():
    with get_db() as db:
        patients = db.query(Patient).all()
        assert len(patients) >= 3
        p101 = db.query(Patient).filter_by(patient_id="P101").first()
        assert p101 is not None
        assert p101.name == "Sarah Connor"
        assert p101.ip_address == "10.0.0.1"

def test_vitals_time_range_query():
    with get_db() as db:
        now = time.time()
        readings = (
            db.query(VitalReading)
            .filter(VitalReading.patient_id == "P101")
            .filter(VitalReading.timestamp >= now - 60)
            .order_by(VitalReading.timestamp.desc())
            .all()
        )
        assert len(readings) > 0
        for r in readings:
            assert 50.0 <= r.hr <= 150.0
            assert 80.0 <= r.spo2 <= 100.0

def test_alert_lifecycle_and_acknowledgment():
    with get_db() as db:
        test_alert = Alert(
            patient_id="P101",
            timestamp=time.time(),
            severity="CRITICAL",
            title="Severe Tachycardia Alert",
            message="Heart rate exceeded 130 bpm",
            acknowledged=False
        )
        db.add(test_alert)
        db.flush()
        alert_id = test_alert.id

    # Acknowledge alert
    with get_db() as db:
        alert = db.query(Alert).filter_by(id=alert_id).first()
        assert alert is not None
        assert alert.acknowledged is False
        alert.acknowledged = True
        alert.acknowledged_by = "Dr. House"

    # Verify update persisted
    with get_db() as db:
        alert = db.query(Alert).filter_by(id=alert_id).first()
        assert alert.acknowledged is True
        assert alert.acknowledged_by == "Dr. House"

def test_flow_event_and_network_metrics():
    with get_db() as db:
        event = FlowEvent(
            patient_id="P101",
            rule_name="PRIORITY_QUEUE_P101",
            match_ip="10.0.0.1",
            match_port=1883,
            queue_id=1,
            priority=32768,
            action="INSTALL",
            reason="Critical Arrhythmia Alert",
            flow_setup_time_ms=5.2,
            installed_at=time.time()
        )
        db.add(event)

        metric = NetworkMetric(
            timestamp=time.time(),
            source_host="sensor",
            target_host="gateway",
            latency_ms=3.8,
            throughput_mbps=9.8,
            packet_loss_pct=0.0,
            priority_on=True
        )
        db.add(metric)

    with get_db() as db:
        saved_event = db.query(FlowEvent).filter_by(rule_name="PRIORITY_QUEUE_P101").first()
        assert saved_event is not None
        assert saved_event.queue_id == 1

        saved_metric = db.query(NetworkMetric).filter_by(priority_on=True).first()
        assert saved_metric is not None
        assert saved_metric.latency_ms < 10.0

def test_retention_pruning():
    # Insert old record (timestamp = 100)
    with get_db() as db:
        old_reading = VitalReading(
            patient_id="P101",
            timestamp=100.0,
            hr=70.0,
            spo2=98.0,
            temp=36.7,
            leads_off=False
        )
        db.add(old_reading)

    # Prune records older than 1 hour
    prune_old_records(retention_seconds=3600)

    # Verify old record pruned while fresh records remain
    with get_db() as db:
        pruned = db.query(VitalReading).filter_by(timestamp=100.0).first()
        assert pruned is None
        recent = db.query(VitalReading).filter(VitalReading.timestamp > time.time() - 3600).all()
        assert len(recent) > 0
