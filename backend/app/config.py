import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable fallbacks."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    # Security & CORS
    SECRET_KEY: str = "dev-insecure-secret-key-change-in-production"
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Database
    DATABASE_URL: str = "sqlite:///./evidenceguard.db"

    # Storage Paths (Outside public directories)
    STORAGE_BASE_DIR: str = "./storage"
    EVIDENCE_UPLOAD_DIR: str = "./storage/evidence"
    DERIVED_OUTPUT_DIR: str = "./storage/derived"
    REPORTS_DIR: str = "./storage/reports"

    # Upload Limits (Default 100 MB in bytes)
    MAX_UPLOAD_SIZE_BYTES: int = 104857600

    def ensure_storage_directories(self) -> None:
        """Ensure that required storage directories exist."""
        for path_str in [
            self.STORAGE_BASE_DIR,
            self.EVIDENCE_UPLOAD_DIR,
            self.DERIVED_OUTPUT_DIR,
            self.REPORTS_DIR,
        ]:
            path = Path(path_str)
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
