from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: Optional[int] = None
    case_number: Optional[str] = None
    evidence_id: Optional[int] = None
    evidence_number: Optional[str] = None
    actor_id: str
    action: str
    result: str
    details: Optional[Dict[str, Any]] = None
    details_raw: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    events: list[AuditEventResponse]
