from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AuditEvent(Base):
    """Forensic Platform Audit Event model."""
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True, index=True)
    
    actor_id = Column(String(128), default="system_investigator", nullable=False)
    action = Column(String(128), nullable=False)  # e.g., CASE_CREATE, EVIDENCE_UPLOAD, HASH_VERIFY
    result = Column(String(32), default="success", nullable=False)  # success, failure, warning
    
    details_json = Column(Text, nullable=True)  # Minimal non-sensitive action parameters
    ip_address = Column(String(64), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    case = relationship("Case", back_populates="audit_events")
    evidence = relationship("Evidence", back_populates="audit_events")
