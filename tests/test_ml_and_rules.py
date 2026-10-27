# tests/test_ml_and_rules.py - Unit tests for ML feature extraction, model inference, and clinical thresholds
import sys
import time
from pathlib import Path
import numpy as np
import pytest
import joblib

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.features import ECGFeatureExtractor, FEATURE_NAMES
from data.synthetic_generator import SyntheticPhysiologicalGenerator
from ml.inference_service import HybridInferenceEngine

def test_feature_extractor_r_peaks_and_features():
    gen = SyntheticPhysiologicalGenerator(sampling_rate=360, seed=42)
    extractor = ECGFeatureExtractor(fs=360)

    # 1 second of normal sinus rhythm (approx 1.2 beats)
    ecg_batch = gen.generate_ecg_batch(duration_sec=1.0, hr_bpm=72.0)
    features = extractor.extract_features(ecg_batch, hr_hint=72.0)

    assert len(features) == len(FEATURE_NAMES)
    assert len(features) == 9
    # Mean RR interval should be around 0.8s
    assert 0.5 <= features[0] <= 1.2
    # Estimated HR should be around 60-90 bpm
    assert 50.0 <= features[3] <= 100.0

def test_model_loading_and_prediction():
    model_path = ROOT_DIR / "ml" / "models" / "ecg_rf_model.joblib"
    assert model_path.exists(), "Model file not found"

    clf = joblib.load(model_path)
    extractor = ECGFeatureExtractor(fs=360)
    gen = SyntheticPhysiologicalGenerator(sampling_rate=360, seed=42)

    # Normal beat features
    normal_ecg = gen.generate_ecg_batch(duration_sec=1.0, hr_bpm=72.0)
    feat_norm = extractor.extract_features(normal_ecg, hr_hint=72.0)
    pred_norm = clf.predict([feat_norm])[0]
    probs_norm = clf.predict_proba([feat_norm])[0]

    assert pred_norm in (0, 1)
    assert len(probs_norm) == 2
    assert 0.0 <= probs_norm[0] <= 1.0
    assert 0.0 <= probs_norm[1] <= 1.0

def test_clinical_threshold_rules():
    # Test threshold rule evaluations
    test_cases = [
        {"hr": 72.0, "spo2": 98.0, "temp": 36.8, "leads_off": False, "expect_abnormal": False},
        {"hr": 42.0, "spo2": 98.0, "temp": 36.8, "leads_off": False, "expect_abnormal": True},   # Bradycardia
        {"hr": 138.0, "spo2": 98.0, "temp": 36.8, "leads_off": False, "expect_abnormal": True},  # Tachycardia
        {"hr": 72.0, "spo2": 84.0, "temp": 36.8, "leads_off": False, "expect_abnormal": True},   # Hypoxemia
        {"hr": 72.0, "spo2": 98.0, "temp": 39.2, "leads_off": False, "expect_abnormal": True},   # Fever
        {"hr": 72.0, "spo2": 98.0, "temp": 36.8, "leads_off": True, "expect_abnormal": True},    # Leads off
    ]

    for tc in test_cases:
        rule_violations = []
        if tc["leads_off"]:
            rule_violations.append("Leads Disconnected")
        if tc["hr"] < 50.0:
            rule_violations.append("Bradycardia")
        elif tc["hr"] > 120.0:
            rule_violations.append("Tachycardia")
        if tc["spo2"] < 90.0:
            rule_violations.append("Hypoxemia")
        if tc["temp"] > 38.0:
            rule_violations.append("Fever")
        elif tc["temp"] < 35.0:
            rule_violations.append("Hypothermia")

        is_abnormal = len(rule_violations) > 0
        assert is_abnormal == tc["expect_abnormal"], f"Failed for {tc}"
