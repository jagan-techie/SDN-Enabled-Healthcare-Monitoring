# CardioSDN: Troubleshooting & Diagnostic Guide

This document catalogs common operational issues, error signatures, and their exact solutions.

---

## 1. Network & Port Conflicts

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`Address already in use: 1883`** | Another MQTT broker or previous instance is running. | Run `python scripts/stop_all.py` or kill the process using port 1883 (`netstat -ano \| findstr 1883` on Windows, `sudo fuser -k 1883/tcp` on Linux). |
| **`Address already in use: 5000`** | Previous Flask instance still running or AirPlay/service on port 5000. | Change `FLASK_PORT=5001` in `.env` or terminate the running process. |
| **`Address already in use: 8080`** | Previous Ryu controller or proxy service running on 8080. | Change `RYU_PORT=8081` in `.env` and update `RYU_REST_URL`. |

---

## 2. Machine Learning & Data Pipeline

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`FileNotFoundError: ecg_rf_model.joblib not found`** | The ML model has not been trained yet. | Run `python ml/train.py`. The script will train the model in ~0.2 seconds and serialize it to `ml/models/`. |
| **`FATAL DATA LEAKAGE Assertion Error`** | Patient IDs appeared in both train and test partitions. | Check `data/processed/dataset_metadata.json`. Train records (`DS1`) and test records (`DS2`) must be disjoint. Rerun `python data/download_datasets.py`. |
| **`PhysioNet HTTP 429 / Connection Timeout`** | Public PhysioNet bandwidth throttle or firewall restriction. | `data/download_datasets.py` automatically falls back to generating the synthetic clinical benchmark dataset. |

---

## 3. Database & SQLAlchemy

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`database is locked (SQLite)`** | Multiple high-frequency writes attempted without WAL mode. | Verify that `PRAGMA journal_mode=WAL` is active. `db/session.py` automatically executes WAL pragmas on connect. |
| **`DetachedInstanceError`** | Model instance attributes accessed in Jinja template after session close. | `db/session.py` sets `expire_on_commit=False` and `app.py` passes clean dictionary representations via `get_patient_dicts()`. |

---

## 4. Software-Defined Networking & Mininet

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`Cannot find a default OpenFlow controller`** | Ryu controller was not started before Mininet. | Start Ryu controller first (`ryu-manager controller/ryu_healthcare_controller.py`) before running `topology.py`. |
| **`ovs-vsctl: cannot find interface s1-eth3`** | Mininet topology was not started before running `setup_ovs_queues.sh`. | Ensure Mininet topology is active so virtual interfaces exist before applying Linux HTB QoS. |
| **`Eventlet / Greenlet ImportError on Python 3.10+`** | Ryu relies on eventlet internals incompatible with newer Python releases. | Run Ryu inside its own dedicated virtualenv pinned to Python 3.9 as detailed in `docs/WSL2_SETUP.md`. |
