# WSL2 Ubuntu Setup Guide: Mininet, Open vSwitch, and Ryu Controller

This document provides exact, verified step-by-step instructions to run the Software-Defined Networking (SDN) and Open vSwitch (OVS) components under WSL2 (Windows Subsystem for Linux) on Ubuntu 20.04 / 22.04 LTS.

---

## 1. Why WSL2 is Required for the SDN Layer
Open vSwitch and Mininet rely heavily on Linux kernel network namespaces (`netns`), OpenFlow kernel modules (`openvswitch.ko`), and traffic control (`tc-htb`) for hardware emulation. These Linux kernel features are not natively present in Windows NT. 

The backend (Flask dashboard, SQLite WAL database, ML inference, and telemetry replay) runs natively on any OS, while the network emulator runs inside WSL2 or native Linux.

---

## 2. Installation Commands (WSL2 Ubuntu)

### Step 2.1: Update System & Install Mininet, OVS, and Mosquitto
Open your WSL2 Ubuntu terminal and run:
```bash
sudo apt-get update
sudo apt-get install -y \
    mininet \
    openvswitch-switch \
    openvswitch-common \
    iperf3 \
    mosquitto \
    mosquitto-clients \
    git \
    curl \
    software-properties-common
```

### Step 2.2: Setup Dedicated Python 3.9 Virtualenv for Ryu
*Note: Ryu requires Python 3.9 with pinned `eventlet==0.30.2` due to compatibility constraints in newer Python releases.*
```bash
# Add deadsnakes PPA if Python 3.9 is not installed
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.9 python3.9-venv python3.9-dev build-essential

# Navigate to project directory
cd "/mnt/d/PRESIDENCY UNIVERSITY/MiniProject"

# Create and activate Ryu virtual environment
python3.9 -m venv ryu_env
source ryu_env/bin/activate

# Install Ryu with pinned eventlet
pip install --upgrade pip setuptools wheel
pip install -r requirements-ryu.txt
```

---

## 3. Running the SDN System Step-by-Step

### Terminal 1: Start Open vSwitch Service & Ryu Controller
```bash
# 1. Start OVS service
sudo service openvswitch-switch start
sudo ovs-vsctl show

# 2. Activate Python 3.9 environment
source ryu_env/bin/activate

# 3. Launch Ryu Controller with OpenFlow 1.3 & REST WSGI
ryu-manager --observe-links --ofp-tcp-listen-port 6653 controller/ryu_healthcare_controller.py
```
*Ryu will listen for switches on port `6653` and expose the REST API on `http://127.0.0.1:8080`.*

### Terminal 2: Start Mininet Topology
In a separate WSL2 terminal:
```bash
cd "/mnt/d/PRESIDENCY UNIVERSITY/MiniProject"
sudo python3 controller/topology.py
```
*Mininet will create switches `s1`, `s2` and hosts `sensor`, `noise`, `gateway`, `server` with the 10 Mbps bottleneck link.*

### Terminal 3: Apply OVS QoS Queues
```bash
sudo bash controller/setup_ovs_queues.sh
```

---

## 4. Verification & Flow Table Inspection
Verify that OpenFlow 1.3 rules and QoS queues are active:

1. **Dump OpenFlow 1.3 Flows:**
   ```bash
   sudo ovs-ofctl -O OpenFlow13 dump-flows s1
   ```
   *Expected Output: Table-miss rule (priority=0) plus dynamic patient priority flows (priority=32768, action=set_queue:1).*

2. **Inspect Queue Statistics:**
   ```bash
   sudo ovs-ofctl -O OpenFlow13 queue-stats s1
   ```
   *Verifies packet counters climbing in Queue 1 when an alert is active.*

3. **Test Priority REST API manually:**
   ```bash
   # Query status
   curl -X GET http://127.0.0.1:8080/api/v1/priority/status

   # Test flow installation
   curl -X POST http://127.0.0.1:8080/api/v1/priority/install \
     -H "Content-Type: application/json" \
     -d '{"patient_id":"P101","ip_address":"10.0.0.1","port":1883,"priority":32768,"queue_id":1,"hard_timeout":60}'
   ```
