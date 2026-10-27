# ml/train.py - Random Forest model training with inter-patient split and explicit leakage check
import os
import sys
import json
import time
import logging
from pathlib import Path
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.features import ECGFeatureExtractor, FEATURE_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [MLTrain] %(message)s")
logger = logging.getLogger("MLTrain")

MODELS_DIR = BASE_DIR / "models"
PROCESSED_DATA_DIR = ROOT_DIR / "data" / "processed"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

def load_split_data(split_name: str, extractor: ECGFeatureExtractor):
    split_dir = PROCESSED_DATA_DIR / split_name
    if not split_dir.exists():
        raise FileNotFoundError(f"Processed dataset directory {split_dir} does not exist. Run data/download_datasets.py first.")

    X_list = []
    y_list = []
    patient_ids = set()

    for file_path in split_dir.glob("*.json"):
        with open(file_path, "r") as f:
            data = json.load(f)

        pid = data["record_id"]
        patient_ids.add(pid)
        signal = data["signal"]
        labels = data["labels"]
        fs = data.get("fs", 360)
        has_arrhythmia = data.get("has_arrhythmia", False)

        # Slice 60s signal into 1-second non-overlapping windows (360 samples each)
        window_size = fs
        num_windows = len(signal) // window_size
        r_peaks = np.array(data.get("r_peaks", []))
        beat_labels = np.array(data.get("labels", []))
        # Find exact sample locations of ectopic ventricular beats (label == 1)
        pvc_peaks = r_peaks[beat_labels == 1] if len(beat_labels) == len(r_peaks) and len(r_peaks) > 0 else []
        beat_margin = 90  # ~250ms ectopic ventricular beat morphology span

        for w_idx in range(num_windows):
            chunk = signal[w_idx * window_size : (w_idx + 1) * window_size]
            features = extractor.extract_features(chunk)
            X_list.append(features)

            w_start = w_idx * window_size
            w_end = (w_idx + 1) * window_size
            if len(pvc_peaks) > 0:
                in_window = np.any((pvc_peaks + beat_margin >= w_start) & (pvc_peaks - beat_margin < w_end))
                window_label = 1 if in_window else 0
            else:
                window_label = 0
            y_list.append(window_label)

    return np.array(X_list), np.array(y_list), patient_ids

def train():
    logger.info("Initializing ECG feature extractor and loading dataset...")
    extractor = ECGFeatureExtractor(fs=360)

    X_train, y_train, train_patients = load_split_data("train", extractor)
    X_test, y_test, test_patients = load_split_data("test", extractor)

    # MANDATORY Inter-Patient Leakage Check
    overlap = train_patients.intersection(test_patients)
    assert len(overlap) == 0, f"FATAL DATA LEAKAGE: Patient IDs appear in both train and test sets: {overlap}"
    logger.info(f"Inter-patient split verified: Train patients={sorted(list(train_patients))}, Test patients={sorted(list(test_patients))}. Overlap={len(overlap)} (Zero Leakage)")

    logger.info(f"Dataset summary: Train samples={len(X_train)} (Positive={np.sum(y_train)}), Test samples={len(X_test)} (Positive={np.sum(y_test)})")

    # Handle class imbalance via class_weight='balanced'
    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=4,
        class_weight="balanced",
        random_state=42,
        n_jobs=1
    )

    start_train = time.time()
    clf.fit(X_train, y_train)
    train_duration_sec = time.time() - start_train
    logger.info(f"Random Forest model trained in {train_duration_sec:.2f} seconds.")

    # Save model and artifacts
    model_path = MODELS_DIR / "ecg_rf_model.joblib"
    joblib.dump(clf, model_path)
    logger.info(f"Model serialized to {model_path}")

    metadata = {
        "model_type": "RandomForestClassifier",
        "n_estimators": 100,
        "max_depth": 10,
        "class_weight": "balanced",
        "feature_names": FEATURE_NAMES,
        "num_features": len(FEATURE_NAMES),
        "train_patients": sorted(list(train_patients)),
        "test_patients": sorted(list(test_patients)),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "training_time_sec": round(train_duration_sec, 3),
        "classes": ["NORMAL", "ARRHYTHMIA"]
    }

    meta_path = MODELS_DIR / "model_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Model metadata saved to {meta_path}")

if __name__ == "__main__":
    train()
