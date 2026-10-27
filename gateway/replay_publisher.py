# gateway/replay_publisher.py - Hardware-ready WBAN sensor node replay publisher
"""
Simulates WBAN (Wireless Body Area Network) wearable sensor nodes streaming physiological telemetry.
Streams:
  - 1 Hz multi-parameter vitals to topic: wban/<patient_id>/vitals
  - 360 Hz batched ECG waveform to topic: wban/<patient_id>/ecg
Schema and topics are 1:1 identical to ESP32 FreeRTOS firmware for seamless drop-in hardware replacement.
QoS: QoS 1 (At least once delivery) ensures critical medical telemetry is never dropped.
"""

import os
import sys
import time
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
import paho.mqtt.client as mqtt

# Add workspace root to sys.path
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data.scenario_engine import ScenarioEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [WBAN-Node] %(message)s")
logger = logging.getLogger("ReplayPublisher")

class WBANReplayPublisher:
    def __init__(
        self,
        broker_host: str = "127.0.0.1",
        broker_port: int = 1883,
        patient_ids: Optional[List[str]] = None,
        speed: float = 1.0,
        qos: int = 1,
        config_path: Optional[str] = None
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.speed = max(0.1, speed)
        self.qos = qos
        self.engine = ScenarioEngine(config_path=config_path)
        self.patient_ids = patient_ids or self.engine.get_patient_ids()
        if hasattr(mqtt, "CallbackAPIVersion"):
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"wban_replay_node_{os.getpid()}", protocol=mqtt.MQTTv311)
        else:
            self.client = mqtt.Client(client_id=f"wban_replay_node_{os.getpid()}", protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.connected = False
        self.running = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port} with QoS {self.qos}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker (rc: {rc}). Retrying...")

    def connect(self, max_retries: int = 5, retry_interval: float = 2.0):
        for attempt in range(1, max_retries + 1):
            try:
                self.client.connect(self.broker_host, self.broker_port, keepalive=60)
                self.client.loop_start()
                # Wait briefly for CONNACK
                for _ in range(10):
                    if self.connected:
                        return
                    time.sleep(0.1)
                if self.connected:
                    return
            except Exception as e:
                logger.warning(f"Broker connection attempt {attempt}/{max_retries} failed: {e}")
                time.sleep(retry_interval)
        logger.warning("Could not establish initial connection. Will run loop in background.")

    def publish_frame(self, patient_id: str, reading: Dict[str, Any]):
        """Publishes telemetry using the hardware-ready JSON schema."""
        # 1. Topic: wban/<patient_id>/vitals
        vitals_payload = {
            "timestamp": reading["timestamp"],
            "patient_id": patient_id,
            "hr": reading["hr"],
            "spo2": reading["spo2"],
            "temp": reading["temp"],
            "leads_off": reading["leads_off"]
        }
        vitals_topic = f"wban/{patient_id}/vitals"
        self.client.publish(vitals_topic, json.dumps(vitals_payload), qos=self.qos)

        # 2. Topic: wban/<patient_id>/ecg
        ecg_payload = {
            "timestamp": reading["timestamp"],
            "patient_id": patient_id,
            "fs": 360,
            "ecg_batch": reading["ecg_batch"]
        }
        ecg_topic = f"wban/{patient_id}/ecg"
        self.client.publish(ecg_topic, json.dumps(ecg_payload), qos=self.qos)

    def run_replay(self, duration_sec: Optional[float] = None):
        """Streams multi-patient telemetry continuously or for duration_sec."""
        self.running = True
        logger.info(f"Starting WBAN replay for patients: {self.patient_ids} at {self.speed}x speed")
        start_time = time.time()
        elapsed_scenario_sec = 0.0

        try:
            while self.running:
                step_start = time.time()
                for pid in self.patient_ids:
                    reading = self.engine.sample_reading(pid, elapsed_sec=elapsed_scenario_sec)
                    self.publish_frame(pid, reading)
                    if reading["is_anomalous"]:
                        logger.info(f"[ANOMALY-INJECTED] Patient {pid}: GT={reading['ground_truth']} (HR={reading['hr']}, SpO2={reading['spo2']}%, Temp={reading['temp']}C)")

                elapsed_scenario_sec += 1.0
                if duration_sec is not None and elapsed_scenario_sec >= duration_sec:
                    logger.info(f"Replay completed target duration: {duration_sec}s")
                    break

                # Account for speed multiplier: 1s simulated time takes (1.0 / speed) wall-clock seconds
                sleep_target = (1.0 / self.speed) - (time.time() - step_start)
                if sleep_target > 0:
                    time.sleep(sleep_target)
        except KeyboardInterrupt:
            logger.info("Replay stopped by user interrupt.")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        logger.info("WBAN Replay publisher stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WBAN Sensor Telemetry Replay Node")
    parser.add_argument("--broker", default=os.getenv("MQTT_BROKER_HOST", "127.0.0.1"), help="MQTT broker host")
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_BROKER_PORT", 1883)), help="MQTT broker port")
    parser.add_argument("--speed", type=float, default=float(os.getenv("REPLAY_SPEED", 1.0)), help="Playback speed multiplier")
    parser.add_argument("--duration", type=float, default=None, help="Replay duration in seconds (optional)")
    parser.add_argument("--patients", nargs="+", default=None, help="Specific patient IDs to stream")
    args = parser.parse_args()

    publisher = WBANReplayPublisher(
        broker_host=args.broker,
        broker_port=args.port,
        patient_ids=args.patients,
        speed=args.speed
    )
    publisher.connect()
    publisher.run_replay(duration_sec=args.duration)
