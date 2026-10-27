# ml/features.py - Feature extraction and live Pan-Tompkins R-peak detector for 360Hz ECG
import numpy as np
from typing import List, Tuple, Dict, Any, Optional

class ECGFeatureExtractor:
    """Extracts clinically grounded morphological and HRV features from 360Hz ECG signals."""

    def __init__(self, fs: int = 360):
        self.fs = fs
        self.min_rr_samples = int(0.25 * fs)  # 250 ms refractory period (~240 bpm max)

    def detect_r_peaks(self, signal: np.ndarray) -> np.ndarray:
        """Lightweight real-time Pan-Tompkins style R-peak detector.

        Applies derivative filter, squaring, moving window integration, and dynamic peak thresholding.
        """
        if len(signal) < self.fs:
            return np.array([], dtype=int)

        sig = np.asarray(signal, dtype=float)
        # 1. Bandpass / Baseline removal (first difference)
        diff = np.diff(sig)

        # 2. Squaring to amplify high-frequency QRS energy
        squared = diff ** 2

        # 3. Moving window integrator (approx 100 ms window = 36 samples)
        window_size = int(0.10 * self.fs)
        kernel = np.ones(window_size) / window_size
        integrated = np.convolve(squared, kernel, mode="same")

        # 4. Adaptive thresholding
        threshold = 0.35 * np.max(integrated) if np.max(integrated) > 0 else 0.05
        peaks = []
        last_peak = -self.min_rr_samples

        for i in range(1, len(integrated) - 1):
            if integrated[i] > threshold and integrated[i] > integrated[i - 1] and integrated[i] > integrated[i + 1]:
                if (i - last_peak) >= self.min_rr_samples:
                    # Refine peak to actual maximum in original ECG signal within +/- 30ms window
                    search_start = max(0, i - int(0.03 * self.fs))
                    search_end = min(len(sig), i + int(0.03 * self.fs))
                    refined_idx = search_start + np.argmax(sig[search_start:search_end])
                    peaks.append(refined_idx)
                    last_peak = refined_idx

        return np.array(peaks, dtype=int)

    def extract_features(self, ecg_batch: List[float], hr_hint: Optional[float] = None) -> np.ndarray:
        """Extracts 9-dimensional feature vector:

        [mean_rr, std_rr, rmssd, estimated_hr, pnn50, qrs_amplitude, qrs_energy, skewness, kurtosis]
        """
        sig = np.asarray(ecg_batch, dtype=float)
        r_peaks = self.detect_r_peaks(sig)

        if len(r_peaks) >= 2:
            rr_intervals_sec = np.diff(r_peaks) / float(self.fs)
            mean_rr = float(np.mean(rr_intervals_sec))
            std_rr = float(np.std(rr_intervals_sec)) if len(rr_intervals_sec) > 1 else 0.0
            diff_rr = np.diff(rr_intervals_sec)
            rmssd = float(np.sqrt(np.mean(diff_rr ** 2))) if len(diff_rr) > 0 else 0.0
            estimated_hr = float(60.0 / mean_rr) if mean_rr > 0 else 75.0
            pnn50 = float(np.sum(np.abs(diff_rr) > 0.05) / len(diff_rr)) if len(diff_rr) > 0 else 0.0
            qrs_amplitude = float(np.mean(sig[r_peaks]))
        else:
            # Fallback when isolated single beat is present in short 1s window
            mean_rr = (60.0 / hr_hint) if (hr_hint and hr_hint > 0) else 0.8
            std_rr = 0.04
            rmssd = 0.03
            estimated_hr = hr_hint if (hr_hint and hr_hint > 0) else 75.0
            pnn50 = 0.0
            qrs_amplitude = float(np.max(sig) - np.min(sig)) if len(sig) > 0 else 1.0

        # Morphology energy & distribution
        qrs_energy = float(np.mean(sig ** 2)) if len(sig) > 0 else 0.0
        # Skewness & Kurtosis
        centered = sig - np.mean(sig) if len(sig) > 0 else np.zeros(1)
        var = np.var(sig)
        std = np.sqrt(var) if var > 1e-8 else 1.0
        skewness = float(np.mean((centered / std) ** 3))
        kurtosis = float(np.mean((centered / std) ** 4) - 3.0)

        return np.array([
            round(mean_rr, 4),
            round(std_rr, 4),
            round(rmssd, 4),
            round(estimated_hr, 1),
            round(pnn50, 4),
            round(qrs_amplitude, 4),
            round(qrs_energy, 4),
            round(skewness, 4),
            round(kurtosis, 4)
        ], dtype=float)

FEATURE_NAMES = [
    "mean_rr",
    "std_rr",
    "rmssd",
    "estimated_hr",
    "pnn50",
    "qrs_amplitude",
    "qrs_energy",
    "signal_skewness",
    "signal_kurtosis"
]
