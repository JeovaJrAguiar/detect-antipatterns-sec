from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Double, ForeignKey, Index, Integer, String, event
from sqlalchemy.schema import DDL
from observa.database.database import Base
from sqlalchemy.dialects.postgresql import JSONB 
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'operator', 'executor')",
            name="ck_users_role",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SecurityAuditLogModel(Base):
    __tablename__ = "security_audit_log"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success', 'failure')",
            name="ck_security_audit_log_outcome",
        ),
        Index("ix_security_audit_log_occurred_at", "occurred_at"),
        Index("ix_security_audit_log_actor_user_id", "actor_user_id"),
    )

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(255), nullable=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    outcome = Column(String(16), nullable=False)
    client_ip = Column(String(45), nullable=True)
    request_id = Column(String(36), nullable=True)


event.listen(
    SecurityAuditLogModel.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER security_audit_log_reject_update
        BEFORE UPDATE ON security_audit_log
        BEGIN
            SELECT RAISE(ABORT, 'security audit log is append-only');
        END
        """
    ).execute_if(dialect="sqlite"),
)
event.listen(
    SecurityAuditLogModel.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER security_audit_log_reject_delete
        BEFORE DELETE ON security_audit_log
        BEGIN
            SELECT RAISE(ABORT, 'security audit log is append-only');
        END
        """
    ).execute_if(dialect="sqlite"),
)


class SourceModel(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    json_data = Column(JSONB, nullable=True)  # conteúdo do arquivo JSON
    api_url = Column(String, nullable=True)     # se for remoto
    
    history_items = relationship(
        "HistoryModel",
        back_populates="source",
        passive_deletes=True
    )

class DetectorModel(Base):
    __tablename__ = "detectors"

    id = Column(Integer, primary_key=True, index=True)
    name_ap = Column(String, nullable=False)
    name = Column(String, unique=True, nullable=False)
    class_path = Column(String, nullable=True)  # ex: "observa.detectors.excessive_alerts.ExcessiveAlertsDetector"
    api_url = Column(String, nullable=True)     # se for remoto
    
    history_items = relationship(
        "HistoryModel",
        back_populates="detector",
        passive_deletes=True
    )

class HistoryModel(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    detector_id = Column(Integer, ForeignKey("detectors.id", ondelete="CASCADE"), nullable=False)
    detected = Column(Integer, nullable=False)  
    total = Column(Integer, nullable=False)  
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    execution_time = Column(Double, nullable=False)  
    result = Column(JSONB, nullable=True)     
    
    source = relationship("SourceModel", back_populates="history_items")
    detector = relationship("DetectorModel", back_populates="history_items")