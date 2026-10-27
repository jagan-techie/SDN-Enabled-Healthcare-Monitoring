# scripts/run_all.py - Universal one-command startup orchestrator with graceful shutdown
import os
import sys
import time
import subprocess
import signal
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Orchestrator] %(message)s")
logger = logging.getLogger("Orchestrator")

PROCESSES = []

def get_python_executable():
    """Detects virtual environment python if available to guarantee installed dependencies are used."""
    if sys.platform == "win32":
        venv_python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = ROOT_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def start_process(command: list, name: str, wait_sec: float = 1.0):
    logger.info(f"Starting {name}...")
    proc = subprocess.Popen(command, cwd=str(ROOT_DIR))
    PROCESSES.append((name, proc))
    time.sleep(wait_sec)
    if proc.poll() is not None:
        logger.error(f"Failed to start {name} (exited with code {proc.returncode})")
        shutdown_all()
        sys.exit(1)
    logger.info(f"{name} running [PID: {proc.pid}]")
    return proc

def cleanup_ports(ports=(1883, 8080, 5000)):
    """Proactively terminates any lingering zombie processes holding required ports."""
    if sys.platform == "win32":
        for port in ports:
            try:
                out = subprocess.check_output(f'netstat -ano | findstr ":{port} "', shell=True, text=True)
                for line in out.strip().splitlines():
                    if "LISTENING" in line:
                        parts = line.strip().split()
                        pid = parts[-1]
                        if pid and pid != "0" and int(pid) != os.getpid():
                            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

def shutdown_all(signum=None, frame=None):
    logger.info("\nShutting down all CardioSDN healthcare services...")
    for name, proc in reversed(PROCESSES):
        if proc.poll() is None:
            logger.info(f"Stopping {name} [PID: {proc.pid}]...")
            try:
                if sys.platform == "win32":
                    subprocess.run(f"taskkill /F /T /PID {proc.pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    proc.terminate()
                    proc.wait(timeout=2)
            except Exception:
                proc.kill()
    cleanup_ports()
    logger.info("All services stopped cleanly.")
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, shutdown_all)
    signal.signal(signal.SIGTERM, shutdown_all)

    # Ensure required ports are clean before boot
    cleanup_ports()

    print("=" * 70)
    print("   Intelligent Healthcare Monitoring using SDN, IoT & Machine Learning   ")
    print("                      CardioSDN Production Stack                         ")
    print("=" * 70)

    python_bin = get_python_executable()
    logger.info(f"Using Python runtime: {python_bin}")

    # 1. Initialize Database & Seed Patients if needed
    logger.info("Checking database and seeding patient records...")
    subprocess.run([python_bin, "-u", "db/seed.py"], cwd=str(ROOT_DIR), check=True)

    # 2. Start MQTT Broker
    start_process([python_bin, "-u", "scripts/local_broker.py"], "MQTT Broker (Port 1883)", wait_sec=1.5)

    # 3. Start SDN Controller REST Service
    start_process([python_bin, "-u", "scripts/controller_service.py"], "SDN Controller REST Service (Port 8080)", wait_sec=1.5)

    # 4. Start ML Streaming Hybrid Inference Service
    start_process([python_bin, "-u", "ml/inference_service.py"], "ML Hybrid Inference Engine", wait_sec=2.0)

    # 5. Start Flask Web Dashboard
    start_process([python_bin, "-u", "dashboard/app.py"], "Flask Web Dashboard (Port 5000)", wait_sec=2.0)

    # 6. Start WBAN Sensor Replay Publisher
    start_process([python_bin, "-u", "gateway/replay_publisher.py", "--speed", "1.0"], "WBAN Sensor Replay Publisher", wait_sec=1.0)

    print("=" * 70)
    print("SYSTEM OPERATIONAL & STREAMING")
    print("  -> Web Dashboard:      http://127.0.0.1:5000 (Login: admin / admin123)")
    print("  -> SDN Controller API: http://127.0.0.1:8080/api/v1/priority/status")
    print("  -> MQTT Broker:        127.0.0.1:1883")
    print("  -> Replay Publisher:   Streaming P101, P102, P103 at 1x real-time speed")
    print("Press Ctrl+C to terminate all services.")
    print("=" * 70)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_all()

if __name__ == "__main__":
    main()