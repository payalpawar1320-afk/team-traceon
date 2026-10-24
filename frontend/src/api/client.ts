import type {
  HealthResponse,
  CaseSummary,
  CaseDetail,
  CaseStats,
  CaseCreatePayload,
  CaseUpdatePayload,
  EvidenceItem,
  EvidenceDetail,
  IntegrityVerifyResult,
  BatchVerifyResponse,
  ImageForensicAnalysisResponse,
  VideoForensicAnalysisResponse,
  AudioForensicAnalysisResponse,
  AnyForensicAnalysisResponse,
  CrossEvidenceCompareRequest,
  CrossEvidenceComparisonResponse,
  ReportItem,
  ReportGeneratePayload,
  AuditLogListResponse,
} from '../types';



export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/health');
  if (!response.ok) {
    try {
      const errorData = await response.json();
      return errorData as HealthResponse;
    } catch {
      throw new Error(`Health check request failed with HTTP status ${response.status}`);
    }
  }
  return response.json();
}

export async function fetchCaseStats(): Promise<CaseStats> {
  const response = await fetch('/api/cases/stats');
  if (!response.ok) {
    throw new Error(`Failed to load case statistics: HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchCases(search?: string, status?: string): Promise<CaseSummary[]> {
  const params = new URLSearchParams();
  if (search && search.trim()) {
    params.set('search', search.trim());
  }
  if (status && status.trim() && status !== 'all') {
    params.set('status', status.trim());
  }

  const query = params.toString();
  const url = query ? `/api/cases?${query}` : '/api/cases';
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch cases: HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchCaseById(identifier: string | number): Promise<CaseDetail> {
  const response = await fetch(`/api/cases/${identifier}`);
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Case not found (HTTP ${response.status})`);
  }
  return response.json();
}

export async function createCase(payload: CaseCreatePayload): Promise<CaseSummary> {
  const response = await fetch('/api/cases', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    let msg = errorBody.detail;
    if (Array.isArray(msg)) {
      msg = msg.map((e: { msg?: string }) => e.msg || 'Validation error').join(', ');
    }
    throw new Error(msg || `Failed to create case: HTTP ${response.status}`);
  }
  return response.json();
}

export async function updateCase(
  caseId: number,
  payload: CaseUpdatePayload
): Promise<CaseSummary> {
  const response = await fetch(`/api/cases/${caseId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Failed to update case: HTTP ${response.status}`);
  }
  return response.json();
}

// --- Digital Evidence APIs ---

export async function uploadEvidence(
  caseId: number,
  file: File,
  investigatorName?: string
): Promise<EvidenceItem> {
  const formData = new FormData();
  formData.append('file', file);
  if (investigatorName && investigatorName.trim()) {
    formData.append('investigator_name', investigatorName.trim());
  }

  const response = await fetch(`/api/cases/${caseId}/evidence`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Evidence ingestion failed: HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchCaseEvidence(caseId: number): Promise<EvidenceItem[]> {
  const response = await fetch(`/api/cases/${caseId}/evidence`);
  if (!response.ok) {
    throw new Error(`Failed to load case evidence items: HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchAllEvidence(params?: {
  search?: string;
  fileType?: string;
  caseId?: number;
}): Promise<EvidenceItem[]> {
  const q = new URLSearchParams();
  if (params?.search && params.search.trim()) {
    q.set('search', params.search.trim());
  }
  if (params?.fileType && params.fileType.trim() && params.fileType !== 'all') {
    q.set('detected_file_type', params.fileType.trim());
  }
  if (params?.caseId) {
    q.set('case_id', params.caseId.toString());
  }

  const queryString = q.toString();
  const url = queryString ? `/api/evidence?${queryString}` : '/api/evidence';
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load evidence directory: HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchEvidenceById(evidenceId: number): Promise<EvidenceDetail> {
  const response = await fetch(`/api/evidence/${evidenceId}`);
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Evidence item not found: HTTP ${response.status}`);
  }
  return response.json();
}

export function getEvidenceDownloadUrl(evidenceId: number): string {
  return `/api/evidence/${evidenceId}/download`;
}

// --- SHA-256 Integrity Verification APIs ---

export async function verifyEvidenceIntegrity(
  evidenceId: number,
  notes?: string
): Promise<IntegrityVerifyResult> {
  const query = notes ? `?notes=${encodeURIComponent(notes)}` : '';
  const response = await fetch(`/api/evidence/${evidenceId}/verify${query}`, {
    method: 'POST',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Integrity verification failed: HTTP ${response.status}`);
  }
  return response.json();
}

export async function verifyAllCaseEvidence(caseId: number): Promise<BatchVerifyResponse> {
  const response = await fetch(`/api/cases/${caseId}/verify-all`, {
    method: 'POST',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Batch case verification failed: HTTP ${response.status}`);
  }
  return response.json();
}

// --- Image Forensic Analysis APIs (FR-05) ---

export async function runImageAnalysis(
  evidenceId: number,
  options?: { quality?: number; scale?: number }
): Promise<ImageForensicAnalysisResponse> {
  const params = new URLSearchParams();
  if (options?.quality) params.set('quality', options.quality.toString());
  if (options?.scale) params.set('scale', options.scale.toString());

  const q = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`/api/evidence/${evidenceId}/analyze/image${q}`, {
    method: 'POST',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Image analysis failed: HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchEvidenceAnalyses(
  evidenceId: number
): Promise<AnyForensicAnalysisResponse[]> {
  const response = await fetch(`/api/evidence/${evidenceId}/analysis`);
  if (!response.ok) {
    throw new Error(`Failed to load evidence analysis history: HTTP ${response.status}`);
  }
  return response.json();
}

export async function runVideoAnalysis(
  evidenceId: number,
  options?: { targetSampleFrames?: number }
): Promise<VideoForensicAnalysisResponse> {
  const params = new URLSearchParams();
  if (options?.targetSampleFrames) {
    params.set('target_sample_frames', options.targetSampleFrames.toString());
  }

  const q = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`/api/evidence/${evidenceId}/analyze/video${q}`, {
    method: 'POST',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Video analysis failed: HTTP ${response.status}`);
  }
  return response.json();
}

export async function runAudioAnalysis(
  evidenceId: number,
  options?: { targetWaveformPoints?: number }
): Promise<AudioForensicAnalysisResponse> {
  const params = new URLSearchParams();
  if (options?.targetWaveformPoints) {
    params.set('target_waveform_points', options.targetWaveformPoints.toString());
  }

  const q = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`/api/evidence/${evidenceId}/analyze/audio${q}`, {
    method: 'POST',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Audio analysis failed: HTTP ${response.status}`);
  }
  return response.json();
}

export function getDerivedAssetUrl(filename: string): string {
  return `/api/analysis/derived/${encodeURIComponent(filename)}`;
}

export async function compareCrossEvidence(
  caseId: number | string,
  payload: CrossEvidenceCompareRequest
): Promise<CrossEvidenceComparisonResponse> {
  const response = await fetch(`/api/cases/${caseId}/compare-evidence`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Cross-evidence comparison failed: HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchCaseReports(caseId: number | string): Promise<ReportItem[]> {
  const response = await fetch(`/api/cases/${caseId}/reports`);
  if (!response.ok) {
    throw new Error(`Failed to load case reports: HTTP ${response.status}`);
  }
  return response.json();
}

export async function generateCaseReport(
  caseId: number | string,
  payload: ReportGeneratePayload
): Promise<ReportItem> {
  const response = await fetch(`/api/cases/${caseId}/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `Forensic report generation failed: HTTP ${response.status}`);
  }
  return response.json();
}

export function getReportDownloadUrl(reportId: number): string {
  return `/api/reports/${reportId}/download`;
}

export async function fetchAuditLog(params?: {
  caseId?: number | string;
  evidenceId?: number;
  action?: string;
  result?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditLogListResponse> {
  const q = new URLSearchParams();
  if (params?.caseId && params.caseId !== 'all') {
    q.set('case_id', params.caseId.toString());
  }
  if (params?.evidenceId) {
    q.set('evidence_id', params.evidenceId.toString());
  }
  if (params?.action && params.action !== 'all') {
    q.set('action', params.action);
  }
  if (params?.result && params.result !== 'all') {
    q.set('result', params.result);
  }
  if (params?.search && params.search.trim()) {
    q.set('search', params.search.trim());
  }
  if (params?.limit) {
    q.set('limit', params.limit.toString());
  }
  if (params?.offset) {
    q.set('offset', params.offset.toString());
  }

  const queryStr = q.toString() ? `?${q.toString()}` : '';
  const response = await fetch(`/api/audit-log${queryStr}`);
  if (!response.ok) {
    throw new Error(`Failed to load audit log: HTTP ${response.status}`);
  }
  return response.json();
}





