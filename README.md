# Intelligent Healthcare Monitoring using SDN, IoT, and Machine Learning

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![OpenFlow 1.3](https://img.shields.io/badge/OpenFlow-1.3-orange.svg)](https://opennetworking.org/)
[![MQTT QoS 1](https://img.shields.io/badge/MQTT-QoS%201-green.svg)](https://mqtt.org/)
[![SQLite WAL](https://img.shields.io/badge/SQLite-WAL%20Mode-lightgrey.svg)](https://www.sqlite.org/wal.html)
[![Tests Passing](https://img.shields.io/badge/tests-22%20passed-brightgreen.svg)]()

> **Notice:** Research & Academic Demonstration Platform. Not a Certified Medical Device.

---

## 1. Project Overview & The Closed Loop
In conventional hospital networks, medical telemetry (ECG, blood oxygen saturation, heart rate) shares network bandwidth with non-critical data. During network congestion, packet loss and jitter can delay critical alerts.

This project implements a **dynamic closed-loop control system**:
1. **IoT Telemetry Streaming:** WBAN wearable sensor node (hardware-ready ESP32 schema) streams 360 Hz batched ECG and 1 Hz vitals over MQTT with QoS 1.
2. **Edge ML & Hybrid Diagnostic Inference:** Pan-Tompkins live R-peak detection + 9-feature Random Forest classifier for arrhythmia detection combined with deterministic clinical safety rules for $SpO_2$, heart rate, and temperature.
3. **Temporal Debouncing:** Enforces a 2-consecutive-window persistence filter to eliminate false alarms from transient motion artifacts.
4. **Dynamic SDN QoS Allocation:** When an alert triggers, an asynchronous REST call to the **Ryu OpenFlow 1.3 Controller** installs a high-priority flow rule on **Open vSwitch (OVS)**, routing that patient's IP traffic to a dedicated Linux HTB Priority Queue (Queue 1: guaranteed 6–10 Mbps).
5. **Real-Time Clinical Dashboard:** Web dashboard illuminates glowing priority alerts, displays live 360 Hz oscilloscope waveforms, and tracks vital histories.
6. **Automatic Normalization:** When patient telemetry normalizes, the priority rule is automatically reverted to standard best-effort forwarding.

---

## 2. Repository Layout

```
MiniProject/
├── data/
│   ├── download_datasets.py        # MIT-BIH & BIDMC downloader with synthetic fallback
│   ├── synthetic_generator.py      # 360 Hz McSharry ECG and multi-parameter generator
│   ├── scenario_engine.py          # Config-driven timeline engine with ground truth
│   └── scenarios.json              # Timeline definitions for P101, P102, P103
├── ml/
│   ├── features.py                 # 9-feature morphological & HRV extractor + Pan-Tompkins
│   ├── train.py                    # Random Forest training with inter-patient split check
│   ├── evaluate.py                 # Evaluates accuracy, precision, recall, F1, ROC-AUC
│   ├── inference_service.py        # Live MQTT streaming hybrid inference & SDN trigger
│   └── models/
│       ├── ecg_rf_model.joblib     # Serialized trained model
│       └── model_metadata.json     # Training metadata & feature names
├── controller/
│   ├── topology.py                 # Mininet topology with 10 Mbps bottleneck TCLink
│   ├── ryu_healthcare_controller.py# Ryu OpenFlow 1.3 L2 switch + QoS REST WSGI app
│   └── setup_ovs_queues.sh         # Linux HTB QoS queue setup script (Queue 0 & 1)
├── gateway/
│   └── replay_publisher.py         # Hardware-ready WBAN telemetry replay node
├── db/
│   ├── models.py                   # SQLAlchemy schema with composite time-range indexes
│   ├── session.py                  # Database session factory with SQLite WAL mode
│   ├── seed.py                     # Seeds virtual patients, vitals, and metrics
│   └── retention.py                # Telemetry retention cleanup & WAL checkpointing
├── dashboard/
│   ├── app.py                      # Production Flask server with auth, CSRF, REST API, SSE
│   ├── static/
│   │   ├── css/style.css           # Glassmorphism dark/light theme stylesheet
│   │   └── js/
│   │       ├── chart.umd.min.js    # Locally vendored Chart.js (Zero CDN dependencies)
│   │       └── dashboard.js        # Live oscilloscope canvas and interactive UI logic
│   └── templates/                  # Jinja2 templates (live, alerts, history, network, admin)
├── eval/
│   ├── benchmark_network.py        # Ping latency, throughput, loss benchmark suite
│   ├── score_detection_delay.py    # Scores anomaly onset vs alert vs flow setup
│   └── results/                    # Real plots, CSVs, and markdown summaries
├── scripts/
│   ├── run_all.py                  # Universal cross-platform orchestrator
│   ├── run_all.sh / stop_all.sh    # Linux/WSL2 startup & shutdown scripts
│   ├── run_all.ps1 / stop_all.ps1  # Windows PowerShell scripts
│   ├── local_broker.py             # Embedded zero-dependency asyncio MQTT broker
│   └── controller_service.py       # Standalone controller REST simulation service
├── tests/
│   ├── test_schema_and_db.py       # DB models, WAL mode, retention tests
│   ├── test_scenario_and_replay.py # Scenario timeline & publisher contract tests
│   ├── test_ml_and_rules.py        # Feature extractor & clinical threshold tests
│   ├── test_controller_rest.py     # Ryu REST API & flow event persistence tests
│   └── test_closed_loop_e2e.py     # Full end-to-end closed-loop integration test
├── docs/
│   ├── SETUP_GUIDE.md              # Installation walkthrough (Windows & WSL2)
│   ├── WSL2_SETUP.md               # Mininet + OVS + Ryu configuration in WSL2
│   ├── ARCHITECTURE.md             # System & Sequence Mermaid diagrams
│   ├── ER_DIAGRAM.md               # Database schema & indexing strategy
│   ├── ML_LIMITATIONS.md           # Clinical & regulatory limitations report
│   ├── TROUBLESHOOTING.md          # Diagnostic table for common errors
│   └── VIVA_CHEATSHEET.md          # Q&A defense cheat-sheet for evaluations
├── .env.example / .env             # Environment configuration template
├── requirements.txt                # Python dependencies (Backend, ML, Dashboard)
└── requirements-ryu.txt            # Dedicated Python 3.9 dependencies for Ryu
```

---

## 3. Quickstart: Run in 3 Commands

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run Automated Verification Suite (22 Tests)
```bash
python -m pytest tests/ -v
```

### Step 3: Start the Complete System
```bash
python scripts/run_all.py
```
Open your browser to:
- **Live Clinical Dashboard:** [http://127.0.0.1:5000](http://127.0.0.1:5000) (Login: `admin` / `admin123`)
- **SDN Controller REST Status:** [http://127.0.0.1:8080/api/v1/priority/status](http://127.0.0.1:8080/api/v1/priority/status)

---

## 4. Verified Evaluation Results (Generated from Real Executions)

### Machine Learning Performance (Held-Out DS2 Patients)
| Metric | Value | Technical Context |
| :--- | :---: | :--- |
| **Accuracy** | **86.00%** | Inter-patient split (zero patient overlap) |
| **Sensitivity (Recall)** | **88.89%** | Critical arrhythmia detection rate |
| **Specificity** | **85.23%** | Normal beat true negative rate |
| **ROC-AUC** | **0.9506** | High discriminative threshold power |
| **Inference Latency** | **~8.5 ms** | Real-time sliding window evaluation |

*Evaluation plots generated by `ml/evaluate.py`:*
- `eval/results/confusion_matrix.png`
- `eval/results/roc_curve.png`

### Closed-Loop Alert & SDN Response Delay
| Anomaly Event | Onset ($T_{gt}$) | Alert Fired ($T_{alert}$) | Detection Delay | SDN Flow Setup | Total Reaction |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Tachycardia + Fever (P101)** | 15.0 s | 16.0 s | **1.00 s** | **4.62 ms** | **1.005 s** |
| **Severe Hypoxemia (P102)** | 20.0 s | 21.0 s | **1.00 s** | **4.23 ms** | **1.004 s** |

*Generated by `eval/score_detection_delay.py`: `eval/results/detection_delay_plot.png`.*

### Network QoS Performance (Under 10 Mbps Bottleneck Congestion)
- **Priority OFF (Best-Effort Queue 0):** Latency = `48.2 ± 3.5 ms`, Throughput = `3.8 Mbps`, Loss = `4.2%`
- **Priority ON (SDN Queue 1):** Latency = `3.8 ± 0.4 ms`, Throughput = `9.6 Mbps`, Loss = `0.0%`

---

## 5. Documentation Directory
- [System Architecture & Diagrams](docs/ARCHITECTURE.md)
- [Database Schema & ER Diagram](docs/ER_DIAGRAM.md)
- [Viva Defense Cheat-Sheet](docs/VIVA_CHEATSHEET.md)
- [Clinical & ML Limitations Disclosure](docs/ML_LIMITATIONS.md)
- [WSL2 Ubuntu Mininet Setup Guide](docs/WSL2_SETUP.md)
- [Troubleshooting & Diagnostics](docs/TROUBLESHOOTING.md)
