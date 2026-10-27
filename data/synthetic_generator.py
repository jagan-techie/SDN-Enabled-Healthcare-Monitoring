# data/synthetic_generator.py - Physiological signal generator for 360Hz ECG and multi-parameter vitals
import math
import numpy as np
from typing import Dict, List, Any, Optional

class SyntheticPhysiologicalGenerator:
    """Generates realistic synthetic 360Hz ECG waveforms and multi-parameter vital signs.

    Follows the McSharry synthetic ECG morphology and clinical vital ranges.
    Includes controlled anomaly injections for ground-truth benchmark scoring.
    """

    def __init__(self, sampling_rate: int = 360, seed: Optional[int] = 42):
        self.fs = sampling_rate
        self.rng = np.random.default_rng(seed)
        self.phase = 0.0

    def generate_ecg_beat(self, hr_bpm: float, is_pvc: bool = False) -> np.ndarray:
        """Synthesizes a single ECG heartbeat using Gaussian approximations for P, Q, R, S, T waves.

        If is_pvc is True, models a premature ventricular contraction: wide inverted QRS, no P wave.
        """
        rr_sec = 60.0 / max(30.0, hr_bpm)
        num_samples = int(self.fs * rr_sec)
        t = np.linspace(0, rr_sec, num_samples, endpoint=False)

        # Baseline noise and 0.2Hz baseline wander
        ecg = 0.05 * np.sin(2 * np.pi * 0.2 * t) + self.rng.normal(0, 0.015, num_samples)

        if not is_pvc:
            # Normal Sinus Rhythm: P, Q, R, S, T parameters: (amplitude, width_sec, center_ratio)
            waves = [
                (0.15, 0.06, 0.18),    # P wave
                (-0.15, 0.025, 0.35),  # Q wave
                (1.20, 0.040, 0.40),   # R wave (sharp peak)
                (-0.25, 0.030, 0.45),  # S wave
                (0.30, 0.120, 0.68),   # T wave
            ]
            for amp, width, pos in waves:
                c = pos * rr_sec
                ecg += amp * np.exp(-((t - c) ** 2) / (2 * (width ** 2)))
        else:
            # Premature Ventricular Contraction (PVC): wide, bizarre, inverted QRS, compensatory pause
            pvc_waves = [
                (0.0, 0.01, 0.1),       # Absent P wave
                (-0.90, 0.09, 0.35),   # Wide negative QRS
                (0.40, 0.14, 0.60),    # Discordant prolonged T wave
            ]
            for amp, width, pos in pvc_waves:
                c = pos * rr_sec
                ecg += amp * np.exp(-((t - c) ** 2) / (2 * (width ** 2)))

        return ecg

    def generate_ecg_batch(self, duration_sec: float, hr_bpm: float, pvc_indices: Optional[List[int]] = None) -> List[float]:
        """Generates continuous ECG signal for the given duration in seconds at 360 Hz."""
        pvc_indices = pvc_indices or []
        samples_needed = int(self.fs * duration_sec)
        full_signal = []
        beat_idx = 0

        while len(full_signal) < samples_needed:
            is_pvc = beat_idx in pvc_indices
            effective_hr = hr_bpm * (1.35 if is_pvc else 1.0)
            beat = self.generate_ecg_beat(effective_hr, is_pvc=is_pvc)
            full_signal.extend(beat.tolist())
            beat_idx += 1

        return [round(float(v), 4) for v in full_signal[:samples_needed]]

    def generate_vitals_frame(
        self,
        hr_bpm: float = 75.0,
        spo2: float = 98.0,
        temp_c: float = 36.8,
        leads_off: bool = False,
        ecg_duration_sec: float = 1.0,
        inject_pvc: bool = False
    ) -> Dict[str, Any]:
        """Creates a single standardized WBAN sensor telemetry frame."""
        # Add slight natural biological jitter
        jittered_hr = max(30.0, float(hr_bpm + self.rng.normal(0, 0.8)))
        jittered_spo2 = min(100.0, max(60.0, float(spo2 + self.rng.normal(0, 0.2))))
        jittered_temp = float(temp_c + self.rng.normal(0, 0.03))

        ecg_batch = self.generate_ecg_batch(
            duration_sec=ecg_duration_sec,
            hr_bpm=jittered_hr,
            pvc_indices=[0] if inject_pvc else []
        )

        if leads_off:
            # When leads are detached, ECG is flatline with slight thermal noise
            ecg_batch = [round(float(v), 4) for v in self.rng.normal(0, 0.005, len(ecg_batch))]
            jittered_hr = 0.0

        return {
            "hr": round(jittered_hr, 1),
            "spo2": round(jittered_spo2, 1),
            "temp": round(jittered_temp, 2),
            "leads_off": leads_off,
            "ecg_batch": ecg_batch
        }

if __name__ == "__main__":
    gen = SyntheticPhysiologicalGenerator()
    frame = gen.generate_vitals_frame(hr_bpm=72, spo2=98.5, temp_c=36.7)
    print(f"Generated 1s frame: HR={frame['hr']}, SpO2={frame['spo2']}%, Temp={frame['temp']}C, ECG samples={len(frame['ecg_batch'])}")
