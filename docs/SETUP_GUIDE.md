# CardioSDN: Comprehensive System Setup & Installation Guide

This guide walks through setting up the complete **Intelligent Healthcare Monitoring using SDN, IoT and Machine Learning** platform on Windows and Linux/WSL2.

---

## 1. Prerequisites
- **Python:** Python 3.10+ (tested on Python 3.11 and 3.15) for backend, ML, and dashboard.
- **Python 3.9:** Dedicated environment for Ryu SDN Controller (if running native Ryu in WSL2/Linux).
- **Operating Systems Supported:**
  - **Windows 10/11:** Full native support for IoT replay, MQTT broker, SQLite WAL, ML hybrid inference, and Flask dashboard. SDN layer uses controller simulation REST service.
  - **Linux / WSL2 Ubuntu:** Full native support for Mininet OpenFlow 1.3 topology, OVS Linux HTB queues, Ryu controller, and background iperf network congestion.

---

## 2. Windows Quickstart (Native)

### Step 2.1: Clone and Install Dependencies
```powershell
# In PowerShell / Command Prompt
cd "d:\PRESIDENCY UNIVERSITY\MiniProject"

# Install core dependencies
python -m pip install -r requirements.txt
```

### Step 2.2: Generate Datasets & Train Model
```powershell
# Generate verified benchmark dataset
python data/download_datasets.py

# Train Random Forest classifier with zero-leakage inter-patient split
python ml/train.py

# Evaluate model and generate plots
python ml/evaluate.py
```

### Step 2.3: One-Command Start
```powershell
python scripts/run_all.py
```
Open your browser to:
- **Dashboard:** [http://127.0.0.1:5000](http://127.0.0.1:5000) (Login: `admin` / `admin123`)
- **SDN Controller Status:** [http://127.0.0.1:8080/api/v1/priority/status](http://127.0.0.1:8080/api/v1/priority/status)

---

## 3. Linux / WSL2 Ubuntu Complete SDN Mininet Setup

### Step 3.1: Install System Packages
```bash
sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch openvswitch-testcontroller mosquitto mosquitto-clients iperf3 python3-pip
```

### Step 3.2: Create Python 3.9 Environment for Ryu
```bash
python3.9 -m venv ryu_env
source ryu_env/bin/activate
pip install -r requirements-ryu.txt
deactivate
```

### Step 3.3: Launch Stack with Mininet
1. **Terminal 1: Start Controller & OVS**
   ```bash
   sudo service openvswitch-switch start
   source ryu_env/bin/activate
   ryu-manager --observe-links controller/ryu_healthcare_controller.py
   ```
2. **Terminal 2: Launch Mininet Topology**
   ```bash
   sudo python3 controller/topology.py
   ```
3. **Terminal 3: Apply OVS QoS Queues**
   ```bash
   sudo bash controller/setup_ovs_queues.sh
   ```
4. **Terminal 4: Start Replay, ML Inference, and Dashboard**
   ```bash
   bash scripts/run_all.sh
   ```

---

## 4. Running the Pytest Verification Suite
To verify the entire system across all components:
```bash
python -m pytest tests/ -v
```
All 22 test cases will execute:
- Schema, foreign keys, and WAL session queries
- Scenario engine and timeline slicing
- ML Pan-Tompkins R-peak detector and Random Forest inference
- Clinical threshold checks
- SDN REST WSGI priority flow installation & deletion
- Flask dashboard authentication, CSRF, and REST endpoints
- End-to-end closed-loop automated test
