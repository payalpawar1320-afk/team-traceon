from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ForensicFinding(BaseModel):
    severity: str = Field(..., description="Severity level: high, medium, low, info")
    category: str = Field(..., description="Finding category: e.g. Timestamp, Software, Hardware, Compression, Frame Continuity")
    title: str = Field(..., description="Short summary title of the finding")
    description: str = Field(..., description="Detailed, explainable forensic reasoning")


class GPSData(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float] = None


class ImageMetadataReport(BaseModel):
    format: str
    width: int
    height: int
    color_mode: str
    has_exif: bool
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software: Optional[str] = None
    capture_date: Optional[str] = None
    digitized_date: Optional[str] = None
    modification_date: Optional[str] = None
    gps: Optional[GPSData] = None
    raw_exif: Dict[str, str] = {}
    findings: List[ForensicFinding] = []
    indicators_count: int = 0


class ELAReport(BaseModel):
    status: str
    ela_filename: Optional[str] = None
    ela_url: Optional[str] = None
    quality_factor: int
    amplification_scale: int
    mean_error: float
    max_error: int
    variance: float
    indicator_detected: bool
    findings: List[ForensicFinding] = []
    limitations: str


class ImageForensicAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: int
    evidence_id: int
    case_id: int
    analysis_type: str = "image_forensics"
    status: str
    metadata_report: ImageMetadataReport
    ela_report: ELAReport
    total_indicators: int
    limitations: str
    created_at: datetime


# --- Video Forensic Schemas (FR-06) ---


class VideoFrameSample(BaseModel):
    frame_index: int
    timestamp_sec: float
    thumbnail_filename: str
    thumbnail_url: str
    is_duplicate: bool = False
    duplicate_of_index: Optional[int] = None


class DuplicateFrameGroup(BaseModel):
    primary_frame_index: int
    duplicate_frame_indices: List[int]
    timestamps_sec: List[float]
    is_consecutive: bool


class VideoForensicReport(BaseModel):
    status: str
    duration_sec: float
    width: int
    height: int
    fps: float
    total_frames: int
    codec: str
    sampled_frames_count: int
    duplicate_frames_count: int
    duplicate_percentage: float
    is_frozen_detected: bool
    sampled_frames: List[VideoFrameSample] = []
    duplicate_groups: List[DuplicateFrameGroup] = []
    findings: List[ForensicFinding] = []
    limitations: str


class VideoForensicAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: int
    evidence_id: int
    case_id: int
    analysis_type: str = "video_forensics"
    status: str
    video_report: VideoForensicReport
    total_indicators: int
    limitations: str
    created_at: datetime


# --- Audio Forensic Schemas (FR-07) ---


class WaveformSamplePoint(BaseModel):
    time_sec: float
    min_amplitude: float
    max_amplitude: float


class AudioMetadataReport(BaseModel):
    status: str
    format: str
    duration_sec: float
    sample_rate_hz: int
    channels: int
    channel_mode: str
    bit_depth: int
    bitrate_kbps: Optional[int] = None
    software_signature: Optional[str] = None
    id3_tags: Dict[str, str] = {}
    rms_dbfs: Optional[float] = None
    peak_amplitude: Optional[float] = None
    clipped_samples_count: int = 0
    is_clipped: bool = False
    silence_drop_count: int = 0
    waveform_peaks: List[WaveformSamplePoint] = []
    findings: List[ForensicFinding] = []
    limitations: str


class AudioForensicAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: int
    evidence_id: int
    case_id: int
    analysis_type: str = "audio_forensics"
    status: str
    audio_report: AudioMetadataReport
    total_indicators: int
    limitations: str
    created_at: datetime


class AnalysisResultBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    evidence_id: int
    analysis_type: str
    status: str
    created_at: datetime
    error_summary: Optional[str] = None

