#!/bin/bash
# scripts/run_all.sh - One-command startup script for Linux and WSL2 Ubuntu environments
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=========================================================================="
echo " Starting CardioSDN Healthcare System Stack (Linux / WSL2) "
echo "=========================================================================="

# 1. Initialize DB
python3 db/seed.py

# 2. Check for Mosquitto or use local broker
if command -v mosquitto >/dev/null 2>&1; then
    echo "Starting Mosquitto daemon on port 1883..."
    mosquitto -c config/mosquitto.conf -d || true
else
    echo "Starting embedded local MQTT broker..."
    python3 scripts/local_broker.py > /tmp/cardiosdn_mqtt.log 2>&1 &
    echo $! > /tmp/cardiosdn_mqtt.pid
fi

# 3. Start SDN Controller (Ryu or Controller Service)
if [ -d "ryu_env" ]; then
    echo "Starting Ryu Controller in Python 3.9 virtual environment..."
    source ryu_env/bin/activate
    ryu-manager --observe-links controller/ryu_healthcare_controller.py > /tmp/cardiosdn_ryu.log 2>&1 &
    echo $! > /tmp/cardiosdn_ryu.pid
    deactivate
else
    echo "Starting standalone SDN Controller REST Service on port 8080..."
    python3 scripts/controller_service.py > /tmp/cardiosdn_controller.log 2>&1 &
    echo $! > /tmp/cardiosdn_controller.pid
fi

# 4. Start ML Streaming Inference Service
echo "Starting ML Hybrid Inference Service..."
python3 ml/inference_service.py > /tmp/cardiosdn_inference.log 2>&1 &
echo $! > /tmp/cardiosdn_inference.pid

# 5. Start Flask Web Dashboard
echo "Starting Flask Dashboard on http://127.0.0.1:5000..."
python3 dashboard/app.py > /tmp/cardiosdn_dashboard.log 2>&1 &
echo $! > /tmp/cardiosdn_dashboard.pid

# 6. Start WBAN Sensor Replay Publisher
echo "Starting WBAN Replay Publisher..."
python3 gateway/replay_publisher.py --speed 1.0 > /tmp/cardiosdn_replay.log 2>&1 &
echo $! > /tmp/cardiosdn_replay.pid

echo "=========================================================================="
echo "All services launched in background!"
echo "  - Web Dashboard:      http://127.0.0.1:5000 (Login: admin / admin123)"
echo "  - SDN Controller API: http://127.0.0.1:8080/api/v1/priority/status"
echo "To stop all services, run: bash scripts/stop_all.sh"
echo "=========================================================================="
