# Alert Detection Delay & SDN Closed-Loop Response Benchmark

Evaluation scoring of ground-truth anomaly onset versus ML inference detection and OpenFlow 1.3 flow installation.

| patient_id   | anomaly_type      |   ground_truth_start_s |   alert_detected_s |   detection_delay_s |   sdn_flow_setup_ms |   total_closed_loop_s |
|:-------------|:------------------|-----------------------:|-------------------:|--------------------:|--------------------:|----------------------:|
| P101         | TACHYCARDIA_FEVER |                     15 |                 16 |                   1 |                3.13 |                 1.003 |
| P102         | HYPOXEMIA         |                     20 |                 21 |                   1 |                3.93 |                 1.004 |
| P103         | ARRHYTHMIA_PVC    |                     12 |                 13 |                   1 |                4.75 |                 1.005 |

### Statistical Summary
- **Mean Detection Delay:** 1.00 seconds (governed by 2-window debounce filter for zero false alarms)
- **Mean SDN Flow-Setup Latency:** 3.94 ms
- **Mean Total Closed-Loop Reaction Time:** 1.00 seconds
