from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utc_now():
    return datetime.now(timezone.utc)

class Patient(Base):
    __tablename__ = "patients"

    patient_id = Column(String(32), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    room = Column(String(50), nullable=False)
    ip_address = Column(String(45), nullable=False, index=True)
    mac_address = Column(String(20), nullable=True)
    status = Column(String(20), default="NORMAL", index=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    vitals = relationship("VitalReading", back_populates="patient", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="patient", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="patient", cascade="all, delete-orphan")

class VitalReading(Base):
    __tablename__ = "vitals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(32), ForeignKey("patients.patient_id"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    hr = Column(Float, nullable=False)
    spo2 = Column(Float, nullable=False)
    temp = Column(Float, nullable=False)
    leads_off = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    patient = relationship("Patient", back_populates="vitals")

    __table_args__ = (
        Index("ix_vitals_patient_timestamp", "patient_id", "timestamp"),
    )

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(32), ForeignKey("patients.patient_id"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    ecg_classification = Column(String(20), nullable=False)
    ecg_confidence = Column(Float, nullable=False)
    vitals_status = Column(String(20), nullable=False)
    overall_status = Column(String(20), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    inference_latency_ms = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    patient = relationship("Patient", back_populates="predictions")

    __table_args__ = (
        Index("ix_predictions_patient_timestamp", "patient_id", "timestamp"),
    )

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(32), ForeignKey("patients.patient_id"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    acknowledged = Column(Boolean, default=False, nullable=False, index=True)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    patient = relationship("Patient", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_patient_timestamp", "patient_id", "timestamp"),
        Index("ix_alerts_ack_status", "acknowledged", "severity"),
    )

class FlowEvent(Base):
    __tablename__ = "flow_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(32), nullable=True, index=True)
    rule_name = Column(String(100), nullable=False)
    match_ip = Column(String(45), nullable=False)
    match_port = Column(Integer, nullable=True)
    queue_id = Column(Integer, nullable=False)
    priority = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # "INSTALL", "REMOVE", "TIMEOUT"
    reason = Column(Text, nullable=False)
    flow_setup_time_ms = Column(Float, nullable=True)
    installed_at = Column(Float, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_flow_patient_installed", "patient_id", "installed_at"),
    )

class NetworkMetric(Base):
    __tablename__ = "network_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, nullable=False, index=True)
    source_host = Column(String(50), nullable=False)
    target_host = Column(String(50), nullable=False)
    latency_ms = Column(Float, nullable=False)
    throughput_mbps = Column(Float, nullable=False)
    packet_loss_pct = Column(Float, nullable=False)
    priority_on = Column(Boolean, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_metrics_timestamp_prio", "timestamp", "priority_on"),
    )
