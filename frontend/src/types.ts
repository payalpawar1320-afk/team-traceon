export type PageId =
  | 'dashboard'
  | 'create-case'
  | 'my-cases'
  | 'case-details'
  | 'evidence-upload'
  | 'evidence-details'
  | 'analysis-results'
  | 'integrity-check'
  | 'cross-check'
  | 'reports'
  | 'audit-log'
  | 'settings';

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
  database_connected: boolean;
  storage_verified: boolean;
  storage_details: Record<string, boolean>;
}

export interface CaseSummary {
  id: number;
  case_number: string;
  title: string;
  description?: string;
  status: 'active' | 'closed' | 'archived';
  investigator_name: string;
  created_at: string;
  updated_at: string;
  evidence_count: number;
  analysis_count: number;
}

export interface EvidenceItem {
  id: number;
  case_id: number;
  evidence_number: string;
  original_filename: string;
  storage_filename: string;
  detected_file_type: string;
  mime_type: string;
  file_size: number;
  sha256_hash: string;
  uploaded_at: string;
  metadata_json?: string;
  latest_integrity_status?: string;
}

export interface IntegrityCheckRecord {
  id: number;
  evidence_id: number;
  recorded_hash: string;
  recalculated_hash: string;
  result: string;
  notes?: string;
  checked_at: string;
}

export interface EvidenceDetail extends EvidenceItem {
  case_number: string;
  case_title: string;
  integrity_checks: IntegrityCheckRecord[];
}

export interface IntegrityVerifyResult {
  evidence_id: number;
  evidence_number: string;
  original_filename: string;
  recorded_hash: string;
  recalculated_hash: string;
  status: string;
  is_match: boolean;
  notes: string;
  checked_at: string;
}

export interface BatchVerifyItem {
  evidence_id: number;
  evidence_number: string;
  original_filename: string;
  recorded_hash: string;
  recalculated_hash: string;
  status: string;
  is_match: boolean;
}

export interface BatchVerifyResponse {
  case_id: number;
  case_number: string;
  total_checked: number;
  match_count: number;
  mismatch_count: number;
  failed_count: number;
  results: BatchVerifyItem[];
}

// --- Image Forensic Analysis Types (FR-05) ---

export interface ForensicFinding {
  severity: 'high' | 'medium' | 'low' | 'info';
  category: string;
  title: string;
  description: string;
}

export interface GPSData {
  latitude: number;
  longitude: number;
  altitude?: number | null;
}

export interface ImageMetadataReport {
  format: string;
  width: number;
  height: number;
  color_mode: string;
  has_exif: boolean;
  camera_make?: string | null;
  camera_model?: string | null;
  software?: string | null;
  capture_date?: string | null;
  digitized_date?: string | null;
  modification_date?: string | null;
  gps?: GPSData | null;
  raw_exif: Record<string, string>;
  findings: ForensicFinding[];
  indicators_count: number;
}

export interface ELAReport {
  status: string;
  ela_filename?: string | null;
  ela_url?: string | null;
  quality_factor: number;
  amplification_scale: number;
  mean_error: number;
  max_error: number;
  variance: number;
  indicator_detected: boolean;
  findings: ForensicFinding[];
  limitations: string;
}

export interface AIDetectionReport {
  status: string;
  model_name: string;
  model_version: string;
  prediction: string;
  is_ai_generated: boolean;
  confidence_score: number;
  probability_ai_pct: number;
  probability_real_pct: number;
  raw_logit: number;
  fft_anomaly_detected: boolean;
  fft_outer_center_ratio: number;
  indicator_detected: boolean;
  verdict: string;
  findings: ForensicFinding[];
  limitations: string;
}

export interface ImageForensicAnalysisResponse {
  analysis_id: number;
  evidence_id: number;
  case_id: number;
  analysis_type: string;
  status: string;
  metadata_report: ImageMetadataReport;
  ela_report: ELAReport;
  ai_detection_report?: AIDetectionReport | null;
  total_indicators: number;
  limitations: string;
  created_at: string;
}

// --- Video / CCTV Forensic Analysis Types (FR-06) ---

export interface VideoFrameSample {
  frame_index: number;
  timestamp_sec: number;
  thumbnail_filename: string;
  thumbnail_url: string;
  is_duplicate: boolean;
  duplicate_of_index?: number | null;
}

export interface DuplicateFrameGroup {
  primary_frame_index: number;
  duplicate_frame_indices: number[];
  timestamps_sec: number[];
  is_consecutive: boolean;
}

export interface VideoForensicReport {
  status: string;
  duration_sec: number;
  width: number;
  height: number;
  fps: number;
  total_frames: number;
  codec: string;
  sampled_frames_count: number;
  duplicate_frames_count: number;
  duplicate_percentage: number;
  is_frozen_detected: boolean;
  sampled_frames: VideoFrameSample[];
  duplicate_groups: DuplicateFrameGroup[];
  findings: ForensicFinding[];
  limitations: string;
}

export interface VideoForensicAnalysisResponse {
  analysis_id: number;
  evidence_id: number;
  case_id: number;
  analysis_type: string;
  status: string;
  video_report: VideoForensicReport;
  total_indicators: number;
  limitations: string;
  created_at: string;
}

// --- Audio Forensic Analysis Types (FR-07) ---

export interface WaveformSamplePoint {
  time_sec: number;
  min_amplitude: number;
  max_amplitude: number;
}

export interface AudioMetadataReport {
  status: string;
  format: string;
  duration_sec: number;
  sample_rate_hz: number;
  channels: number;
  channel_mode: string;
  bit_depth: number;
  bitrate_kbps?: number | null;
  software_signature?: string | null;
  id3_tags: Record<string, string>;
  rms_dbfs?: number | null;
  peak_amplitude?: number | null;
  clipped_samples_count: number;
  is_clipped: boolean;
  silence_drop_count: number;
  waveform_peaks: WaveformSamplePoint[];
  findings: ForensicFinding[];
  limitations: string;
}

export interface AudioForensicAnalysisResponse {
  analysis_id: number;
  evidence_id: number;
  case_id: number;
  analysis_type: string;
  status: string;
  audio_report: AudioMetadataReport;
  total_indicators: number;
  limitations: string;
  created_at: string;
}

export type AnyForensicAnalysisResponse =
  | ImageForensicAnalysisResponse
  | VideoForensicAnalysisResponse
  | AudioForensicAnalysisResponse;



export interface AuditEventItem {
  id: number;
  case_id?: number;
  evidence_id?: number;
  actor_id: string;
  action: string;
  result: 'success' | 'failure' | 'warning';
  created_at: string;
  ip_address?: string;
}

export interface CaseDetail extends CaseSummary {
  evidence_items: EvidenceItem[];
  audit_events: AuditEventItem[];
}

export interface CaseStats {
  total_cases: number;
  active_cases: number;
  closed_cases: number;
  archived_cases: number;
  total_evidence: number;
}

export interface CaseCreatePayload {
  case_number?: string;
  title: string;
  description?: string;
  investigator_name?: string;
  status?: 'active' | 'closed' | 'archived';
}

export interface CaseUpdatePayload {
  title?: string;
  description?: string;
  investigator_name?: string;
  status?: 'active' | 'closed' | 'archived';
}

// --- Cross-Evidence Consistency Analysis Types (FR-08) ---

export interface CrossEvidenceCompareRequest {
  evidence_ids: number[];
  time_tolerance_seconds?: number;
}

export interface CrossEvidenceItemSummary {
  evidence_id: number;
  evidence_number: string;
  original_filename: string;
  file_type: string;
  mime_type: string;
  file_size_bytes: number;
  sha256_hash: string;
  uploaded_at: string;
  capture_timestamp?: string | null;
  capture_timestamp_raw?: string | null;
  modification_timestamp?: string | null;
  device_make?: string | null;
  device_model?: string | null;
  device_label?: string | null;
  software_footprint?: string | null;
  dimensions?: string | null;
  duration_sec?: number | null;
  gps_latitude?: number | null;
  gps_longitude?: number | null;
  has_gps: boolean;
  has_exif: boolean;
}

export interface TimelineEvent {
  timestamp: string;
  timestamp_str: string;
  event_type: string;
  evidence_id: number;
  evidence_number: string;
  filename: string;
  description: string;
  is_estimated: boolean;
}

export interface FieldComparison {
  field_id: string;
  field_label: string;
  status: 'consistent' | 'inconsistent' | 'missing_data' | 'not_applicable';
  values_by_evidence: Record<string, any>;
  delta_or_diff?: string | null;
  finding_title: string;
  explanation: string;
  plausible_causes: string[];
}

export interface ComparisonSummary {
  total_fields_evaluated: number;
  consistent_count: number;
  inconsistent_count: number;
  missing_data_count: number;
  overall_status: 'consistent' | 'inconsistencies_detected' | 'insufficient_data';
  highest_severity: 'info' | 'low' | 'medium' | 'high';
}

export interface CrossEvidenceComparisonResponse {
  case_id: number;
  case_number: string;
  compared_evidence_ids: number[];
  evidence_summaries: CrossEvidenceItemSummary[];
  timeline: TimelineEvent[];
  comparison_matrix: FieldComparison[];
  summary: ComparisonSummary;
  limitations: string;
  compared_at: string;
}

// --- Forensic PDF Reports & Chain of Custody Audit Types (FR-10, §6) ---

export interface ReportItem {
  id: number;
  case_id: number;
  report_number: string;
  report_filename: string;
  report_status: string;
  generated_at: string;
  file_size_bytes?: number | null;
  download_url: string;
}

export interface ReportGeneratePayload {
  include_all_evidence?: boolean;
  evidence_ids?: number[];
  include_audit_trail?: boolean;
  notes?: string;
}

export interface AuditEventDetail {
  id: number;
  case_id?: number | null;
  case_number?: string | null;
  evidence_id?: number | null;
  evidence_number?: string | null;
  actor_id: string;
  action: string;
  result: 'success' | 'failure' | 'warning';
  details?: Record<string, any> | null;
  details_raw?: string | null;
  ip_address?: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  total_count: number;
  limit: number;
  offset: number;
  events: AuditEventDetail[];
}


