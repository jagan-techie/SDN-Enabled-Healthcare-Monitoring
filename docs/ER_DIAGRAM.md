# Healthcare SDN-IoT Database Architecture & Entity-Relationship Diagram

This document describes the relational database schema implemented in SQLite (WAL mode) via SQLAlchemy ORM. The schema is fully compliant with PostgreSQL and TimescaleDB for high-throughput time-series production scaling.

## Mermaid ER Diagram

```mermaid
erDiagram
    PATIENTS ||--o{ VITALS : "records"
    PATIENTS ||--o{ PREDICTIONS : "generates"
    PATIENTS ||--o{ ALERTS : "triggers"
    PATIENTS ||--o{ FLOW_EVENTS : "allocates"

    PATIENTS {
        string patient_id PK "Unique patient identifier (e.g., P101)"
        string name "Patient full name"
        int age "Patient age"
        string gender "Gender (M/F/Other)"
        string room "Assigned ward or ICU room"
        string ip_address "Static IP of patient's WBAN node"
        string mac_address "MAC address of WBAN device"
        string status "Current clinical status (NORMAL/CRITICAL)"
        datetime created_at "Registration timestamp"
    }

    VITALS {
        int id PK "Autoincrement primary key"
        string patient_id FK "References PATIENTS"
        float timestamp "Unix epoch timestamp (seconds)"
        float hr "Heart rate in beats per minute (bpm)"
        float spo2 "Blood oxygen saturation percentage (%)"
        float temp "Body temperature (Celsius)"
        boolean leads_off "Sensor electrode detachment flag"
        datetime created_at "Ingestion timestamp"
    }

    PREDICTIONS {
        int id PK "Autoincrement primary key"
        string patient_id FK "References PATIENTS"
        float timestamp "Unix epoch timestamp"
        string ecg_classification "ML result: NORMAL or ARRHYTHMIA"
        float ecg_confidence "Random Forest model confidence"
        string vitals_status "Threshold evaluation: NORMAL or ABNORMAL"
        string overall_status "Combined status: NORMAL, WARNING, CRITICAL"
        text reason "Clinical explanation of detection"
        float inference_latency_ms "Execution latency of ML pipeline"
        datetime created_at "Timestamp of inference"
    }

    ALERTS {
        int id PK "Autoincrement primary key"
        string patient_id FK "References PATIENTS"
        float timestamp "Trigger epoch timestamp"
        string severity "CRITICAL, WARNING, or INFO"
        string title "Concise alert headline"
        text message "Clinical summary and vital values"
        boolean acknowledged "Triage status flag"
        string acknowledged_by "Clinician name / ID"
        datetime acknowledged_at "Clinician timestamp"
        datetime created_at "Alert generation timestamp"
    }

    FLOW_EVENTS {
        int id PK "Autoincrement primary key"
        string patient_id "Associated patient ID (nullable)"
        string rule_name "OpenFlow rule descriptor"
        string match_ip "Target IP address matching packet"
        int match_port "Destination L4 port (e.g., 1883)"
        int queue_id "OVS HTB Queue ID (0=BestEffort, 1=Priority)"
        int priority "OpenFlow priority level (e.g., 32768)"
        string action "INSTALL, REMOVE, or TIMEOUT"
        text reason "Triggering medical alert or normalization"
        float flow_setup_time_ms "Round-trip flow installation latency"
        float installed_at "Epoch timestamp of rule activation"
        datetime created_at "Log record timestamp"
    }

    NETWORK_METRICS {
        int id PK "Autoincrement primary key"
        float timestamp "Measurement epoch timestamp"
        string source_host "Source node (e.g., sensor)"
        string target_host "Destination node (e.g., gateway)"
        float latency_ms "End-to-end ping RTT in ms"
        float throughput_mbps "Bandwidth throughput in Mbps"
        float packet_loss_pct "Packet drop percentage (%)"
        boolean priority_on "SDN high-priority queue active"
        datetime created_at "Metric ingestion timestamp"
    }
```

## Indexing Strategy for High Concurrency
1. **Time-Range Lookups:** Composite indexes `(patient_id, timestamp)` on `vitals`, `predictions`, and `alerts` ensure $O(\log N)$ historical queries.
2. **Alert Management:** Index `(acknowledged, severity)` powers real-time triage queries without full table scans.
3. **SDN Performance Benchmarks:** Index `(timestamp, priority_on)` provides immediate slicing between baseline and prioritized states.
