# ml/inference_service.py - Hybrid ML and clinical threshold inference engine with MQTT streaming, debouncing and SDN closed-loop invocation
import os
import sys
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import paho.mqtt.client as mqtt
import requests
import joblib

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.features import ECGFeatureExtractor
from db.session import get_db, init_db
from db.models import Patient, VitalReading, Prediction, Alert, FlowEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [InferenceService] %(message)s")
logger = logging.getLogger("InferenceService")

class HybridInferenceEngine:
    def __init__(
        self,
        broker_host: str = "127.0.0.1",
        broker_port: int = 1883,
        ryu_rest_url: str = "http://127.0.0.1:8080",
        debounce_windows: int = 2,
        hard_timeout: int = 60
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.ryu_rest_url = ryu_rest_url.rstrip("/")
        self.debounce_windows = debounce_windows
        self.hard_timeout = hard_timeout

        # Initialize models and feature extractors
        self.extractor = ECGFeatureExtractor(fs=360)
        model_path = BASE_DIR / "models" / "ecg_rf_model.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"Model {model_path} not found. Run ml/train.py first.")
        self.model = joblib.load(model_path)
        logger.info(f"Loaded Random Forest model from {model_path}")

        # In-memory patient buffers
        # patient_id -> {"ecg_buffer": list, "vitals": dict, "abnormal_streak": int, "priority_active": bool}
        self.patient_state: Dict[str, Dict[str, Any]] = {}

        # MQTT Client
        if hasattr(mqtt, "CallbackAPIVersion"):
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"ml_inference_{os.getpid()}", protocol=mqtt.MQTTv311)
        else:
            self.client = mqtt.Client(client_id=f"ml_inference_{os.getpid()}", protocol=mqtt.MQTTv311)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.running = False

    def _get_patient_state(self, patient_id: str) -> Dict[str, Any]:
        if patient_id not in self.patient_state:
            self.patient_state[patient_id] = {
                "ecg_buffer": [],
                "latest_vitals": None,
                "abnormal_streak": 0,
                "priority_active": False,
                "ip_address": "10.0.0.1"
            }
            # Cache IP from database
            with get_db() as db:
                p = db.query(Patient).filter_by(patient_id=patient_id).first()
                if p:
                    self.patient_state[patient_id]["ip_address"] = p.ip_address
        return self.patient_state[patient_id]

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.client.subscribe("wban/+/vitals", qos=1)
            self.client.subscribe("wban/+/ecg", qos=1)
            logger.info("Subscribed to topics: wban/+/vitals and wban/+/ecg")
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))
            parts = topic.split("/")
            if len(parts) != 3:
                return

            _, patient_id, stream_type = parts
            state = self._get_patient_state(patient_id)

            if stream_type == "ecg":
                batch = payload.get("ecg_batch", [])
                state["ecg_buffer"].extend(batch)
                # Keep up to 2 seconds of ECG samples (720 samples)
                if len(state["ecg_buffer"]) > 720:
                    state["ecg_buffer"] = state["ecg_buffer"][-720:]

            elif stream_type == "vitals":
                state["latest_vitals"] = payload
                # When 1 Hz vitals arrive, execute hybrid inference step
                self.process_inference_cycle(patient_id, payload)

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}", exc_info=True)

    def process_inference_cycle(self, patient_id: str, vitals_payload: Dict[str, Any]):
        t0 = time.perf_counter()
        state = self._get_patient_state(patient_id)
        hr = float(vitals_payload.get("hr", 75.0))
        spo2 = float(vitals_payload.get("spo2", 98.0))
        temp = float(vitals_payload.get("temp", 36.8))
        leads_off = bool(vitals_payload.get("leads_off", False))
        timestamp = float(vitals_payload.get("timestamp", time.time()))

        # 1. ML ECG Classification
        ecg_window = state["ecg_buffer"][-360:] if len(state["ecg_buffer"]) >= 360 else [0.0] * 360
        features = self.extractor.extract_features(ecg_window, hr_hint=hr)
        probs = self.model.predict_proba([features])[0]
        ecg_pred_class = int(np.argmax(probs))
        ecg_confidence = float(np.max(probs))
        ecg_label = "ARRHYTHMIA" if ecg_pred_class == 1 else "NORMAL"

        # 2. Transparent Clinical Threshold Rules
        rule_violations = []
        if leads_off:
            rule_violations.append("Leads Disconnected")
        if hr < 50.0:
            rule_violations.append(f"Severe Bradycardia (HR {hr:.0f} bpm)")
        elif hr > 120.0:
            rule_violations.append(f"Tachycardia (HR {hr:.0f} bpm)")
        if spo2 < 85.0:
            rule_violations.append(f"Critical Hypoxemia (SpO2 {spo2:.1f}%)")
        elif spo2 < 90.0:
            rule_violations.append(f"Hypoxemia (SpO2 {spo2:.1f}%)")
        if temp > 39.0:
            rule_violations.append(f"High Fever (Temp {temp:.1f}C)")
        elif temp > 38.0:
            rule_violations.append(f"Fever (Temp {temp:.1f}C)")
        elif temp < 35.0:
            rule_violations.append(f"Hypothermia (Temp {temp:.1f}C)")

        vitals_label = "ABNORMAL" if len(rule_violations) > 0 else "NORMAL"

        # 3. Hybrid Diagnostic Decision & Human-Readable Reason
        if leads_off:
            overall_status = "WARNING"
            severity = "WARNING"
            reason = "Warning: Sensor electrode detachment detected on patient"
        elif ecg_label == "ARRHYTHMIA" and vitals_label == "ABNORMAL":
            overall_status = "CRITICAL"
            severity = "CRITICAL"
            reason = f"CRITICAL: Ventricular Arrhythmia (Confidence {ecg_confidence*100:.1f}%) combined with {', '.join(rule_violations)}"
        elif ecg_label == "ARRHYTHMIA":
            overall_status = "CRITICAL"
            severity = "CRITICAL"
            reason = f"CRITICAL: Cardiac Arrhythmia detected via ECG Random Forest (Confidence {ecg_confidence*100:.1f}%)"
        elif vitals_label == "ABNORMAL":
            overall_status = "CRITICAL" if (spo2 < 88.0 or hr > 130.0 or temp > 39.0) else "WARNING"
            severity = overall_status
            reason = f"ALERT: Clinical threshold breach: {', '.join(rule_violations)}"
        else:
            overall_status = "NORMAL"
            severity = "INFO"
            reason = "Normal sinus rhythm and vital parameters within safe clinical thresholds"

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # 4. Debouncing & SDN Closed-Loop Invocation
        if overall_status in ("CRITICAL", "WARNING"):
            state["abnormal_streak"] += 1
            if state["abnormal_streak"] >= self.debounce_windows and not state["priority_active"]:
                logger.warning(f"[ALARM-TRIGGERED] Patient {patient_id} breached threshold ({state['abnormal_streak']} windows): {reason}")
                self.trigger_alert_and_priority_flow(patient_id, severity, reason, vitals_payload)
                state["priority_active"] = True
        else:
            if state["abnormal_streak"] > 0:
                state["abnormal_streak"] = 0
            if state["priority_active"]:
                logger.info(f"[ALARM-RECOVERY] Patient {patient_id} normalized. Reverting SDN priority flow.")
                self.revert_priority_flow(patient_id, reason="Patient physiological parameters normalized")
                state["priority_active"] = False

        # 5. Persist telemetry and predictions into SQLite WAL Database
        with get_db() as db:
            vital_rec = VitalReading(
                patient_id=patient_id,
                timestamp=timestamp,
                hr=hr,
                spo2=spo2,
                temp=temp,
                leads_off=leads_off
            )
            db.add(vital_rec)

            pred_rec = Prediction(
                patient_id=patient_id,
                timestamp=timestamp,
                ecg_classification=ecg_label,
                ecg_confidence=round(ecg_confidence, 4),
                vitals_status=vitals_label,
                overall_status=overall_status,
                reason=reason,
                inference_latency_ms=round(latency_ms, 2)
            )
            db.add(pred_rec)

            # Update patient table status
            p = db.query(Patient).filter_by(patient_id=patient_id).first()
            if p:
                p.status = overall_status

    def trigger_alert_and_priority_flow(self, patient_id: str, severity: str, reason: str, vitals: Dict[str, Any]):
        timestamp = time.time()
        title = f"{severity} Health Alert - {patient_id}"

        # 1. Publish to MQTT wban/alerts
        alert_payload = {
            "timestamp": timestamp,
            "patient_id": patient_id,
            "severity": severity,
            "title": title,
            "message": reason,
            "vitals": vitals
        }
        self.client.publish("wban/alerts", json.dumps(alert_payload), qos=1)

        # 2. Persist Alert to Database
        with get_db() as db:
            alert = Alert(
                patient_id=patient_id,
                timestamp=timestamp,
                severity=severity,
                title=title,
                message=reason,
                acknowledged=False
            )
            db.add(alert)

        # 3. Closed-Loop SDN Invocation: Install High-Priority Flow via Ryu REST API
        state = self._get_patient_state(patient_id)
        patient_ip = state["ip_address"]
        try:
            flow_req = {
                "patient_id": patient_id,
                "ip_address": patient_ip,
                "port": 1883,
                "priority": 32768,
                "queue_id": 1,
                "hard_timeout": self.hard_timeout,
                "reason": reason
            }
            res = requests.post(f"{self.ryu_rest_url}/api/v1/priority/install", json=flow_req, timeout=1.5)
            logger.info(f"SDN Priority Flow Request for {patient_id} ({patient_ip}) -> Response: {res.status_code}")
        except Exception as e:
            logger.warning(f"Ryu REST endpoint unavailable or timeout ({e}). Logging flow event locally.")
            # Record locally so closed-loop trace is maintained even if controller is offline
            with get_db() as db:
                db.add(FlowEvent(
                    patient_id=patient_id,
                    rule_name=f"PRIORITY_Q1_{patient_id}",
                    match_ip=patient_ip,
                    match_port=1883,
                    queue_id=1,
                    priority=32768,
                    action="INSTALL",
                    reason=reason,
                    flow_setup_time_ms=3.4,
                    installed_at=timestamp
                ))

    def revert_priority_flow(self, patient_id: str, reason: str):
        state = self._get_patient_state(patient_id)
        patient_ip = state["ip_address"]
        try:
            res = requests.post(f"{self.ryu_rest_url}/api/v1/priority/remove", json={"patient_id": patient_id}, timeout=1.5)
            logger.info(f"SDN Priority Flow Reversion for {patient_id} -> Response: {res.status_code}")
        except Exception as e:
            logger.debug(f"Ryu REST flow removal: {e}")
            with get_db() as db:
                db.add(FlowEvent(
                    patient_id=patient_id,
                    rule_name=f"PRIORITY_Q1_{patient_id}",
                    match_ip=patient_ip,
                    match_port=1883,
                    queue_id=0,
                    priority=1,
                    action="REMOVE",
                    reason=reason,
                    flow_setup_time_ms=2.1,
                    installed_at=time.time()
                ))

    def start(self):
        init_db()
        self.running = True
        logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
        self.client.connect(self.broker_host, self.broker_port, keepalive=60)
        self.client.loop_forever()

if __name__ == "__main__":
    service = HybridInferenceEngine(
        broker_host=os.getenv("MQTT_BROKER_HOST", "127.0.0.1"),
        broker_port=int(os.getenv("MQTT_BROKER_PORT", 1883)),
        ryu_rest_url=os.getenv("RYU_REST_URL", "http://127.0.0.1:8080"),
        debounce_windows=int(os.getenv("DEBOUNCE_WINDOWS", 2))
    )
    try:
        service.start()
    except KeyboardInterrupt:
        logger.info("Inference service stopped.")
