import React, { useState, useEffect, useCallback } from 'react';
import type { PageId, EvidenceDetail, IntegrityVerifyResult } from '../types';
import {
  fetchEvidenceById,
  verifyEvidenceIntegrity,
  getEvidenceDownloadUrl,
} from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import {
  ArrowLeft,
  ShieldCheck,
  AlertTriangle,
  HardDrive,
  Clock,
  Folder,
  FileText,
  Download,
  Copy,
  Check,
  RefreshCw,
  FileImage,
  FileVideo,
  FileAudio,
  ShieldAlert,
  Info,
  FileSearch,
} from 'lucide-react';


interface EvidenceDetailPageProps {
  evidenceId: number | null;
  onNavigate: (page: PageId, caseIdentifier?: string | number, evidenceId?: number) => void;
}

export const EvidenceDetailPage: React.FC<EvidenceDetailPageProps> = ({
  evidenceId,
  onNavigate,
}) => {
  const [evidence, setEvidence] = useState<EvidenceDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState<boolean>(false);
  const [verifyResult, setVerifyResult] = useState<IntegrityVerifyResult | null>(null);
  const [copiedHash, setCopiedHash] = useState<boolean>(false);

  const loadEvidence = useCallback(async () => {
    if (!evidenceId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEvidenceById(evidenceId);
      setEvidence(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to retrieve evidence dossier.');
    } finally {
      setLoading(false);
    }
  }, [evidenceId]);

  useEffect(() => {
    loadEvidence();
  }, [loadEvidence]);

  const handleVerify = async () => {
    if (!evidence) return;
    setVerifying(true);
    try {
      const res = await verifyEvidenceIntegrity(evidence.id);
      setVerifyResult(res);
      // Refresh check history
      await loadEvidence();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Integrity verification failed.');
    } finally {
      setVerifying(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const formatDate = (isoStr: string) => {
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  if (!evidenceId) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
        <HardDrive size={40} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
        <h2 style={{ fontSize: '18px', fontWeight: 600 }}>No Evidence Item Selected</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '8px 0 16px' }}>
          Please select an evidence file from a case or the integrity dashboard to inspect its dossier.
        </p>
        <button className="btn btn-primary" onClick={() => onNavigate('my-cases')}>
          <ArrowLeft size={14} /> Go to Cases
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
        <RefreshCw size={24} className="spin" style={{ color: 'var(--primary-blue)', marginBottom: '12px' }} />
        <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Loading forensic evidence dossier...</p>
      </div>
    );
  }

  if (error || !evidence) {
    return (
      <div className="card" style={{ padding: '32px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#dc2626', marginBottom: '12px' }}>
          <AlertTriangle size={20} />
          <h2 style={{ fontSize: '16px', fontWeight: 600 }}>Error Loading Evidence</h2>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '16px' }}>{error}</p>
        <button className="btn btn-secondary" onClick={() => onNavigate('my-cases')}>
          <ArrowLeft size={14} /> Return to Cases
        </button>
      </div>
    );
  }

  const downloadUrl = getEvidenceDownloadUrl(evidence.id);

  return (
    <div>
      {/* Page Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '4px 8px', fontSize: '12px', marginBottom: '8px' }}
            onClick={() => onNavigate('case-details', evidence.case_id)}
          >
            <ArrowLeft size={12} />
            <span>Back to Case {evidence.case_number}</span>
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 className="page-title" style={{ margin: 0 }}>
              {evidence.evidence_number}
            </h1>
            <span className="badge badge-neutral">{evidence.detected_file_type.toUpperCase()}</span>
            <StatusBadge
              status={
                evidence.latest_integrity_status === 'Match'
                  ? 'INTEGRITY VERIFIED'
                  : evidence.latest_integrity_status === 'Mismatch'
                  ? 'TAMPER DETECTED'
                  : 'NOT CHECKED'
              }
              variant={
                evidence.latest_integrity_status === 'Match'
                  ? 'success'
                  : evidence.latest_integrity_status === 'Mismatch'
                  ? 'danger'
                  : 'neutral'
              }
            />
          </div>
          <p className="page-subtitle" style={{ marginTop: '4px' }}>
            Original File: <strong>{evidence.original_filename}</strong> — Associated with Case {evidence.case_number} ({evidence.case_title})
          </p>
          {evidence.is_duplicate && (
            <div
              style={{
                marginTop: '10px',
                padding: '10px 14px',
                background: '#fffbeb',
                border: '1px solid #fef3c7',
                borderRadius: '4px',
                color: '#92400e',
                fontSize: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <AlertTriangle size={15} color="#d97706" />
              <span>
                <strong>Duplicate File Warning:</strong> {evidence.duplicate_warning || 'Identical SHA-256 hash matches another evidence file in this case. Both records are preserved in chain of custody.'}
              </span>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          {evidence.detected_file_type === 'image' && (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: '12px' }}
              onClick={() => onNavigate('analysis-results', evidence.case_id, evidence.id)}
            >
              <FileSearch size={13} />
              <span>Image Forensics & ELA</span>
            </button>
          )}
          {evidence.detected_file_type === 'video' && (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: '12px' }}
              onClick={() => onNavigate('analysis-results', evidence.case_id, evidence.id)}
            >
              <FileSearch size={13} />
              <span>CCTV & Frame Analysis</span>
            </button>
          )}
          {evidence.detected_file_type === 'audio' && (
            <button
              type="button"
              className="btn btn-secondary"
              style={{ fontSize: '12px' }}
              onClick={() => onNavigate('analysis-results', evidence.case_id, evidence.id)}
            >
              <FileSearch size={13} />
              <span>Audio & Signal Forensics</span>
            </button>
          )}

          <a
            href={downloadUrl}
            download={evidence.original_filename}
            className="btn btn-secondary"
            style={{ fontSize: '12px' }}
          >
            <Download size={13} />
            <span>Export Original Bytes</span>
          </a>
          <button
            type="button"
            className="btn btn-primary"
            style={{ fontSize: '12px' }}
            onClick={handleVerify}
            disabled={verifying}
          >
            <RefreshCw size={13} className={verifying ? 'spin' : ''} />
            <span>{verifying ? 'Recalculating SHA-256...' : 'Recalculate & Verify SHA-256'}</span>
          </button>
        </div>

      </div>

      {/* Verification Result Alert Banner */}
      {verifyResult && (
        <div
          style={{
            background: verifyResult.is_match ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${verifyResult.is_match ? '#bbf7d0' : '#fecaca'}`,
            color: verifyResult.is_match ? '#166534' : '#991b1b',
            padding: '16px 20px',
            borderRadius: '4px',
            marginBottom: '20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            {verifyResult.is_match ? (
              <ShieldCheck size={20} color="#16a34a" />
            ) : (
              <ShieldAlert size={20} color="#dc2626" />
            )}
            <strong style={{ fontSize: '14px' }}>
              Verification Verdict: {verifyResult.status.toUpperCase()}
            </strong>
          </div>
          <p style={{ fontSize: '13px', marginBottom: '10px' }}>{verifyResult.notes}</p>
          <div style={{ fontSize: '12px', display: 'grid', gridTemplateColumns: '130px 1fr', gap: '6px' }}>
            <span style={{ fontWeight: 500 }}>Recorded Hash:</span>
            <span className="mono">{verifyResult.recorded_hash}</span>
            <span style={{ fontWeight: 500 }}>Recalculated:</span>
            <span className="mono">{verifyResult.recalculated_hash}</span>
          </div>
        </div>
      )}

      {/* Metadata & Hashing Overview Grid */}
      <div className="stats-grid" style={{ marginBottom: '20px' }}>
        <div className="stat-card">
          <div>
            <div className="stat-card-label">File Size</div>
            <div className="stat-card-val" style={{ fontSize: '16px' }}>
              {(evidence.file_size / 1024).toFixed(1)} KB
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {evidence.file_size.toLocaleString()} raw bytes
            </div>
          </div>
          <HardDrive size={22} color="var(--text-muted)" />
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">MIME Type</div>
            <div className="stat-card-val" style={{ fontSize: '15px' }}>
              {evidence.mime_type}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Magic bytes verified</div>
          </div>
          {evidence.detected_file_type === 'image' ? (
            <FileImage size={22} color="#2563eb" />
          ) : evidence.detected_file_type === 'video' ? (
            <FileVideo size={22} color="#7c3aed" />
          ) : (
            <FileAudio size={22} color="#059669" />
          )}
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">Ingestion Timestamp</div>
            <div className="stat-card-val" style={{ fontSize: '14px' }}>
              {formatDate(evidence.uploaded_at)}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Synchronous intake check</div>
          </div>
          <Clock size={22} color="var(--text-muted)" />
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">Associated Case</div>
            <div className="stat-card-val" style={{ fontSize: '15px' }}>
              {evidence.case_number}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{evidence.case_title}</div>
          </div>
          <Folder size={22} color="var(--text-muted)" />
        </div>
      </div>

      {/* SHA-256 Digest Card */}
      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={16} color="#2563eb" />
            <span>SHA-256 Reference Baseline Digest</span>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '3px 10px', fontSize: '11px' }}
            onClick={() => copyToClipboard(evidence.sha256_hash)}
          >
            {copiedHash ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
            <span>{copiedHash ? 'Digest Copied' : 'Copy Hash'}</span>
          </button>
        </div>

        <div
          style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '4px',
            padding: '12px 16px',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span className="mono" style={{ fontSize: '13px', wordBreak: 'break-all', fontWeight: 600 }}>
            {evidence.sha256_hash}
          </span>
        </div>

        <div style={{ marginTop: '12px', fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
          <Info size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>
            <strong>Forensic Reference Note (FR-04):</strong> A matching hash verifies exact byte equality with the reference calculated at ingestion. It proves that the evidence on storage has not suffered byte degradation, tampering, or bit-rot since registration.
          </span>
        </div>
      </div>

      {/* Media Preview Section */}
      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header">
          <span className="card-title">Evidence Media Inspection</span>
          <span className="badge badge-neutral">Read-Only Safe Stream</span>
        </div>

        <div style={{ textAlign: 'center', background: '#0f172a', borderRadius: '4px', padding: '24px', minHeight: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {evidence.detected_file_type === 'image' && (
            <img
              src={downloadUrl}
              alt={evidence.original_filename}
              style={{ maxHeight: '360px', maxWidth: '100%', objectFit: 'contain', borderRadius: '4px' }}
            />
          )}

          {evidence.detected_file_type === 'video' && (
            <video
              controls
              src={downloadUrl}
              style={{ maxHeight: '360px', maxWidth: '100%', borderRadius: '4px' }}
            >
              Your browser does not support inline video playback.
            </video>
          )}

          {evidence.detected_file_type === 'audio' && (
            <div style={{ width: '100%', maxWidth: '480px' }}>
              <FileAudio size={48} color="#94a3b8" style={{ marginBottom: '16px' }} />
              <audio controls src={downloadUrl} style={{ width: '100%' }}>
                Your browser does not support inline audio playback.
              </audio>
            </div>
          )}
        </div>
      </div>

      {/* Chronological Integrity Checks Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={16} color="var(--primary-blue)" />
            <span>SHA-256 Integrity Verification Audit History</span>
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            ({evidence.integrity_checks.length} Verification Records)
          </span>
        </div>

        <div className="table-container" style={{ border: 'none' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Verification Timestamp</th>
                <th>Status Verdict</th>
                <th>Recorded Hash</th>
                <th>Recalculated Hash</th>
                <th>Forensic Audit Notes</th>
              </tr>
            </thead>
            <tbody>
              {evidence.integrity_checks.map((chk) => (
                <tr key={chk.id}>
                  <td style={{ fontSize: '12px', whiteSpace: 'nowrap' }}>{formatDate(chk.checked_at)}</td>
                  <td>
                    <StatusBadge
                      status={chk.result.toUpperCase()}
                      variant={
                        chk.result === 'Match'
                          ? 'success'
                          : chk.result === 'Mismatch'
                          ? 'danger'
                          : 'neutral'
                      }
                    />
                  </td>
                  <td>
                    <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {chk.recorded_hash.substring(0, 16)}...
                    </span>
                  </td>
                  <td>
                    <span className="mono" style={{ fontSize: '11px', color: chk.result === 'Match' ? '#166534' : '#991b1b' }}>
                      {chk.recalculated_hash ? `${chk.recalculated_hash.substring(0, 16)}...` : 'N/A'}
                    </span>
                  </td>
                  <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{chk.notes || 'Routine check'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
