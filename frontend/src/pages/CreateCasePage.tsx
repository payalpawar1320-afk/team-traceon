import React, { useState } from 'react';
import type { PageId } from '../types';
import { createCase } from '../api/client';
import { FolderPlus, ArrowLeft, ShieldAlert, CheckCircle2 } from 'lucide-react';

interface CreateCasePageProps {
  onNavigate: (page: PageId, caseIdentifier?: string | number) => void;
}

export const CreateCasePage: React.FC<CreateCasePageProps> = ({ onNavigate }) => {
  const [caseNumber, setCaseNumber] = useState('');
  const [title, setTitle] = useState('');
  const [investigatorName, setInvestigatorName] = useState('Lead Investigator');
  const [status, setStatus] = useState<'active' | 'closed' | 'archived'>('active');
  const [description, setDescription] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    if (title.trim().length < 3) {
      setError('Case title must be at least 3 characters in length.');
      return;
    }

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
      setError(err instanceof Error ? err.message : 'Failed to register investigation case.');
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
        <button
          className="btn btn-secondary"
          onClick={() => onNavigate('my-cases')}
          type="button"
        >
          <ArrowLeft size={15} /> Back to Cases
        </button>
      </div>

      <div className="notice-box notice-info" style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span className="badge badge-primary" style={{ padding: '3px 8px', fontSize: '11px', fontWeight: 700 }}>STEP 1 OF 5</span>
        <span style={{ fontSize: '12px' }}>
          <strong>Start Investigation:</strong> Register an official case container first. All subsequent evidence uploads, integrity checks, and reports will be grouped under this case.
        </span>
      </div>

      {error && (
        <div className="alert-banner alert-error">
          <ShieldAlert size={18} />
          <div>{error}</div>
        </div>
      )}

      {successMsg && (
        <div className="alert-banner alert-success">
          <CheckCircle2 size={18} />
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

        <form onSubmit={handleSubmit}>
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
                className="form-input"
                placeholder="e.g. Inspector R. Sharma"
                value={investigatorName}
                onChange={(e) => setInvestigatorName(e.target.value)}
                required
                disabled={loading}
              />
              <p className="form-hint">Authorised investigator maintaining chain-of-custody.</p>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="caseTitle">
              Case Title / Primary Incident Classification <span className="required">*</span>
            </label>
            <input
              id="caseTitle"
              type="text"
              className="form-input"
              placeholder="e.g. Unauthorized Cloud Server Infiltration & Digital Extortion"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              disabled={loading}
            />
            <p className="form-hint">A concise, descriptive summary of the incident under forensic inquiry.</p>
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
              type="submit"
              className="btn btn-primary"
              disabled={loading}
            >
              <FolderPlus size={16} />
              {loading ? 'Registering Case...' : 'Register Case File'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
