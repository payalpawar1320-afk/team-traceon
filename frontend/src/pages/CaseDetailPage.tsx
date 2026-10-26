import React, { useState, useEffect, useCallback } from 'react';
import type { PageId, CaseDetail } from '../types';
import { fetchCaseById, updateCase } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import {
  ArrowLeft,
  Folder,
  FileUp,
  FileCheck2,
  Activity,
  User,
  Clock,
  ShieldCheck,
  AlertTriangle,
  FileCode,
  HardDrive,
  Copy,
  Check,
  GitCompare,
  Files,
} from 'lucide-react';

interface CaseDetailPageProps {
  caseIdentifier: string | number | null;
  onNavigate: (page: PageId, caseIdentifier?: string | number, evidenceId?: number) => void;
}


export const CaseDetailPage: React.FC<CaseDetailPageProps> = ({
  caseIdentifier,
  onNavigate,
}) => {
  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState<boolean>(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const loadCase = useCallback(async () => {
    if (!caseIdentifier) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCaseById(caseIdentifier);
      setCaseData(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to retrieve case details.');
    } finally {
      setLoading(false);
    }
  }, [caseIdentifier]);

  useEffect(() => {
    loadCase();
  }, [loadCase]);

  const handleStatusChange = async (newStatus: 'active' | 'closed' | 'archived') => {
    if (!caseData || newStatus === caseData.status) return;
    setUpdatingStatus(true);
    try {
      await updateCase(caseData.id, { status: newStatus });
      await loadCase();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to update case status.');
    } finally {
      setUpdatingStatus(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
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
      });
    } catch {
      return isoStr;
    }
  };

  if (!caseIdentifier) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
        <Folder size={40} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
        <h2 style={{ fontSize: '18px', fontWeight: 600 }}>No Case Selected</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '8px 0 16px' }}>
          Please select an investigation case from the directory to review its evidence and forensic findings.
        </p>
        <button className="btn btn-primary" onClick={() => onNavigate('my-cases')}>
          <ArrowLeft size={14} /> Go to Cases Directory
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
        <p>Loading case file {String(caseIdentifier)}...</p>
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div>
        <div className="alert-banner alert-error">
          <AlertTriangle size={18} />
          <div>{error || 'Unable to open case file.'}</div>
        </div>
        <button className="btn btn-secondary" onClick={() => onNavigate('my-cases')}>
          <ArrowLeft size={14} /> Back to Directory
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header with Case Title & Quick Controls */}
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 8px', fontSize: '12px' }}
              onClick={() => onNavigate('my-cases')}
            >
              <ArrowLeft size={13} /> Cases
            </button>
            <span className="mono" style={{ fontSize: '14px', fontWeight: 700, color: 'var(--primary-blue)' }}>
              {caseData.case_number}
            </span>
            <StatusBadge status={caseData.status.toUpperCase()} />
          </div>
          <h1 className="page-title">{caseData.title}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <User size={13} /> {caseData.investigator_name}
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={13} /> Registered: {formatDate(caseData.created_at)}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
            Status:
          </label>
          <select
            className="form-select"
            style={{ width: 'auto', padding: '5px 10px', fontSize: '12px' }}
            value={caseData.status}
            disabled={updatingStatus}
            onChange={(e) => handleStatusChange(e.target.value as 'active' | 'closed' | 'archived')}
          >
            <option value="active">Active (Under Investigation)</option>
            <option value="closed">Closed (Inquiry Complete)</option>
            <option value="archived">Archived</option>
          </select>

          <button
            className="btn btn-secondary"
            onClick={() => onNavigate('cross-check', caseData.id)}
            title="Perform cross-evidence forensic timeline and consistency comparison"
          >
            <GitCompare size={14} /> Cross-Check
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => {
              sessionStorage.setItem('preferredUploadMode', 'single');
              onNavigate('evidence-upload', caseData.id);
            }}
          >
            <FileUp size={14} /> Add Evidence
          </button>

          <button
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            onClick={() => {
              sessionStorage.setItem('preferredUploadMode', 'batch');
              onNavigate('evidence-upload', caseData.id);
            }}
            title="Upload multiple images at once to this case"
          >
            <Files size={14} /> Add Multiple Images
          </button>
        </div>
      </div>

      {/* Stats Summary Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div>
            <div className="stat-card-label">Digital Evidence Items</div>
            <div className="stat-card-val">{caseData.evidence_count}</div>
          </div>
          <HardDrive size={24} style={{ color: 'var(--text-muted)' }} />
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">Forensic Analyses</div>
            <div className="stat-card-val">{caseData.analysis_count}</div>
          </div>
          <FileCheck2 size={24} style={{ color: 'var(--primary-blue)' }} />
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">Chain-of-Custody Events</div>
            <div className="stat-card-val">{caseData.audit_events.length}</div>
          </div>
          <Activity size={24} style={{ color: 'var(--text-muted)' }} />
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">Integrity Status</div>
            <div style={{ marginTop: '4px' }}>
              <StatusBadge status="ACTIVE HASH GUARANTEE" variant="success" />
            </div>
          </div>
          <ShieldCheck size={24} style={{ color: '#16a34a' }} />
        </div>
      </div>

      {/* Case Description / Incident Notes */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Incident Background & Forensic Objectives</span>
        </div>
        <p style={{ fontSize: '13px', lineHeight: 1.6, color: caseData.description ? 'var(--text-main)' : 'var(--text-muted)' }}>
          {caseData.description || 'No detailed incident summary was provided at registration.'}
        </p>
      </div>

      {/* Associated Digital Evidence Items */}
      <div className="card">
        <div className="card-header">
          <div>
            <span className="card-title">Digital Evidence Inventory</span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '10px' }}>
              ({caseData.evidence_items.length} Registered Items)
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: '12px' }}
              onClick={() => onNavigate('integrity-check', caseData.id)}
            >
              <ShieldCheck size={13} /> Verify Integrity
            </button>
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
              onClick={() => {
                sessionStorage.setItem('preferredUploadMode', 'single');
                onNavigate('evidence-upload', caseData.id);
              }}
            >
              <FileUp size={13} /> Ingest File
            </button>
            <button
              className="btn btn-primary"
              style={{ padding: '4px 10px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
              onClick={() => {
                sessionStorage.setItem('preferredUploadMode', 'batch');
                onNavigate('evidence-upload', caseData.id);
              }}
              title="Upload multiple photos or evidence files at once"
            >
              <Files size={13} /> Add Multiple Images
            </button>
          </div>
        </div>

        {caseData.evidence_items.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-muted)' }}>
            <FileCode size={32} style={{ marginBottom: '8px', opacity: 0.5 }} />
            <p style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-main)', marginBottom: '4px' }}>
              No digital evidence registered yet
            </p>
            <p style={{ fontSize: '12px', maxWidth: '380px', margin: '0 auto 14px' }}>
              Securely upload image, video, or audio media to this case to generate SHA-256 baseline hashes and perform tamper analysis.
            </p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap' }}>
              <button
                className="btn btn-primary"
                style={{ fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                onClick={() => {
                  sessionStorage.setItem('preferredUploadMode', 'batch');
                  onNavigate('evidence-upload', caseData.id);
                }}
              >
                <Files size={13} /> Add Multiple Images (Batch)
              </button>
              <button
                className="btn btn-secondary"
                style={{ fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                onClick={() => {
                  sessionStorage.setItem('preferredUploadMode', 'single');
                  onNavigate('evidence-upload', caseData.id);
                }}
              >
                <FileUp size={13} /> Single File Ingest
              </button>
            </div>
          </div>
        ) : (
          <div className="table-container" style={{ border: 'none' }}>
            {caseData.evidence_items.some((e) => e.is_duplicate) && (
              <div
                style={{
                  marginBottom: '14px',
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
                  <strong>Duplicate Evidence Detected:</strong> Multiple records share identical SHA-256 cryptographic digests. Both files were preserved and retained in chain of custody.
                </span>
              </div>
            )}
            <table className="data-table">
              <thead>
                <tr>
                  <th>Original Filename</th>
                  <th>Type</th>
                  <th>File Size</th>
                  <th>SHA-256 Baseline Digest</th>
                  <th>Ingested At</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {caseData.evidence_items.map((ev) => (
                  <tr key={ev.id}>
                    <td style={{ fontWeight: 600 }}>
                      {ev.original_filename}
                      {ev.is_duplicate && (
                        <div style={{ marginTop: '2px' }}>
                          <span
                            className="badge"
                            style={{
                              background: '#fef3c7',
                              color: '#92400e',
                              border: '1px solid #fde68a',
                              fontSize: '10px',
                              fontWeight: 600,
                            }}
                            title={ev.duplicate_warning || 'Identical SHA-256 hash matches another evidence file in this case'}
                          >
                            ⚠️ Duplicate File
                          </span>
                        </div>
                      )}
                    </td>
                    <td>
                      <span className="badge badge-neutral">{ev.detected_file_type.toUpperCase()}</span>
                    </td>
                    <td>{(ev.file_size / 1024).toFixed(1)} KB</td>
                    <td>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                        <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {ev.sha256_hash.substring(0, 16)}...
                        </span>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(ev.sha256_hash)}
                          title="Copy full SHA-256 hash"
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary-blue)' }}
                        >
                          {copiedHash === ev.sha256_hash ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
                        </button>
                      </div>
                    </td>
                    <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{formatDate(ev.uploaded_at)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '3px 8px', fontSize: '11px' }}
                        onClick={() => onNavigate('evidence-details', caseData.id, ev.id)}
                      >
                        Examine
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

      </div>

      {/* Case Audit Trail Log */}
      <div className="card">
        <div className="card-header">
          <div>
            <span className="card-title">Forensic Audit Log</span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '10px' }}>
              (Chain of Custody Events)
            </span>
          </div>
        </div>

        {caseData.audit_events.length === 0 ? (
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No audit events recorded.</p>
        ) : (
          <div className="table-container" style={{ border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '170px' }}>Timestamp</th>
                  <th style={{ width: '160px' }}>Action</th>
                  <th>Investigating Officer / Actor</th>
                  <th style={{ width: '100px' }}>Result</th>
                  <th style={{ width: '130px' }}>Origin IP</th>
                </tr>
              </thead>
              <tbody>
                {caseData.audit_events.map((evt) => (
                  <tr key={evt.id}>
                    <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      {formatDate(evt.created_at)}
                    </td>
                    <td>
                      <span className="mono" style={{ fontWeight: 600, fontSize: '12px' }}>
                        {evt.action}
                      </span>
                    </td>
                    <td style={{ fontSize: '12px' }}>{evt.actor_id}</td>
                    <td>
                      <StatusBadge status={evt.result.toUpperCase()} />
                    </td>
                    <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {evt.ip_address || '127.0.0.1'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
