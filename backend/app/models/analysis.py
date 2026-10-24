from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AnalysisResult(Base):
    """Forensic Analysis Result model."""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    
    analysis_type = Column(String(64), nullable=False)  # metadata, ela, video_frames, audio_spectrum, cross_check
    status = Column(String(64), nullable=False)  # Indicator detected, No indicator detected by this check, etc.
    
    findings_json = Column(Text, nullable=True)  # Structured forensic findings
    limitations = Column(Text, nullable=True)  # Explainable limitations of check
    error_summary = Column(Text, nullable=True)  # In case of failure
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="analysis_results")
    evidence = relationship("Evidence", back_populates="analysis_results")
