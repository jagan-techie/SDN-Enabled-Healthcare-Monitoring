#!/bin/bash
# scripts/stop_all.sh - Clean shutdown script for all CardioSDN background processes
echo "Stopping all CardioSDN healthcare services..."

for pid_file in /tmp/cardiosdn_*.pid; do
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        echo "Killing PID $PID from $pid_file..."
        kill -15 "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null || true
        rm -f "$pid_file"
    fi
done

# Kill any remaining instances by process pattern
pkill -f "python.*dashboard/app.py" 2>/dev/null || true
pkill -f "python.*ml/inference_service.py" 2>/dev/null || true
pkill -f "python.*gateway/replay_publisher.py" 2>/dev/null || true
pkill -f "python.*scripts/local_broker.py" 2>/dev/null || true
pkill -f "python.*scripts/controller_service.py" 2>/dev/null || true
pkill -f "ryu-manager" 2>/dev/null || true

echo "All CardioSDN processes terminated cleanly."
