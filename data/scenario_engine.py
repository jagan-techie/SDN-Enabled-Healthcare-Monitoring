import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data.synthetic_generator import SyntheticPhysiologicalGenerator

logger = logging.getLogger("ScenarioEngine")

class ScenarioEngine:
    """Manages multi-patient physiological timelines with injected anomalies and ground-truth labels."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = str(Path(__file__).resolve().parent / "scenarios.json")
        self.config_path = config_path
        self.generator = SyntheticPhysiologicalGenerator(sampling_rate=360)
        self.scenarios = self._load_config()
        self.patients = {p["patient_id"]: p for p in self.scenarios.get("patients", [])}

    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r") as f:
            return json.load(f)

    def get_patient_ids(self) -> List[str]:
        return list(self.patients.keys())

    def get_patient_info(self, patient_id: str) -> Optional[Dict[str, Any]]:
        return self.patients.get(patient_id)

    def get_timeline_slice(self, patient_id: str, elapsed_sec: float) -> Dict[str, Any]:
        """Finds the active timeline segment for the given elapsed time."""
        patient = self.patients.get(patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not defined in scenarios.json")

        timeline = patient["timeline"]
        max_duration = timeline[-1]["end_sec"] if timeline else 60.0
        # Loop timeline if elapsed_sec exceeds defined duration
        effective_sec = elapsed_sec % max_duration

        for segment in timeline:
            if segment["start_sec"] <= effective_sec < segment["end_sec"]:
                return segment

        return timeline[-1]

    def sample_reading(self, patient_id: str, elapsed_sec: float, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Samples a standardized WBAN sensor telemetry reading for the patient."""
        seg = self.get_timeline_slice(patient_id, elapsed_sec)
        ts = timestamp if timestamp is not None else time.time()

        frame = self.generator.generate_vitals_frame(
            hr_bpm=seg["hr"],
            spo2=seg["spo2"],
            temp_c=seg["temp"],
            leads_off=seg.get("leads_off", False),
            ecg_duration_sec=1.0,
            inject_pvc=seg.get("pvc", False)
        )

        return {
            "timestamp": round(ts, 3),
            "patient_id": patient_id,
            "hr": frame["hr"],
            "spo2": frame["spo2"],
            "temp": frame["temp"],
            "leads_off": frame["leads_off"],
            "ecg_batch": frame["ecg_batch"],
            "ground_truth": seg.get("ground_truth", "NORMAL"),
            "is_anomalous": seg.get("is_anomalous", False)
        }

if __name__ == "__main__":
    engine = ScenarioEngine()
    reading = engine.sample_reading("P101", elapsed_sec=20.0)
    print(f"Sample at 20s for P101: GT={reading['ground_truth']}, Anomalous={reading['is_anomalous']}, HR={reading['hr']}, Temp={reading['temp']}")
