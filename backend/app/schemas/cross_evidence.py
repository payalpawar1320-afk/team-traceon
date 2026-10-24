from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class CrossEvidenceCompareRequest(BaseModel):
    """Request payload for comparing multiple evidence items in a case."""
    evidence_ids: List[int] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="List of at least 2 and at most 10 evidence IDs to cross-examine.",
    )
    time_tolerance_seconds: int = Field(
        default=60,
        ge=0,
        le=86400,
        description="Allowed difference (in seconds) before flagging timestamp divergence as inconsistent.",
    )


class CrossEvidenceItemSummary(BaseModel):
    """Normalized forensic metadata extracted from an evidence item for comparison."""
    evidence_id: int
    evidence_number: str
    original_filename: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    uploaded_at: datetime
    
    # Forensic attributes
    capture_timestamp: Optional[datetime] = None
    capture_timestamp_raw: Optional[str] = None
    modification_timestamp: Optional[datetime] = None
    device_make: Optional[str] = None
    device_model: Optional[str] = None
    device_label: Optional[str] = None
    software_footprint: Optional[str] = None
    dimensions: Optional[str] = None
    duration_sec: Optional[float] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    has_gps: bool = False
    has_exif: bool = False


class TimelineEvent(BaseModel):
    """A chronologically ordered event across the compared evidence items."""
    timestamp: datetime
    timestamp_str: str
    event_type: str  # e.g., "Capture / Creation", "File Modification", "Ingestion / Upload"
    evidence_id: int
    evidence_number: str
    filename: str
    description: str
    is_estimated: bool = False


class FieldComparison(BaseModel):
    """Comparison evaluation for a specific forensic dimension."""
    field_id: str
    field_label: str
    status: str  # "consistent", "inconsistent", "missing_data", "not_applicable"
    values_by_evidence: Dict[str, Any]  # Key: evidence_number or evidence_id as str
    delta_or_diff: Optional[str] = None
    finding_title: str
    explanation: str
    plausible_causes: List[str] = []


class ComparisonSummary(BaseModel):
    total_fields_evaluated: int
    consistent_count: int
    inconsistent_count: int
    missing_data_count: int
    overall_status: str  # "consistent", "inconsistencies_detected", "insufficient_data"
    highest_severity: str  # "info", "low", "medium", "high"


class CrossEvidenceComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    case_id: int
    case_number: str
    compared_evidence_ids: List[int]
    evidence_summaries: List[CrossEvidenceItemSummary]
    timeline: List[TimelineEvent]
    comparison_matrix: List[FieldComparison]
    summary: ComparisonSummary
    limitations: str
    compared_at: datetime
