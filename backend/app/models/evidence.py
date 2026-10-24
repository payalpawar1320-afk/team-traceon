from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from app.database import Base


class Evidence(Base):
    """Digital Evidence Item model."""
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_number = Column(String(64), unique=True, index=True, nullable=False)
    
    original_filename = Column(String(255), nullable=False)
    storage_filename = Column(String(255), unique=True, nullable=False)
    storage_path = Column(String(512), nullable=False)  # Internal path, never exposed publicly
    
    detected_file_type = Column(String(32), nullable=False)  # image, video, audio, document, unknown
    mime_type = Column(String(128), nullable=False)
    file_size = Column(BigInteger, nullable=False)  # in bytes
    sha256_hash = Column(String(64), nullable=False, index=True)
    
    metadata_json = Column(Text, nullable=True)  # Structured extracted metadata in JSON
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="evidence_items")
    integrity_checks = relationship("IntegrityCheck", back_populates="evidence", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="evidence", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="evidence")
