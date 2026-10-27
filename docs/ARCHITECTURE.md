# CardioSDN: End-to-End System Architecture

This document details the architectural design of **Intelligent Healthcare Monitoring using Software-Defined Networking, IoT, and Machine Learning**.

---

## 1. System Architecture Diagram

```mermaid
graph TD
    subgraph WBAN_IoT_Layer ["WBAN IoT Sensing Layer (Hardware-Ready)"]
        SensorNode["WBAN Node / Replay Publisher<br/>(ESP32 Schema)"]
        ECG_Stream["360 Hz ECG Stream<br/>(wban/:id/ecg)"]
        Vitals_Stream["1 Hz Multi-Parameter Vitals<br/>(wban/:id/vitals)"]
        SensorNode --> ECG_Stream
        SensorNode --> Vitals_Stream
    end

    subgraph Transport_Layer ["Transport & Message Broker"]
        Mosquitto["MQTT Broker (QoS 1)<br/>Port 1883"]
        ECG_Stream --> Mosquitto
        Vitals_Stream --> Mosquitto
    end

    subgraph Edge_ML_Layer ["Edge Intelligence & Decision Engine"]
        InferenceSvc["ML Inference Service<br/>(Sliding Window Buffer)"]
        PanTomp["Pan-Tompkins<br/>Live R-Peak Detector"]
        RF_Model["Random Forest Classifier<br/>(ECG Arrhythmia / Normal)"]
        RulesEngine["Deterministic Rules<br/>(SpO2, HR, Temp Thresholds)"]
        Debouncer["Temporal Debouncer<br/>(N >= 2 Consecutive Windows)"]
        
        Mosquitto -->|Subscribes| InferenceSvc
        InferenceSvc --> PanTomp
        PanTomp --> RF_Model
        InferenceSvc --> RulesEngine
        RF_Model --> Debouncer
        RulesEngine --> Debouncer
    end

    subgraph Storage_Layer ["Data Persistence (WAL Mode)"]
        SQLiteDB[(SQLite WAL Database<br/>Composite Time Indexes)]
        InferenceSvc -->|Persists Vitals & Preds| SQLiteDB
    end

    subgraph SDN_Control_Layer ["SDN Dynamic Closed-Loop QoS"]
        RyuController["Ryu OpenFlow 1.3 Controller<br/>REST WSGI (Port 8080)"]
        OVS_Switches["Open vSwitch s1 & s2<br/>(10 Mbps TCLink Bottleneck)"]
        Queue0["Queue 0: Best Effort (1-4 Mbps)<br/>Cross Traffic / Background Noise"]
        Queue1["Queue 1: Priority Medical (6-10 Mbps)<br/>Guaranteed Zero-Loss Telemetry"]

        Debouncer -->|POST /api/v1/priority/install| RyuController
        RyuController -->|OpenFlow 1.3 OFPFlowMod<br/>Action: set_queue=1| OVS_Switches
        OVS_Switches --> Queue0
        OVS_Switches --> Queue1
        RyuController -->|Audit Log| SQLiteDB
    end

    subgraph Presentation_Layer ["Presentation & Clinical Triage"]
        FlaskServer["Flask Web Server<br/>(Port 5000)"]
        DashboardUI["Web Dashboard<br/>(Dark/Light Glassmorphism)"]
        Oscilloscope["360 Hz Oscilloscope Canvas"]
        Charts["Vendored Chart.js History"]
        
        SQLiteDB --> FlaskServer
        FlaskServer --> DashboardUI
        DashboardUI --> Oscilloscope
        DashboardUI --> Charts
    end
```

---

## 2. Closed-Loop Sequence Diagram

The closed-loop timing cycle illustrates the rapid response from anomaly injection to network traffic prioritization:

```mermaid
sequenceDiagram
    autonumber
    actor Patient as Simulated Patient (WBAN)
    participant Broker as MQTT Broker (Mosquitto)
    participant ML as ML Inference Service
    participant DB as SQLite WAL Database
    participant SDN as Ryu SDN Controller
    participant OVS as Open vSwitch (s1)
    participant Dash as Web Dashboard

    Patient->>Broker: Publish 360 Hz ECG & Vitals (wban/P101/vitals)
    Broker->>ML: Forward Telemetry Packet
    ML->>ML: Extract 9 ECG Features & Run RF Predict
    ML->>ML: Evaluate Clinical Threshold Rules (SpO2, HR, Temp)

    alt Normal Sinus Rhythm & Safe Thresholds
        ML->>DB: Insert VitalReading & Prediction (Status: NORMAL)
        ML->>Dash: Update Live Dashboard (Status: NORMAL)
    else Clinical Anomaly Breached (e.g., Tachycardia + Fever)
        ML->>ML: Increment Abnormal Window Streak
        Note over ML: Streak >= 2 Windows (Debounce Verified)
        ML->>Broker: Publish Alert to wban/alerts
        ML->>DB: Insert Alert Record (CRITICAL)
        ML->>SDN: POST /api/v1/priority/install (IP: 10.0.0.1, Queue: 1)
        SDN->>OVS: OFPFlowMod (priority=32768, action=set_queue:1, hard_timeout=60)
        OVS-->>SDN: Flow Entry Installed in Hardware / Kernel
        SDN->>DB: Log FlowEvent (Setup Time ~4.4 ms)
        ML->>Dash: Trigger Glowing Priority Active Banner
    end

    opt Patient Recovery & Normalization
        Patient->>Broker: Normal Telemetry Stream
        Broker->>ML: Forward Telemetry
        ML->>ML: Abnormal Streak Reset to 0
        ML->>SDN: POST /api/v1/priority/remove (P101)
        SDN->>OVS: OFPFlowMod DELETE (Revert to Queue 0)
        SDN->>DB: Log FlowEvent (Action: REMOVE)
        ML->>Dash: Priority Banner Deactivated
    end
```

---

## 3. Data Flow Walkthrough
1. **IoT Sensing:** Replay node generates continuous 360 Hz ECG and 1 Hz multi-parameter physiological telemetry matching ESP32 firmware output.
2. **QoS 1 Ingestion:** Telemetry is published over MQTT to `wban/<patient_id>/vitals` and `wban/<patient_id>/ecg`.
3. **Hybrid Classification:**
   - Morphological Pan-Tompkins analysis and Random Forest classification detect ectopic ventricular beats.
   - Deterministic rules independently flag hypoxemia, tachycardia, bradycardia, or fever.
4. **Temporal Filter:** Debouncing filter enforces 2 consecutive abnormal windows to avoid network oscillation on spurious noise.
5. **SDN Allocation:** An alert initiates an asynchronous REST call to the Ryu controller, which modifies switch flow tables in ~4.4 ms, routing the patient's IP traffic to guaranteed HTB Queue 1.
6. **Clinical Monitoring:** The Flask dashboard consumes real-time SSE telemetry, updates the 360 Hz oscilloscope canvas, and illuminates the SDN priority indicator.
