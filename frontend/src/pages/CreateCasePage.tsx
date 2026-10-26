import React, { useState } from 'react';
import type { PageId, HealthResponse } from '../types';
import { createCase } from '../api/client';
import { FolderPlus, ArrowLeft, ShieldAlert, CheckCircle2, Sparkles, AlertCircle, ServerCrash } from 'lucide-react';

interface CreateCasePageProps {
  onNavigate: (page: PageId, caseIdentifier?: string | number) => void;
  health?: HealthResponse | null;
}

export const CreateCasePage: React.FC<CreateCasePageProps> = ({ onNavigate, health }) => {
  const [caseNumber, setCaseNumber] = useState('');
  const [title, setTitle] = useState('');
  const [investigatorName, setInvestigatorName] = useState('Lead Investigator');
  const [status, setStatus] = useState<'active' | 'closed' | 'archived'>('active');
  const [description, setDescription] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; investigatorName?: string }>({});

  const isBackendOffline = health !== undefined && health === null;

  const handlePreFillSample = () => {
    setError(null);
    setFieldErrors({});
    setTitle('Unauthorized Infiltration & Cloud Extortion Inquiry');
    setInvestigatorName('Inspector R. Sharma');
    setDescription(
      'Investigation into unauthorized credential abuse, exfiltration of financial records, and ransom demands. Seized digital exhibits include server backup archives and suspect smartphone recordings.'
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    const newFieldErrors: { title?: string; investigatorName?: string } = {};

    if (!title.trim()) {
      newFieldErrors.title = 'Case Title is required.';
    } else if (title.trim().length < 3) {
      newFieldErrors.title = 'Case Title must be at least 3 characters in length.';
    }

    if (!investigatorName.trim()) {
      newFieldErrors.investigatorName = 'Investigating Officer name is required.';
    } else if (investigatorName.trim().length < 2) {
      newFieldErrors.investigatorName = 'Investigating Officer name must be at least 2 characters.';
    }

    if (Object.keys(newFieldErrors).length > 0) {
      setFieldErrors(newFieldErrors);
      setError('Please resolve the required field errors highlighted below.');
      return;
    }

    setFieldErrors({});
    setLoading(true);

    try {
      const created = await createCase({
        case_number: caseNumber.trim() || undefined,
        title: title.trim(),
        investigator_name: investigatorName.trim() || undefined,
        status,
        description: description.trim() || undefined,
      });

      setSuccessMsg(`Case ${created.case_number} registered successfully! Redirecting to case file...`);
      setTimeout(() => {
        onNavigate('case-details', created.id);
      }, 1200);
    } catch (err: unknown) {
      let errMsg = err instanceof Error ? err.message : 'Failed to register investigation case.';
      if (
        errMsg.toLowerCase().includes('failed to fetch') ||
        errMsg.toLowerCase().includes('networkerror') ||
        errMsg.toLowerCase().includes('econnrefused') ||
        errMsg.includes('500') ||
        errMsg.includes('504')
      ) {
        errMsg =
          'Backend server is offline or unreachable. Please start the backend service (run: `backend\\venv\\Scripts\\uvicorn app.main:app --app-dir backend --port 8000`) or verify network connection.';
      }
      setError(errMsg);
      // Scroll smoothly to ensure user sees the feedback
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 className="page-title">Register Investigation Case</h1>
          <p className="page-subtitle">
            Create an official digital evidence case container with unique identification and audit log tracking.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="btn btn-secondary"
            onClick={handlePreFillSample}
            type="button"
            title="Automatically populate sample police investigation data"
            style={{ fontSize: '12px' }}
          >
            <Sparkles size={14} color="#6366f1" /> Pre-fill Sample
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => onNavigate('my-cases')}
            type="button"
            style={{ fontSize: '12px' }}
          >
            <ArrowLeft size={14} /> Back to Cases
          </button>
        </div>
      </div>

      {isBackendOffline && (
        <div
          className="alert-banner alert-warning"
          style={{
            background: '#fffbeb',
            borderColor: '#f59e0b',
            color: '#b45309',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            padding: '12px 16px',
            borderRadius: '6px',
          }}
        >
          <ServerCrash size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong>Backend API is Offline:</strong> The web app is currently unable to communicate with the FastAPI backend on port 8000.
            <div style={{ fontSize: '12px', marginTop: '4px', color: '#78350f' }}>
              To enable case registration and evidence ingestion, start the local backend server:
              <br />
              <code style={{ background: '#fef3c7', padding: '2px 6px', borderRadius: '4px' }}>
                backend\venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload --port 8000
              </code>
            </div>
          </div>
        </div>
      )}

      <div className="notice-box notice-info" style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span className="badge badge-primary" style={{ padding: '3px 8px', fontSize: '11px', fontWeight: 700 }}>STEP 1 OF 5</span>
        <span style={{ fontSize: '12px' }}>
          <strong>Start Investigation:</strong> Register an official case container first. All subsequent evidence uploads, integrity checks, and reports will be grouped under this case.
        </span>
      </div>

      {error && (
        <div className="alert-banner alert-error" style={{ marginBottom: '16px' }}>
          <ShieldAlert size={18} style={{ flexShrink: 0 }} />
          <div>{error}</div>
        </div>
      )}

      {successMsg && (
        <div className="alert-banner alert-success" style={{ marginBottom: '16px' }}>
          <CheckCircle2 size={18} style={{ flexShrink: 0 }} />
          <div>{successMsg}</div>
        </div>
      )}

      <div className="card" style={{ maxWidth: '800px' }}>
        <div className="card-header">
          <span className="card-title">Case Registration Form</span>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Digital Evidence Ingestion Standard
          </span>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="caseNumber">
                Case Identifier (Optional)
              </label>
              <input
                id="caseNumber"
                type="text"
                className="form-input mono"
                placeholder="e.g. CASE-2026-1042"
                value={caseNumber}
                onChange={(e) => setCaseNumber(e.target.value)}
                disabled={loading}
              />
              <p className="form-hint">
                Leave blank to auto-generate standard police case number (<code>CASE-2026-XXXX</code>).
              </p>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="investigatorName">
                Assigned Investigating Officer <span className="required">*</span>
              </label>
              <input
                id="investigatorName"
                type="text"
                className={`form-input ${fieldErrors.investigatorName ? 'input-error' : ''}`}
                placeholder="e.g. Inspector R. Sharma"
                value={investigatorName}
                onChange={(e) => {
                  setInvestigatorName(e.target.value);
                  if (fieldErrors.investigatorName) {
                    setFieldErrors((prev) => ({ ...prev, investigatorName: undefined }));
                  }
                }}
                disabled={loading}
              />
              {fieldErrors.investigatorName ? (
                <p className="form-hint" style={{ color: '#dc2626', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <AlertCircle size={12} /> {fieldErrors.investigatorName}
                </p>
              ) : (
                <p className="form-hint">Authorised investigator maintaining chain-of-custody.</p>
              )}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="caseTitle">
              Case Title / Primary Incident Classification <span className="required">*</span>
            </label>
            <input
              id="caseTitle"
              type="text"
              className={`form-input ${fieldErrors.title ? 'input-error' : ''}`}
              placeholder="e.g. Unauthorized Cloud Server Infiltration & Digital Extortion"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                if (fieldErrors.title) {
                  setFieldErrors((prev) => ({ ...prev, title: undefined }));
                }
              }}
              disabled={loading}
            />
            {fieldErrors.title ? (
              <p className="form-hint" style={{ color: '#dc2626', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <AlertCircle size={12} /> {fieldErrors.title}
              </p>
            ) : (
              <p className="form-hint">A concise, descriptive summary of the incident under forensic inquiry (min 3 chars).</p>
            )}
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="status">
                Initial Investigation Status <span className="required">*</span>
              </label>
              <select
                id="status"
                className="form-select"
                value={status}
                onChange={(e) => setStatus(e.target.value as 'active' | 'closed' | 'archived')}
                disabled={loading}
              >
                <option value="active">Active (Under Investigation)</option>
                <option value="closed">Closed (Inquiry Complete)</option>
                <option value="archived">Archived (Cold / Deposited)</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="description">
              Incident Details & Seizure Background
            </label>
            <textarea
              id="description"
              className="form-textarea"
              placeholder="Describe origin of digital evidence, date of seizure, FIR reference number, or relevant forensic goals..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={loading}
              rows={4}
            />
          </div>

          <div className="notice-box notice-info" style={{ marginTop: '10px' }}>
            <div>
              <strong>Forensic Chain-of-Custody Notice:</strong> Registering this case creates a permanent, immutable timestamped record in the system audit log. All subsequent evidence uploads and verification checks will be linked to this case ID.
            </div>
          </div>

          {error && (
            <div
              className="alert-banner alert-error"
              style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <ShieldAlert size={16} style={{ flexShrink: 0 }} />
              <div style={{ fontSize: '13px' }}>{error}</div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onNavigate('my-cases')}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              id="submit-create-case-btn"
              type="submit"
              className="btn btn-primary"
              disabled={loading}
            >
              <FolderPlus size={16} />
              {loading ? 'Registering Case...' : 'Register Case'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
