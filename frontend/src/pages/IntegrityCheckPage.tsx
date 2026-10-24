import React, { useState, useEffect, useCallback } from 'react';
import type { PageId, EvidenceItem, CaseSummary, BatchVerifyResponse } from '../types';
import {
  fetchAllEvidence,
  fetchCases,
  verifyEvidenceIntegrity,
  verifyAllCaseEvidence,
} from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  RefreshCw,
  Search,
  Check,
  Copy,
  ExternalLink,
  Info,
  Layers,
} from 'lucide-react';


interface IntegrityCheckPageProps {
  onNavigate: (page: PageId, caseIdentifier?: string | number, evidenceId?: number) => void;
}

export const IntegrityCheckPage: React.FC<IntegrityCheckPageProps> = ({ onNavigate }) => {
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([]);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<number | 'all'>('all');
  const [search, setSearch] = useState<string>('');
  const [fileType, setFileType] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [verifyingId, setVerifyingId] = useState<number | null>(null);
  const [batchVerifying, setBatchVerifying] = useState<boolean>(false);
  const [batchResult, setBatchResult] = useState<BatchVerifyResponse | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [casesData, evidenceData] = await Promise.all([
        fetchCases(),
        fetchAllEvidence({
          search: search || undefined,
          fileType: fileType !== 'all' ? fileType : undefined,
          caseId: selectedCaseId !== 'all' ? selectedCaseId : undefined,
        }),
      ]);
      setCases(casesData);
      setEvidenceList(evidenceData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to retrieve evidence records.');
    } finally {
      setLoading(false);
    }
  }, [search, fileType, selectedCaseId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleVerifySingle = async (evidenceId: number) => {
    setVerifyingId(evidenceId);
    try {
      await verifyEvidenceIntegrity(evidenceId);
      await loadData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Verification failed.');
    } finally {
      setVerifyingId(null);
    }
  };

  const handleBatchVerify = async () => {
    if (selectedCaseId === 'all') return;
    setBatchVerifying(true);
    setBatchResult(null);
    try {
      const res = await verifyAllCaseEvidence(selectedCaseId);
      setBatchResult(res);
      await loadData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Batch verification failed.');
    } finally {
      setBatchVerifying(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Metrics calculation
  const totalMonitored = evidenceList.length;
  const matchCount = evidenceList.filter((e) => e.latest_integrity_status === 'Match').length;
  const mismatchCount = evidenceList.filter((e) => e.latest_integrity_status === 'Mismatch').length;
  const uncheckedCount = evidenceList.filter(
    (e) => !e.latest_integrity_status || e.latest_integrity_status === 'Not checked'
  ).length;

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">SHA-256 Byte Integrity Verification</h1>
          <p className="page-subtitle">
            Cryptographic byte-level hash verification comparing storage files against intake references (spec.md FR-04).
          </p>
        </div>

        {selectedCaseId !== 'all' && (
          <button
            type="button"
            className="btn btn-primary"
            style={{ fontSize: '12px' }}
            onClick={handleBatchVerify}
            disabled={batchVerifying || evidenceList.length === 0}
          >
            <RefreshCw size={13} className={batchVerifying ? 'spin' : ''} />
            <span>{batchVerifying ? 'Auditing Case Files...' : 'Run Case Batch Integrity Audit'}</span>
          </button>
        )}
      </div>

      <div className="notice-box notice-info" style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span className="badge badge-primary" style={{ padding: '3px 8px', fontSize: '11px', fontWeight: 700 }}>STEP 3 OF 5</span>
        <span style={{ fontSize: '12px' }}>
          <strong>Cryptographic Authenticity Audit:</strong> Verify on-demand whether file bytes exactly match the reference SHA-256 hash recorded at seizure. A matching digest proves zero unauthorized byte tampering.
        </span>
      </div>

      {error && (
        <div
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            padding: '12px 16px',
            borderRadius: '4px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '13px',
          }}
        >
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Batch Result Notification */}
      {batchResult && (
        <div
          style={{
            background: batchResult.mismatch_count > 0 ? '#fef2f2' : '#f0fdf4',
            border: `1px solid ${batchResult.mismatch_count > 0 ? '#fecaca' : '#bbf7d0'}`,
            color: batchResult.mismatch_count > 0 ? '#991b1b' : '#166534',
            padding: '16px 20px',
            borderRadius: '4px',
            marginBottom: '20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            {batchResult.mismatch_count > 0 ? (
              <ShieldAlert size={20} color="#dc2626" />
            ) : (
              <ShieldCheck size={20} color="#16a34a" />
            )}
            <strong style={{ fontSize: '14px' }}>
              Batch Audit Completed for Case {batchResult.case_number}
            </strong>
          </div>
          <p style={{ fontSize: '13px', margin: 0 }}>
            Audited {batchResult.total_checked} files: <strong>{batchResult.match_count} Matches</strong>,{' '}
            <strong style={{ color: '#dc2626' }}>{batchResult.mismatch_count} Mismatches</strong>,{' '}
            <strong>{batchResult.failed_count} Check Failures</strong>.
          </p>
        </div>
      )}

      {/* Metrics Cards */}
      <div className="stats-grid" style={{ marginBottom: '20px' }}>
        <div className="stat-card">
          <div>
            <div className="stat-card-label">Files Monitored</div>
            <div className="stat-card-val">{totalMonitored}</div>
          </div>
          <Layers size={24} color="var(--text-muted)" />
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">Verified Matches</div>
            <div className="stat-card-val" style={{ color: '#16a34a' }}>
              {matchCount}
            </div>
          </div>
          <ShieldCheck size={24} color="#16a34a" />
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">Integrity Mismatches</div>
            <div className="stat-card-val" style={{ color: mismatchCount > 0 ? '#dc2626' : 'var(--text-muted)' }}>
              {mismatchCount}
            </div>
          </div>
          <ShieldAlert size={24} color={mismatchCount > 0 ? '#dc2626' : 'var(--text-muted)'} />
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">Unchecked / Pending</div>
            <div className="stat-card-val" style={{ color: 'var(--text-muted)' }}>
              {uncheckedCount}
            </div>
          </div>
          <RefreshCw size={24} color="var(--text-muted)" />
        </div>
      </div>

      {/* Forensic Guarantee & Legal Disclaimer Card */}
      <div
        style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '4px',
          padding: '12px 16px',
          marginBottom: '20px',
          fontSize: '12px',
          color: '#475569',
          display: 'flex',
          gap: '8px',
          alignItems: 'flex-start',
        }}
      >
        <Info size={16} color="#2563eb" style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong>Forensic Hashing Protocol (spec.md §FR-04):</strong> Recalculated SHA-256 digests strictly guarantee binary byte equality with the reference calculated at the moment of intake. A <em>Match</em> proves the stored evidence bytes have not been tampered with or corrupted while residing in the platform.
        </div>
      </div>

      {/* Filters Bar */}
      <div className="card" style={{ marginBottom: '20px', padding: '14px 16px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Case Filter */}
          <div style={{ minWidth: '240px', flex: 1 }}>
            <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
              Filter by Investigation Case
            </label>
            <select
              className="form-input"
              value={selectedCaseId}
              onChange={(e) =>
                setSelectedCaseId(e.target.value === 'all' ? 'all' : Number(e.target.value))
              }
              style={{ fontSize: '13px' }}
            >
              <option value="all">-- All Investigation Cases --</option>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.case_number} — {c.title}
                </option>
              ))}
            </select>
          </div>

          {/* Media Type Filter */}
          <div style={{ minWidth: '160px' }}>
            <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
              Media Category
            </label>
            <select
              className="form-input"
              value={fileType}
              onChange={(e) => setFileType(e.target.value)}
              style={{ fontSize: '13px' }}
            >
              <option value="all">All Media Types</option>
              <option value="image">Images (JPG, PNG)</option>
              <option value="video">Videos (MP4, MOV, AVI)</option>
              <option value="audio">Audio (WAV, MP3)</option>
            </select>
          </div>

          {/* Search Input */}
          <div style={{ minWidth: '220px', flex: 1 }}>
            <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
              Search Filename or Hash
            </label>
            <div style={{ position: 'relative' }}>
              <Search
                size={14}
                style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }}
              />
              <input
                type="text"
                className="form-input"
                style={{ paddingLeft: '32px', fontSize: '13px' }}
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Evidence Integrity Table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Evidence Files Verification Inventory</span>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Showing {evidenceList.length} registered evidence items
          </span>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '36px', color: 'var(--text-muted)' }}>
            <RefreshCw size={24} className="spin" style={{ marginBottom: '8px' }} />
            <p style={{ fontSize: '13px' }}>Loading evidence integrity records...</p>
          </div>
        ) : evidenceList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 16px', color: 'var(--text-muted)' }}>
            <ShieldCheck size={36} style={{ marginBottom: '8px', opacity: 0.4 }} />
            <p style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-main)', marginBottom: '4px' }}>
              No evidence files match current criteria
            </p>
            <p style={{ fontSize: '12px', marginBottom: '16px' }}>
              Upload evidence media to an investigation case to initiate SHA-256 cryptographic monitoring.
            </p>
            <button
              className="btn btn-primary"
              style={{ fontSize: '12px' }}
              onClick={() => onNavigate('evidence-upload')}
            >
              Upload Digital Evidence
            </button>
          </div>
        ) : (
          <div className="table-container" style={{ border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Evidence ID</th>
                  <th>Original Filename</th>
                  <th>Media Type</th>
                  <th>File Size</th>
                  <th>Baseline SHA-256 Hash</th>
                  <th>Integrity Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {evidenceList.map((item) => (
                  <tr key={item.id}>
                    <td style={{ fontWeight: 600, fontSize: '12px' }}>{item.evidence_number}</td>
                    <td style={{ fontWeight: 500 }}>{item.original_filename}</td>
                    <td>
                      <span className="badge badge-neutral">{item.detected_file_type.toUpperCase()}</span>
                    </td>
                    <td>{(item.file_size / 1024).toFixed(1)} KB</td>
                    <td>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                        <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {item.sha256_hash.substring(0, 16)}...
                        </span>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(item.sha256_hash)}
                          title="Copy full SHA-256 digest"
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary-blue)' }}
                        >
                          {copiedHash === item.sha256_hash ? (
                            <Check size={12} color="#16a34a" />
                          ) : (
                            <Copy size={12} />
                          )}
                        </button>
                      </div>
                    </td>
                    <td>
                      <StatusBadge
                        status={
                          item.latest_integrity_status === 'Match'
                            ? 'MATCH'
                            : item.latest_integrity_status === 'Mismatch'
                            ? 'MISMATCH'
                            : 'NOT CHECKED'
                        }
                        variant={
                          item.latest_integrity_status === 'Match'
                            ? 'success'
                            : item.latest_integrity_status === 'Mismatch'
                            ? 'danger'
                            : 'neutral'
                        }
                      />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ padding: '3px 8px', fontSize: '11px' }}
                          onClick={() => handleVerifySingle(item.id)}
                          disabled={verifyingId === item.id}
                        >
                          <RefreshCw size={11} className={verifyingId === item.id ? 'spin' : ''} />
                          <span>{verifyingId === item.id ? 'Verifying...' : 'Verify'}</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ padding: '3px 8px', fontSize: '11px' }}
                          onClick={() => onNavigate('evidence-details', item.case_id, item.id)}
                          title="Examine dossier and media"
                        >
                          <ExternalLink size={11} />
                          <span>Dossier</span>
                        </button>
                      </div>
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
