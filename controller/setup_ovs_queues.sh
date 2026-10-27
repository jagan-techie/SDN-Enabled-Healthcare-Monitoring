#!/bin/bash
# controller/setup_ovs_queues.sh - Configure Open vSwitch Linux-HTB QoS queues for healthcare traffic
# OpenFlow 1.3 set_queue action directs traffic to Queue 0 (Best-Effort) or Queue 1 (Priority).

set -e

echo "=== Configuring Open vSwitch QoS Queues on Switch s1 ==="

# Clean existing QoS records
ovs-vsctl --all destroy qos || true
ovs-vsctl --all destroy queue || true

# Egress port connecting s1 to s2 is typically s1-eth3
PORT="s1-eth3"

echo "Applying Linux HTB QoS to interface: $PORT"
ovs-vsctl -- set port "$PORT" qos=@newqos \
  -- --id=@newqos create qos type=linux-htb other-config:max-rate=10000000 \
     queues=0=@q0,1=@q1 \
  -- --id=@q0 create queue other-config:min-rate=1000000 other-config:max-rate=4000000 \
  -- --id=@q1 create queue other-config:min-rate=6000000 other-config:max-rate=10000000

echo "=== OVS QoS and Queues Created Successfully ==="
echo "Queue 0 (Best Effort): Min 1 Mbps, Max 4 Mbps"
echo "Queue 1 (High Priority Medical Telemetry): Min 6 Mbps, Max 10 Mbps (guaranteed bandwidth)"
echo ""
echo "Current QoS table:"
ovs-vsctl list qos
echo ""
echo "Current Queue table:"
ovs-vsctl list queue
