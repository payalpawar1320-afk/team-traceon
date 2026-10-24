from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class IntegrityCheck(Base):
    """SHA-256 Byte Integrity Verification History model."""
    __tablename__ = "integrity_checks"

    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    
    recorded_hash = Column(String(64), nullable=False)
    recalculated_hash = Column(String(64), nullable=False)
    result = Column(String(32), nullable=False)  # Match, Mismatch, Not checked, Check failed
    notes = Column(Text, nullable=True)
    
    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    evidence = relationship("Evidence", back_populates="integrity_checks")
