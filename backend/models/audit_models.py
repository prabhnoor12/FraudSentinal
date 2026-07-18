from datetime import datetime, timedelta
from sqlalchemy import Column, DateTime, Integer, String, JSON, ForeignKey, Index
from database import Base

class AuditLog(Base):
    """Immutable audit log for compliance and security traceability."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    event_type = Column(String(50), nullable=False, index=True)  # e.g., 'rule_change', 'case_action'
    action = Column(String(50), nullable=False)  # e.g., 'create', 'update', 'resolve'
    resource_type = Column(String(50), nullable=True)  # e.g., 'fraud_rule', 'review_case'
    resource_id = Column(String(50), nullable=True)
    
    # Payload details
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    details = Column(JSON, nullable=True)
    
    # Client Info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Indexes for multi-condition query
    __table_args__ = (
        Index("idx_audit_lookup", "organisation_id", "event_type", "created_at"),
    )

    @property
    def is_expired(self) -> bool:
        """Check if the log has exceeded the retention period (default 180 days)."""
        retention_days = 180 # Could be configurable
        return datetime.utcnow() > self.created_at + timedelta(days=retention_days)
