from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class IntegrityCheckBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    evidence_id: int
    recorded_hash: str
    recalculated_hash: str
    result: str  # Match, Mismatch, Not checked, Check failed
    notes: Optional[str] = None
    checked_at: datetime


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    evidence_number: str
    original_filename: str
    storage_filename: str
    detected_file_type: str
    mime_type: str
    file_size: int
    sha256_hash: str
    uploaded_at: datetime
    metadata_json: Optional[str] = None
    latest_integrity_status: Optional[str] = "Not checked"


class EvidenceDetailResponse(EvidenceResponse):
    model_config = ConfigDict(from_attributes=True)
    case_number: str
    case_title: str
    integrity_checks: List[IntegrityCheckBrief] = []


class IntegrityVerifyResult(BaseModel):
    evidence_id: int
    evidence_number: str
    original_filename: str
    recorded_hash: str
    recalculated_hash: str
    status: str  # Match, Mismatch, Check failed
    is_match: bool
    notes: str
    checked_at: datetime


class BatchVerifyItem(BaseModel):
    evidence_id: int
    evidence_number: str
    original_filename: str
    recorded_hash: str
    recalculated_hash: str
    status: str
    is_match: bool


class BatchVerifyResponse(BaseModel):
    case_id: int
    case_number: str
    total_checked: int
    match_count: int
    mismatch_count: int
    failed_count: int
    results: List[BatchVerifyItem]
