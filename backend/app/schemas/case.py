from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
import re


class CaseBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Investigation case title")
    description: Optional[str] = Field(None, max_length=4000, description="Incident or case summary")
    investigator_name: str = Field("Lead Investigator", min_length=2, max_length=128, description="Assigned investigating officer")
    status: str = Field("active", description="Case status: active, closed, archived")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = {"active", "closed", "archived"}
        cleaned = v.strip().lower()
        if cleaned not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return cleaned


class CaseCreate(CaseBase):
    case_number: Optional[str] = Field(
        None,
        max_length=64,
        description="Unique police case identifier (e.g., CASE-2026-0001). Auto-generated if omitted."
    )

    @field_validator("case_number")
    @classmethod
    def validate_case_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        cleaned = v.strip().upper()
        if not re.match(r"^[A-Z0-9_\-\/]{3,64}$", cleaned):
            raise ValueError("Case number must be 3-64 characters containing only alphanumeric, hyphen, underscore, or slash.")
        return cleaned


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    investigator_name: Optional[str] = Field(None, min_length=2, max_length=128)
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        valid_statuses = {"active", "closed", "archived"}
        cleaned = v.strip().lower()
        if cleaned not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return cleaned


class EvidenceBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_filename: str
    detected_file_type: str
    file_size: int
    sha256_hash: str
    uploaded_at: datetime
    is_duplicate: bool = False
    duplicate_warning: Optional[str] = None
    duplicate_of_evidence_number: Optional[str] = None


class AuditEventBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: str
    action: str
    result: str
    created_at: datetime
    ip_address: Optional[str] = None


class CaseResponse(CaseBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_number: str
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0
    analysis_count: int = 0


class CaseDetailResponse(CaseResponse):
    model_config = ConfigDict(from_attributes=True)
    evidence_items: List[EvidenceBrief] = []
    audit_events: List[AuditEventBrief] = []


class CaseStatsResponse(BaseModel):
    total_cases: int
    active_cases: int
    closed_cases: int
    archived_cases: int
    total_evidence: int
