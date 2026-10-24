from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ReportGenerateRequest(BaseModel):
    """Optional configuration parameters when requesting a forensic PDF report."""
    include_all_evidence: bool = Field(True, description="Whether to include all registered case evidence.")
    evidence_ids: Optional[List[int]] = Field(None, description="Specific subset of evidence IDs to report on (if not all).")
    include_audit_trail: bool = Field(True, description="Whether to include recent chain of custody audit events.")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional investigative remarks or conclusions.")


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    report_number: str
    report_filename: str
    report_status: str
    generated_at: datetime
    file_size_bytes: Optional[int] = None
    download_url: Optional[str] = None
