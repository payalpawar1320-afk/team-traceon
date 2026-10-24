import React, { useState, useEffect, useCallback } from 'react';
import type { PageId, CaseSummary, AuditEventDetail } from '../types';
import { fetchCases, fetchAuditLog } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import {
  ClipboardList,
  Search,
  RotateCcw,
  AlertTriangle,
  User,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';

interface AuditLogPageProps {
  onNavigate: (page: PageId, caseIdentifier?: string | number, evidenceId?: number) => void;
}

export const AuditLogPage: React.FC<AuditLogPageProps> = ({ onNavigate }) => {
  const [events, setEvents] = useState<AuditEventDetail[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  
  // Filters
  const [selectedCaseId, setSelectedCaseId] = useState<string>('all');
  const [selectedAction, setSelectedAction] = useState<string>('all');
  const [selectedResult, setSelectedResult] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedEventId, setExpandedEventId] = useState<number | null>(null);

  // Load cases for filter dropdown
  useEffect(() => {
    fetchCases()
      .then((data) => setCases(data))
      .catch((err) => console.warn('Could not load cases list for audit filters:', err));
  }, []);

  const loadAuditData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetchAuditLog({
        caseId: selectedCaseId !== 'all' ? selectedCaseId : undefined,
        action: selectedAction !== 'all' ? selectedAction : undefined,
        result: selectedResult !== 'all' ? selectedResult : undefined,
        search: searchTerm.trim() || undefined,
        limit: 100,
        offset: 0,
      });
      setEvents(resp.events);
      setTotalCount(resp.total_count);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to retrieve audit log events.');
    } finally {
      setLoading(false);
    }
  }, [selectedCaseId, selectedAction, selectedResult, searchTerm]);

  useEffect(() => {
    loadAuditData();
  }, [loadAuditData]);

  const toggleExpand = (id: number) => {
    setExpandedEventId((prev) => (prev === id ? null : id));
  };

  const getActionBadgeColor = (action: string) => {
    if (action.includes('UPLOAD') || action.includes('CREATE')) return 'bg-blue-50 text-blue-700 border-blue-200';
    if (action.includes('VERIFY') || action.includes('MATCH')) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (action.includes('ANALYSIS') || action.includes('FORENSICS') || action.includes('CROSS')) return 'bg-purple-50 text-purple-700 border-purple-200';
    if (action.includes('REPORT')) return 'bg-indigo-50 text-indigo-700 border-indigo-200';
    return 'bg-gray-50 text-gray-700 border-gray-200';
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-50 text-indigo-700 rounded-lg">
              <ClipboardList size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Chain of Custody & Audit Log</h1>
              <p className="text-sm text-gray-500">
                Chronological record of investigator actions, hash calculations & forensic operations (spec.md §FR-02 &amp; §6)
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={loadAuditData}
          disabled={loading}
          className="btn btn-secondary text-xs flex items-center gap-1.5 self-start md:self-auto"
        >
          <RotateCcw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh Log
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-start gap-3">
          <AlertTriangle className="shrink-0 mt-0.5" size={18} />
          <div>
            <span className="font-semibold">Notice: </span>
            {error}
          </div>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="card bg-white shadow-sm border border-gray-200 rounded-xl p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Case Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1 uppercase tracking-wider">
              Filter by Case
            </label>
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg bg-gray-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">-- All Investigation Cases --</option>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.case_number} ({c.title})
                </option>
              ))}
            </select>
          </div>

          {/* Action Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1 uppercase tracking-wider">
              Filter by Action
            </label>
            <select
              value={selectedAction}
              onChange={(e) => setSelectedAction(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg bg-gray-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">-- All Actions --</option>
              <option value="CASE_CREATE">Case Creation</option>
              <option value="EVIDENCE_UPLOAD">Evidence Ingestion</option>
              <option value="INTEGRITY_VERIFY">SHA-256 Hash Verification</option>
              <option value="IMAGE_FORENSICS">Image Forensics / ELA</option>
              <option value="VIDEO_FORENSICS">Video / CCTV Analysis</option>
              <option value="AUDIO_FORENSICS">Audio Waveform Analysis</option>
              <option value="CROSS_EVIDENCE_COMPARISON">Cross-Evidence Consistency</option>
              <option value="REPORT_GENERATION">PDF Report Generation</option>
              <option value="REPORT_DOWNLOAD">PDF Report Download</option>
            </select>
          </div>

          {/* Result Filter */}
          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1 uppercase tracking-wider">
              Result Status
            </label>
            <select
              value={selectedResult}
              onChange={(e) => setSelectedResult(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg bg-gray-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">-- All Outcomes --</option>
              <option value="success">Success</option>
              <option value="failure">Failure / Error</option>
              <option value="warning">Warning / Alert</option>
            </select>
          </div>

          {/* Keyword Search */}
          <div>
            <label className="block text-[11px] font-semibold text-gray-600 mb-1 uppercase tracking-wider">
              Search Details / Actor
            </label>
            <div className="relative">
              <input
                type="text"
                placeholder="Search action or parameters..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <Search size={13} className="absolute left-2.5 top-2 text-gray-400" />
            </div>
          </div>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="card bg-white shadow-sm border border-gray-200 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <span className="text-xs font-bold text-gray-900 uppercase tracking-wider">
            Chain of Custody Events Log
          </span>
          <span className="text-xs text-gray-500 font-mono">
            Showing {events.length} of {totalCount} total entries
          </span>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            <RotateCcw className="animate-spin inline-block mr-2" size={16} />
            Loading chain-of-custody log records...
          </div>
        ) : events.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            <ClipboardList size={32} className="mx-auto mb-2 text-gray-400" />
            <p className="font-medium text-gray-700">No audit events match the selected criteria.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-gray-600 uppercase text-[11px] font-semibold border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3">Timestamp (UTC)</th>
                  <th className="px-4 py-3">Investigator / Actor</th>
                  <th className="px-4 py-3">Forensic Action</th>
                  <th className="px-4 py-3">Target Reference</th>
                  <th className="px-4 py-3">Result</th>
                  <th className="px-4 py-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 font-normal">
                {events.map((evt) => {
                  const isExpanded = expandedEventId === evt.id;
                  return (
                    <React.Fragment key={evt.id}>
                      <tr className="hover:bg-gray-50/50 transition-colors">
                        <td className="px-4 py-3 text-xs font-mono text-gray-700 whitespace-nowrap">
                          {new Date(evt.created_at).toISOString().replace('T', ' ').substring(0, 19)}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-800">
                          <div className="flex items-center gap-1.5 font-medium">
                            <User size={13} className="text-gray-400" />
                            {evt.actor_id}
                          </div>
                          {evt.ip_address && (
                            <div className="text-[10px] text-gray-400 font-mono pl-4">
                              {evt.ip_address}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-block text-[11px] font-mono font-bold px-2 py-0.5 rounded border ${getActionBadgeColor(
                              evt.action
                            )}`}
                          >
                            {evt.action}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs">
                          {evt.case_number && (
                            <button
                              onClick={() => evt.case_id && onNavigate('case-details', evt.case_id)}
                              className="font-mono text-blue-600 hover:text-blue-800 hover:underline block"
                            >
                              {evt.case_number}
                            </button>
                          )}
                          {evt.evidence_number && (
                            <span className="text-[11px] font-mono text-indigo-700 block">
                              Ev: {evt.evidence_number}
                            </span>
                          )}
                          {!evt.case_number && !evt.evidence_number && (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge
                            status={evt.result.toUpperCase()}
                            variant={evt.result === 'success' ? 'success' : evt.result === 'failure' ? 'danger' : 'warning'}
                          />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => toggleExpand(evt.id)}
                            className="text-xs text-gray-500 hover:text-gray-800 font-medium inline-flex items-center gap-1"
                          >
                            {isExpanded ? (
                              <>
                                Hide <ChevronUp size={12} />
                              </>
                            ) : (
                              <>
                                View <ChevronDown size={12} />
                              </>
                            )}
                          </button>
                        </td>
                      </tr>

                      {/* Expandable JSON Details Drawer */}
                      {isExpanded && (
                        <tr className="bg-gray-50">
                          <td colSpan={6} className="px-6 py-3 border-b border-gray-200">
                            <div className="text-xs space-y-1">
                              <span className="font-semibold text-gray-700 block">
                                Audit Event Recorded Metadata (JSON):
                              </span>
                              <pre className="p-2.5 bg-gray-900 text-gray-100 rounded text-[11px] font-mono overflow-x-auto max-h-48">
                                {evt.details
                                  ? JSON.stringify(evt.details, null, 2)
                                  : evt.details_raw || 'No additional parameters logged.'}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Chain of Custody Storage Boundaries Notice (§6) */}
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 text-xs flex items-start gap-3">
        <Info size={18} className="shrink-0 mt-0.5 text-slate-600" />
        <div className="space-y-1">
          <span className="font-bold text-slate-900 uppercase tracking-wider block">
            Audit Trail Architecture & Integrity Disclosures (spec.md §6 &amp; §15)
          </span>
          <p className="leading-relaxed text-slate-700">
            Audit events in this hackathon prototype are persistently recorded in the backend SQLite relational table (<code>audit_events</code>).
            Consistent with the rules in <code>spec.md §6</code>, this table is NOT falsely advertised as an immutable distributed ledger or blockchain.
            In production deployments, write-once append-only storage (WORM) or cryptographic hash-chained audit ledgers should be configured for statutory admissibility.
          </p>
        </div>
      </div>
    </div>
  );
};
