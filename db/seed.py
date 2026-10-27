# db/seed.py - Seed script for virtual patients, baseline telemetry, and network metrics
import sys
import time
import json
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.session import init_db, get_db
from db.models import Patient, VitalReading, Prediction, Alert, NetworkMetric

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [DBSeed] %(message)s")
logger = logging.getLogger("DBSeed")

def seed_database():
    init_db()
    scenarios_file = ROOT_DIR / "data" / "scenarios.json"
    if not scenarios_file.exists():
        logger.error(f"Scenarios file not found at {scenarios_file}")
        return

    with open(scenarios_file, "r") as f:
        scenario_data = json.load(f)

    with get_db() as db:
        now = time.time()
        # 1. Seed Patients
        for p in scenario_data.get("patients", []):
            existing = db.query(Patient).filter_by(patient_id=p["patient_id"]).first()
            if not existing:
                patient = Patient(
                    patient_id=p["patient_id"],
                    name=p["name"],
                    age=p["age"],
                    gender=p["gender"],
                    room=p["room"],
                    ip_address=p.get("ip_address", "10.0.0.1"),
                    mac_address=f"00:00:00:00:00:0{p['patient_id'][-1]}",
                    status="NORMAL"
                )
                db.add(patient)
                logger.info(f"Seeded patient: {patient.name} ({patient.patient_id})")

                # 2. Seed 30 seconds of historical normal baseline vitals
                for i in range(30, 0, -1):
                    t = now - i
                    v = VitalReading(
                        patient_id=patient.patient_id,
                        timestamp=round(t, 2),
                        hr=72.0 + (i % 3) * 0.5,
                        spo2=98.0 - (i % 2) * 0.3,
                        temp=36.8 + (i % 4) * 0.02,
                        leads_off=False
                    )
                    db.add(v)

                    pred = Prediction(
                        patient_id=patient.patient_id,
                        timestamp=round(t, 2),
                        ecg_classification="NORMAL",
                        ecg_confidence=0.98,
                        vitals_status="NORMAL",
                        overall_status="NORMAL",
                        reason="Normal sinus rhythm and vital parameters within safe clinical thresholds",
                        inference_latency_ms=12.4 + (i % 5) * 0.8
                    )
                    db.add(pred)

        # 3. Seed baseline network metrics (Priority OFF vs Priority ON)
        for i in range(10, 0, -1):
            t = now - (i * 5)
            # Normal best-effort with cross-traffic congestion (Priority OFF)
            db.add(NetworkMetric(
                timestamp=round(t, 2),
                source_host="sensor",
                target_host="gateway",
                latency_ms=48.2 + (i % 4) * 3.5,
                throughput_mbps=3.8 + (i % 3) * 0.4,
                packet_loss_pct=4.2 + (i % 2) * 1.5,
                priority_on=False
            ))
            # SDN High-Priority Queue 1 active (Priority ON)
            db.add(NetworkMetric(
                timestamp=round(t + 2, 2),
                source_host="sensor",
                target_host="gateway",
                latency_ms=4.1 + (i % 3) * 0.6,
                throughput_mbps=9.4 + (i % 2) * 0.3,
                packet_loss_pct=0.0,
                priority_on=True
            ))

        logger.info("Database seeding completed successfully.")

if __name__ == "__main__":
    seed_database()
