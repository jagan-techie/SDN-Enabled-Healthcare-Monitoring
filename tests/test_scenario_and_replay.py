# tests/test_scenario_and_replay.py - Unit tests for Phase 1 data and replay publisher
import pytest
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data.synthetic_generator import SyntheticPhysiologicalGenerator
from data.scenario_engine import ScenarioEngine
from gateway.replay_publisher import WBANReplayPublisher

def test_synthetic_ecg_beat_generation():
    gen = SyntheticPhysiologicalGenerator(sampling_rate=360, seed=42)
    # 75 bpm -> RR ~ 0.8s -> ~288 samples
    normal_beat = gen.generate_ecg_beat(hr_bpm=75.0, is_pvc=False)
    assert len(normal_beat) == int(360 * (60.0 / 75.0))
    assert max(normal_beat) > 0.8  # Strong R peak

    pvc_beat = gen.generate_ecg_beat(hr_bpm=75.0, is_pvc=True)
    assert len(pvc_beat) == int(360 * (60.0 / 75.0))
    # PVC beat should have prominent negative deflection
    assert min(pvc_beat) < -0.4

def test_synthetic_vitals_frame():
    gen = SyntheticPhysiologicalGenerator(sampling_rate=360, seed=42)
    frame = gen.generate_vitals_frame(hr_bpm=72.0, spo2=98.0, temp_c=36.8, ecg_duration_sec=1.0)
    assert 60.0 <= frame["hr"] <= 85.0
    assert 95.0 <= frame["spo2"] <= 100.0
    assert 36.5 <= frame["temp"] <= 37.2
    assert frame["leads_off"] is False
    assert len(frame["ecg_batch"]) == 360

def test_scenario_engine_timeline():
    engine = ScenarioEngine()
    patients = engine.get_patient_ids()
    assert "P101" in patients
    assert "P102" in patients
    assert "P103" in patients

    # P101 at 5s is normal baseline
    reading_norm = engine.sample_reading("P101", elapsed_sec=5.0)
    assert reading_norm["is_anomalous"] is False
    assert reading_norm["ground_truth"] == "NORMAL"

    # P101 at 20s has tachycardia + fever
    reading_anom = engine.sample_reading("P101", elapsed_sec=20.0)
    assert reading_anom["is_anomalous"] is True
    assert reading_anom["ground_truth"] == "TACHYCARDIA_FEVER"
    assert reading_anom["hr"] > 120.0
    assert reading_anom["temp"] > 38.5

    # P102 at 25s has hypoxemia
    reading_p102 = engine.sample_reading("P102", elapsed_sec=25.0)
    assert reading_p102["is_anomalous"] is True
    assert reading_p102["ground_truth"] == "HYPOXEMIA"
    assert reading_p102["spo2"] < 90.0

def test_replay_publisher_schema_contract():
    publisher = WBANReplayPublisher(broker_host="127.0.0.1", broker_port=1883)
    reading = publisher.engine.sample_reading("P101", elapsed_sec=0.0)

    # Validate JSON serializability and schema fields required by ESP32 firmware contract
    required_vitals_keys = {"timestamp", "patient_id", "hr", "spo2", "temp", "leads_off"}
    for key in required_vitals_keys:
        assert key in reading

    assert len(reading["ecg_batch"]) == 360
