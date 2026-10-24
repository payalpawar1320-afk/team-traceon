from typing import Dict
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(..., description="Overall system health status")
    app_name: str = Field(default="EvidenceGuard AI", description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Active runtime environment")
    timestamp: str = Field(..., description="UTC ISO timestamp of health check")
    database_connected: bool = Field(..., description="Database connectivity status")
    storage_verified: bool = Field(..., description="Integrity of local evidence storage paths")
    storage_details: Dict[str, bool] = Field(..., description="Status of individual storage directories")
