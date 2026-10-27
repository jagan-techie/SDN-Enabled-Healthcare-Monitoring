# db/retention.py - Time-based data retention and cleanup for high-frequency healthcare telemetry
import time
import logging
import argparse
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.session import get_db, engine
from db.models import VitalReading, Prediction, NetworkMetric, FlowEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [DBRetention] %(message)s")
logger = logging.getLogger("DBRetention")

def prune_old_records(retention_seconds: float = 86400 * 7):
    """Deletes high-frequency telemetry records older than retention_seconds."""
    cutoff_time = time.time() - retention_seconds
    logger.info(f"Running data retention cleanup for records older than cutoff {cutoff_time:.2f} ({retention_seconds/3600:.1f} hours)")

    with get_db() as db:
        vitals_deleted = db.query(VitalReading).filter(VitalReading.timestamp < cutoff_time).delete(synchronize_session=False)
        preds_deleted = db.query(Prediction).filter(Prediction.timestamp < cutoff_time).delete(synchronize_session=False)
        metrics_deleted = db.query(NetworkMetric).filter(NetworkMetric.timestamp < cutoff_time).delete(synchronize_session=False)
        flows_deleted = db.query(FlowEvent).filter(FlowEvent.installed_at < cutoff_time).delete(synchronize_session=False)

        logger.info(
            f"Retention cleanup complete: {vitals_deleted} vitals, {preds_deleted} predictions, "
            f"{metrics_deleted} metrics, {flows_deleted} flow events pruned."
        )

    # Checkpoint WAL log
    try:
        with engine.connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            logger.info("WAL checkpoint executed.")
    except Exception as e:
        logger.warning(f"WAL checkpoint note: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Healthcare Telemetry Data Retention Pruning")
    parser.add_argument("--days", type=float, default=7.0, help="Retention period in days (default 7)")
    parser.add_argument("--seconds", type=float, default=None, help="Retention period in seconds")
    args = parser.parse_args()

    ret_sec = args.seconds if args.seconds is not None else (args.days * 86400)
    prune_old_records(retention_seconds=ret_sec)
