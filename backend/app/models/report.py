from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Report(Base):
    """Forensic PDF Report records."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    report_number = Column(String(64), unique=True, index=True, nullable=False)
    
    report_filename = Column(String(255), nullable=False)
    report_path = Column(String(512), nullable=False)  # Internal path, accessed via secure controller
    
    report_status = Column(String(32), default="generated", nullable=False)  # generated, archived
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="reports")
