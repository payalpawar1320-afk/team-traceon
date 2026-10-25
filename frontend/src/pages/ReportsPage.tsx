import React, { useState, useEffect, useCallback } from 'react';
import type { PageId, CaseSummary, ReportItem } from '../types';
import { fetchCases, fetchCaseReports, generateCaseReport, getReportDownloadUrl } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import {
  FileText,
  Download,
  PlusCircle,
  RotateCcw,
  AlertTriangle,
  Folder,
  FileCheck2,
  Calendar,
  HardDrive,
  Info,
  CheckCircle2,
} from 'lucide-react';

interface ReportsPageProps {
  initialCaseId?: string | number | null;
  onNavigate: (page: PageId, caseIdentifier?: string | number, evidenceId?: number) => void;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ initialCaseId, onNavigate }) => {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | number | ''>(initialCaseId || '');
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loadingCases, setLoadingCases] = useState<boolean>(true);
  const [loadingReports, setLoadingReports] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Generation options
  const [includeAuditTrail, setIncludeAuditTrail] = useState<boolean>(true);
  const [investigatorNotes, setInvestigatorNotes] = useState<string>('');

  // 1. Load list of cases
  useEffect(() => {
    let mounted = true;
    const loadCasesList = async () => {
      setLoadingCases(true);
      try {
        const data = await fetchCases();
        if (mounted) {
          setCases(data);
          if (!selectedCaseId && data.length > 0) {
            setSelectedCaseId(data[0].id);
          }
        }
      } catch (err: unknown) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to retrieve cases.');
        }
      } finally {
        if (mounted) setLoadingCases(false);
      }
    };
    loadCasesList();
    return () => {
      mounted = false;
    };
  }, []);

  // 2. Load reports when case is selected
  const loadReports = useCallback(async (caseId: string | number) => {
    setLoadingReports(true);
    setError(null);
    try {
      const data = await fetchCaseReports(caseId);
      setReports(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load case reports.');
      setReports([]);
    } finally {
      setLoadingReports(false);
    }
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      loadReports(selectedCaseId);
    }
  }, [selectedCaseId, loadReports]);

  // Handle generation of new PDF report
  const handleGenerateReport = async () => {
    if (!selectedCaseId) return;
    setGenerating(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const newReport = await generateCaseReport(selectedCaseId, {
        include_all_evidence: true,
        include_audit_trail: includeAuditTrail,
        notes: investigatorNotes.trim() || undefined,
      });
      setSuccessMessage(`Forensic PDF report ${newReport.report_number} generated successfully.`);
      setInvestigatorNotes('');
      await loadReports(selectedCaseId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate report.');
    } finally {
      setGenerating(false);
    }
  };

  const selectedCaseObj = cases.find((c) => String(c.id) === String(selectedCaseId));

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-blue-50 text-blue-700 rounded-lg">
              <FileText size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Forensic PDF Reports</h1>
              <p className="text-sm text-gray-500">
                Generate and download authoritative forensic examination summaries (spec.md §FR-10)
              </p>
            </div>
          </div>
        </div>

        {selectedCaseId && (
          <button
            onClick={() => onNavigate('case-details', selectedCaseId)}
            className="btn btn-secondary text-xs flex items-center gap-1.5 self-start md:self-auto"
          >
            <Folder size={14} />
            View Active Case
          </button>
        )}
      </div>

      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2.5 text-xs text-blue-900">
        <span className="bg-blue-600 text-white font-bold px-2 py-0.5 rounded text-[10px] tracking-wider uppercase">
          STEP 5 OF 5
        </span>
        <span>
          <strong>Forensic Examination Report:</strong> Compile all verified digital fingerprints (SHA-256), multi-modal analysis findings, and chain-of-custody audit logs into a clear, structured PDF examination report.
        </span>
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

      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-sm flex items-center gap-2">
          <CheckCircle2 size={18} className="text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Case Selector and Generator Controls */}
      <div className="card bg-white shadow-sm border border-gray-200 rounded-xl p-5 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Case Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5 uppercase tracking-wider">
              Investigation Case
            </label>
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              disabled={loadingCases || generating}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="" disabled>
                {loadingCases ? 'Loading cases...' : '-- Choose an Investigation Case --'}
              </option>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.case_number} — {c.title} ({c.evidence_count} evidence items)
                </option>
              ))}
            </select>
          </div>

          {/* Quick Case Metadata */}
          {selectedCaseObj && (
            <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg flex flex-wrap items-center justify-between gap-3 text-xs">
              <div>
                <span className="text-gray-400 block">Lead Investigator:</span>
                <span className="font-semibold text-gray-800">{selectedCaseObj.investigator_name}</span>
              </div>
              <div>
                <span className="text-gray-400 block">Status:</span>
                <StatusBadge status={selectedCaseObj.status.toUpperCase()} />
              </div>
              <div>
                <span className="text-gray-400 block">Evidence Registered:</span>
                <span className="font-semibold text-gray-800">{selectedCaseObj.evidence_count} item(s)</span>
              </div>
            </div>
          )}
        </div>

        {/* Generator Form Section */}
        <div className="pt-4 border-t border-gray-200 grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="md:col-span-2 space-y-3">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1 uppercase tracking-wider">
                Investigative Remarks & Notes (Optional)
              </label>
              <textarea
                value={investigatorNotes}
                onChange={(e) => setInvestigatorNotes(e.target.value)}
                placeholder="Include initial impressions, forensic laboratory observations, or chain of custody notes to be rendered into the PDF report..."
                rows={2}
                maxLength={1000}
                className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="includeAuditTrailCheck"
                checked={includeAuditTrail}
                onChange={(e) => setIncludeAuditTrail(e.target.checked)}
                className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
              />
              <label htmlFor="includeAuditTrailCheck" className="text-xs text-gray-700 select-none cursor-pointer">
                Include recent chain-of-custody audit log entries in the document
              </label>
            </div>
          </div>

          <div className="flex flex-col justify-end">
            <button
              onClick={handleGenerateReport}
              disabled={generating || !selectedCaseId}
              className="btn btn-primary flex items-center justify-center gap-2 py-3 font-semibold shadow-sm"
            >
              {generating ? (
                <>
                  <RotateCcw className="animate-spin" size={16} />
                  Compiling ReportLab PDF...
                </>
              ) : (
                <>
                  <PlusCircle size={16} />
                  Generate Forensic PDF Report
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Reports Catalog */}
      <div className="card bg-white shadow-sm border border-gray-200 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileCheck2 size={18} className="text-blue-600" />
            <h2 className="text-base font-bold text-gray-900">Generated Reports Archive</h2>
          </div>
          <span className="text-xs text-gray-500 font-mono">
            {reports.length} report(s) available
          </span>
        </div>

        {loadingReports ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            <RotateCcw className="animate-spin inline-block mr-2" size={16} />
            Loading reports catalog...
          </div>
        ) : reports.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            <FileText size={32} className="mx-auto mb-2 text-gray-400" />
            <p className="font-medium text-gray-700">No reports generated for this case yet.</p>
            <p className="text-xs text-gray-400 mt-1">
              Click &quot;Generate Forensic PDF Report&quot; above to compile an examination document.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-gray-600 uppercase text-[11px] font-semibold border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3">Report Number</th>
                  <th className="px-4 py-3">Generated Date</th>
                  <th className="px-4 py-3">File Size</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 font-normal">
                {reports.map((rep) => (
                  <tr key={rep.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-mono font-bold text-blue-700">{rep.report_number}</div>
                      <div className="text-xs text-gray-500 truncate max-w-xs">{rep.report_filename}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-700">
                      <div className="flex items-center gap-1.5">
                        <Calendar size={13} className="text-gray-400" />
                        {new Date(rep.generated_at).toLocaleString()}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-gray-600">
                      <div className="flex items-center gap-1.5">
                        <HardDrive size={13} className="text-gray-400" />
                        {rep.file_size_bytes ? `${(rep.file_size_bytes / 1024).toFixed(1)} KB` : 'N/A'}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={rep.report_status.toUpperCase()} variant="success" />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <a
                        href={getReportDownloadUrl(rep.id)}
                        download={rep.report_filename}
                        className="btn btn-secondary inline-flex items-center gap-1.5 text-xs py-1.5 px-3 font-medium text-blue-700 hover:text-blue-900 hover:bg-blue-50"
                      >
                        <Download size={13} />
                        Download PDF
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Statutory Disclaimer & Boundaries Banner */}
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 text-xs flex items-start gap-3">
        <Info size={18} className="shrink-0 mt-0.5 text-slate-600" />
        <div className="space-y-1">
          <span className="font-bold text-slate-900 uppercase tracking-wider block">
            Forensic Report Boundaries & Guidelines (spec.md §FR-10 &amp; §15)
          </span>
          <p className="leading-relaxed text-slate-700">
            PDF reports produced by TRACEON are investigator-facing working documents designed to systematically record
            cryptographic digests (SHA-256), observed EXIF and media attributes, and explainable manipulation indicators.
            They are demonstration prototype outputs and do not represent certified judicial certificates under Section 65B of the Indian Evidence Act.
            Always maintain proper physical custody logs and corroborate findings with original hardware inspection.
          </p>
        </div>
      </div>
    </div>
  );
};
