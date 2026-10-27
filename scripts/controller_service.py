# scripts/controller_service.py - Standalone controller REST service for cross-platform simulation and testing
import os
import sys
import time
import json
import logging
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.session import get_db, init_db
from db.models import FlowEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [SDNControllerService] %(message)s")
logger = logging.getLogger("SDNControllerService")

ACTIVE_FLOWS = {}

class SDNRESTRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/v1/priority/status":
            self._send_json(200, {
                "controller": "OpenFlow 1.3 SDN Controller (Active)",
                "connected_switches": ["s1", "s2"],
                "active_priority_flows_count": len(ACTIVE_FLOWS),
                "active_priority_flows": ACTIVE_FLOWS,
                "timestamp": time.time()
            })
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        t_start = time.perf_counter()
        url = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_len).decode("utf-8")) if content_len > 0 else {}

        if url.path == "/api/v1/priority/install":
            patient_id = body.get("patient_id", "P101")
            ip_address = body.get("ip_address", "10.0.0.1")
            port = int(body.get("port", 1883))
            queue_id = int(body.get("queue_id", 1))
            priority = int(body.get("priority", 32768))
            hard_timeout = int(body.get("hard_timeout", 60))
            reason = body.get("reason", "Critical clinical alert")

            # Emulate real OpenFlow 1.3 transaction round-trip (2.0 to 5.0 ms)
            time.sleep(0.003)
            setup_time_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            timestamp = time.time()

            flow_record = {
                "patient_id": patient_id,
                "ip_address": ip_address,
                "port": port,
                "queue_id": queue_id,
                "priority": priority,
                "hard_timeout": hard_timeout,
                "reason": reason,
                "installed_at": timestamp,
                "setup_time_ms": setup_time_ms,
                "switches": ["s1", "s2"]
            }
            ACTIVE_FLOWS[patient_id] = flow_record

            # Persist flow event to SQLite WAL database
            with get_db() as db:
                db.add(FlowEvent(
                    patient_id=patient_id,
                    rule_name=f"PRIORITY_Q1_{patient_id}",
                    match_ip=ip_address,
                    match_port=port,
                    queue_id=queue_id,
                    priority=priority,
                    action="INSTALL",
                    reason=reason,
                    flow_setup_time_ms=setup_time_ms,
                    installed_at=timestamp
                ))

            logger.info(f"[SDN-FLOW-INSTALLED] Patient={patient_id} IP={ip_address} Queue={queue_id} SetupTime={setup_time_ms}ms")
            self._send_json(200, {"status": "SUCCESS", "flow": flow_record})

        elif url.path == "/api/v1/priority/remove":
            patient_id = body.get("patient_id")
            if patient_id in ACTIVE_FLOWS:
                flow = ACTIVE_FLOWS.pop(patient_id)
                time.sleep(0.002)
                with get_db() as db:
                    db.add(FlowEvent(
                        patient_id=patient_id,
                        rule_name=f"PRIORITY_Q1_{patient_id}",
                        match_ip=flow["ip_address"],
                        match_port=flow["port"],
                        queue_id=0,
                        priority=1,
                        action="REMOVE",
                        reason="Telemetry normalized",
                        flow_setup_time_ms=2.1,
                        installed_at=time.time()
                    ))
                logger.info(f"[SDN-FLOW-REMOVED] Patient={patient_id} reverted to Best Effort Queue 0")
                self._send_json(200, {"status": "SUCCESS", "message": f"Flow removed for {patient_id}"})
            else:
                self._send_json(200, {"status": "NOT_FOUND", "message": "No active flow"})
        else:
            self._send_json(404, {"error": "Not found"})

def run_controller_service(host: str = "0.0.0.0", port: int = 8080):
    init_db()
    server = HTTPServer((host, port), SDNRESTRequestHandler)
    logger.info(f"SDN Controller REST Service listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("SDN Controller REST Service stopped.")

if __name__ == "__main__":
    port = int(os.getenv("RYU_PORT", 8080))
    run_controller_service(port=port)
