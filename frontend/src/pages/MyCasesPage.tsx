import React, { useState, useEffect, useCallback } from 'react';
import type { PageId, CaseSummary } from '../types';
import { fetchCases } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import {
  FolderPlus,
  Search,
  FolderOpen,
  RefreshCw,
  FileCheck,
  AlertCircle,
  Clock,
  User,
} from 'lucide-react';

interface MyCasesPageProps {
  onNavigate: (page: PageId, caseIdentifier?: string | number) => void;
}

export const MyCasesPage: React.FC<MyCasesPageProps> = ({ onNavigate }) => {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const loadCases = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCases(searchTerm, statusFilter);
      setCases(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch investigation cases.');
    } finally {
      setLoading(false);
    }
  }, [searchTerm, statusFilter]);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadCases();
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

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 className="page-title">Investigation Cases Directory</h1>
          <p className="page-subtitle">
            Forensic case management, chain-of-custody tracking, and associated digital evidence containers.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="btn btn-secondary"
            onClick={loadCases}
            disabled={loading}
            title="Refresh cases directory"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
          </button>
          <button
            className="btn btn-primary"
            onClick={() => onNavigate('create-case')}
          >
            <FolderPlus size={15} /> Register New Case
          </button>
        </div>
      </div>

      <div className="filter-bar">
        <form onSubmit={handleSearchSubmit} className="search-box-wrapper">
          <Search size={16} className="search-box-icon" />
          <input
            type="text"
            className="search-box-input"
            placeholder="Search by case number (e.g. CASE-2026) or title..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </form>

        <div className="tab-pill-group">
          {(['all', 'active', 'closed', 'archived'] as const).map((st) => (
            <button
              key={st}
              type="button"
              className={`tab-pill ${statusFilter === st ? 'active' : ''}`}
              onClick={() => setStatusFilter(st)}
            >
              {st.charAt(0).toUpperCase() + st.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="alert-banner alert-error">
          <AlertCircle size={18} />
          <div>{error}</div>
        </div>
      )}

      {loading && cases.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
          <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', marginBottom: '12px' }} />
          <p>Loading investigation cases...</p>
        </div>
      ) : cases.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <FolderOpen size={42} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '6px' }}>
            No Investigation Cases Found
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '420px', margin: '0 auto 18px' }}>
            {searchTerm || statusFilter !== 'all'
              ? 'No registered cases match your filter criteria. Try clearing search terms or selecting a different status.'
              : 'No police investigation cases have been registered yet. Create your first case to begin ingesting digital evidence.'}
          </p>
          <button
            className="btn btn-primary"
            onClick={() => onNavigate('create-case')}
          >
            <FolderPlus size={15} /> Register First Case
          </button>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '160px' }}>Case Number</th>
                <th>Case Title & Incident Summary</th>
                <th style={{ width: '180px' }}>Investigator</th>
                <th style={{ width: '110px' }}>Evidence</th>
                <th style={{ width: '120px' }}>Status</th>
                <th style={{ width: '150px' }}>Registered At</th>
                <th style={{ width: '110px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td>
                    <span className="mono" style={{ fontWeight: 600, color: 'var(--primary-blue)' }}>
                      {c.case_number}
                    </span>
                  </td>
                  <td>
                    <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '3px' }}>
                      {c.title}
                    </div>
                    {c.description && (
                      <div
                        style={{
                          fontSize: '12px',
                          color: 'var(--text-muted)',
                          maxWidth: '400px',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {c.description}
                      </div>
                    )}
                  </td>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px' }}>
                      <User size={13} style={{ color: 'var(--text-muted)' }} />
                      {c.investigator_name}
                    </span>
                  </td>
                  <td>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '5px',
                        fontSize: '12px',
                        fontWeight: 600,
                        color: c.evidence_count > 0 ? 'var(--text-main)' : 'var(--text-muted)',
                      }}
                    >
                      <FileCheck size={14} style={{ color: c.evidence_count > 0 ? 'var(--primary-blue)' : 'var(--text-muted)' }} />
                      {c.evidence_count} items
                    </span>
                  </td>
                  <td>
                    <StatusBadge status={c.status.toUpperCase()} />
                  </td>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--text-muted)' }}>
                      <Clock size={12} />
                      {formatDate(c.created_at)}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '4px 10px', fontSize: '12px' }}
                      onClick={() => onNavigate('case-details', c.id)}
                    >
                      <FolderOpen size={13} /> Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
