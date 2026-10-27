# ml/evaluate.py - Honest model evaluation with precision, recall, F1, confusion matrix, and ROC curve
import os
import sys
import json
import logging
from pathlib import Path
import numpy as np
import joblib
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_curve, auc
)

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.features import ECGFeatureExtractor
from ml.train import load_split_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [MLEval] %(message)s")
logger = logging.getLogger("MLEval")

RESULTS_DIR = ROOT_DIR / "eval" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def evaluate():
    model_path = BASE_DIR / "models" / "ecg_rf_model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Model file {model_path} not found. Run ml/train.py first.")

    clf = joblib.load(model_path)
    extractor = ECGFeatureExtractor(fs=360)

    logger.info("Loading held-out DS2 test dataset...")
    X_test, y_test, test_patients = load_split_data("test", extractor)
    logger.info(f"Loaded {len(X_test)} test instances across test patients: {sorted(list(test_patients))}")

    # Predictions
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]

    # Metrics
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    fpr, tpr, thresholds = roc_curve(y_test, y_prob)
    roc_auc = auc(fpr, tpr)

    logger.info("=" * 60)
    logger.info("EVALUATION RESULTS ON INDEPENDENT TEST PATIENTS (DS2)")
    logger.info("=" * 60)
    logger.info(f"Accuracy:    {acc * 100:.2f}%")
    logger.info(f"Precision:   {prec * 100:.2f}%")
    logger.info(f"Recall:      {rec * 100:.2f}%")
    logger.info(f"Specificity: {spec * 100:.2f}%")
    logger.info(f"F1-Score:    {f1 * 100:.2f}%")
    logger.info(f"ROC-AUC:     {roc_auc:.4f}")
    logger.info(f"Confusion Matrix: TN={tn}, FP={fp}, FN={fn}, TP={tp}")
    logger.info("=" * 60)

    # 1. Plot Confusion Matrix
    plt.figure(figsize=(6, 5))
    plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title("Confusion Matrix - Arrhythmia Detection (DS2 Test Set)")
    plt.colorbar()
    tick_marks = np.arange(2)
    plt.xticks(tick_marks, ["Normal", "Arrhythmia"])
    plt.yticks(tick_marks, ["Normal", "Arrhythmia"])

    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(j, i, format(cm[i, j], "d"),
                     horizontalalignment="center",
                     color="white" if cm[i, j] > thresh else "black")

    plt.ylabel("True Class")
    plt.xlabel("Predicted Class")
    plt.tight_layout()
    cm_path = RESULTS_DIR / "confusion_matrix.png"
    plt.savefig(cm_path, dpi=200)
    plt.close()
    logger.info(f"Saved confusion matrix plot to {cm_path}")

    # 2. Plot ROC Curve
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, color="#2563eb", lw=2, label=f"ROC curve (AUC = {roc_auc:.3f})")
    plt.plot([0, 1], [0, 1], color="#9ca3af", lw=1.5, linestyle="--")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate (1 - Specificity)")
    plt.ylabel("True Positive Rate (Sensitivity / Recall)")
    plt.title("Receiver Operating Characteristic (ROC)")
    plt.legend(loc="lower right")
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    roc_path = RESULTS_DIR / "roc_curve.png"
    plt.savefig(roc_path, dpi=200)
    plt.close()
    logger.info(f"Saved ROC plot to {roc_path}")

    # Save metrics JSON
    metrics_summary = {
        "test_patients": sorted(list(test_patients)),
        "num_test_samples": int(len(X_test)),
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "specificity": round(float(spec), 4),
        "f1_score": round(float(f1), 4),
        "roc_auc": round(float(roc_auc), 4),
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp)
        }
    }

    metrics_path = RESULTS_DIR / "ml_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_summary, f, indent=2)
    logger.info(f"Saved numerical metrics export to {metrics_path}")

if __name__ == "__main__":
    evaluate()
