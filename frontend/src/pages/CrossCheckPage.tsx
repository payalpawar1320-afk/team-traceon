import React, { useState, useEffect, useCallback } from 'react';
import type {
  PageId,
  CaseSummary,
  EvidenceItem,
  CrossEvidenceComparisonResponse,
  FieldComparison,
} from '../types';
import { fetchCases, fetchCaseById, compareCrossEvidence } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import {
  GitCompare,
  Clock,
  Camera,
  MapPin,
  Cpu,
  Layers,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  ShieldAlert,
  Calendar,
  FileText,
  RotateCcw,
  Maximize2,
  ChevronRight,
  Info,
} from 'lucide-react';

interface CrossCheckPageProps {
  initialCaseId?: string | number | null;
  onNavigate: (page: PageId, caseIdentifier?: string | number, evidenceId?: number) => void;
}

export const CrossCheckPage: React.FC<CrossCheckPageProps> = ({
  initialCaseId,
  onNavigate,
}) => {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | number | ''>(initialCaseId || '');
  const [caseEvidence, setCaseEvidence] = useState<EvidenceItem[]>([]);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<number[]>([]);
  const [timeTolerance, setTimeTolerance] = useState<number>(60);
  
  const [loadingCases, setLoadingCases] = useState<boolean>(true);
  const [loadingEvidence, setLoadingEvidence] = useState<boolean>(false);
  const [comparing, setComparing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [comparisonResult, setComparisonResult] = useState<CrossEvidenceComparisonResponse | null>(null);

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

  // 2. Load evidence items when a case is selected
  const loadCaseEvidence = useCallback(async (caseId: string | number) => {
    setLoadingEvidence(true);
    setError(null);
    setComparisonResult(null);
    try {
      const caseDetail = await fetchCaseById(caseId);
      const items = caseDetail.evidence_items || [];
      setCaseEvidence(items);
      // Automatically preselect all evidence if between 2 and 4 items
      if (items.length >= 2 && items.length <= 4) {
        setSelectedEvidenceIds(items.map((e) => e.id));
      } else {
        setSelectedEvidenceIds([]);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load case evidence.');
      setCaseEvidence([]);
      setSelectedEvidenceIds([]);
    } finally {
      setLoadingEvidence(false);
    }
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      loadCaseEvidence(selectedCaseId);
    }
  }, [selectedCaseId, loadCaseEvidence]);

  const handleToggleEvidence = (id: number) => {
    setSelectedEvidenceIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSelectAll = () => {
    setSelectedEvidenceIds(caseEvidence.map((e) => e.id));
  };

  const handleClearSelection = () => {
    setSelectedEvidenceIds([]);
  };

  const handleRunComparison = async () => {
    if (!selectedCaseId || selectedEvidenceIds.length < 2) return;
    setComparing(true);
    setError(null);
    try {
      const result = await compareCrossEvidence(selectedCaseId, {
        evidence_ids: selectedEvidenceIds,
        time_tolerance_seconds: timeTolerance,
      });
      setComparisonResult(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Cross-evidence comparison failed.');
    } finally {
      setComparing(false);
    }
  };

  const getDimensionIcon = (fieldId: string) => {
    switch (fieldId) {
      case 'capture_timestamp':
        return <Clock size={16} className="text-blue-500" />;
      case 'device_hardware':
        return <Camera size={16} className="text-indigo-500" />;
      case 'software_footprint':
        return <Cpu size={16} className="text-purple-500" />;
      case 'gps_proximity':
        return <MapPin size={16} className="text-emerald-500" />;
      case 'dimensions_resolution':
        return <Maximize2 size={16} className="text-amber-500" />;
      default:
        return <Layers size={16} className="text-gray-500" />;
    }
  };

  const getStatusBadgeVariant = (status: FieldComparison['status']) => {
    switch (status) {
      case 'consistent':
        return 'success';
      case 'inconsistent':
        return 'danger';
      case 'missing_data':
        return 'warning';
      default:
        return 'neutral';
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-50 text-indigo-700 rounded-lg">
              <GitCompare size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Cross-Evidence Consistency Analysis
              </h1>
              <p className="text-sm text-gray-500">
                Multi-evidence forensic timeline reconciliation, device origin verification & discrepancy detection (spec.md §FR-08)
              </p>
            </div>
          </div>
        </div>

        {selectedCaseId && (
          <button
            onClick={() => onNavigate('case-details', selectedCaseId)}
            className="btn btn-secondary text-xs flex items-center gap-1.5 self-start md:self-auto"
          >
            <FileText size={14} />
            View Case Details
          </button>
        )}
      </div>

      <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-lg flex items-center gap-2.5 text-xs text-indigo-950">
        <span className="bg-indigo-600 text-white font-bold px-2 py-0.5 rounded text-[10px] tracking-wider uppercase">
          COMPARATIVE AUDIT
        </span>
        <span>
          <strong>Cross-Evidence Correlation:</strong> Select 2 or more files from the same case to automatically reconcile timestamps, compare camera/device models, detect editing footprints, and audit GPS proximity.
        </span>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-start gap-3">
          <AlertTriangle className="shrink-0 mt-0.5" size={18} />
          <div>
            <span className="font-semibold">Analysis Notice: </span>
            {error}
          </div>
        </div>
      )}

      {/* Case and Selection Controls Card */}
      <div className="card bg-white shadow-sm border border-gray-200 rounded-xl p-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Case Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5 uppercase tracking-wider">
              1. Select Investigation Case
            </label>
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              disabled={loadingCases}
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

          {/* Time Tolerance Input */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1.5 uppercase tracking-wider">
              2. Timestamp Tolerance Window
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="0"
                max="86400"
                step="10"
                value={timeTolerance}
                onChange={(e) => setTimeTolerance(Math.max(0, parseInt(e.target.value) || 0))}
                className="w-32 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-xs text-gray-500">
                seconds (flags captures &gt; {timeTolerance}s apart)
              </span>
            </div>
          </div>

          {/* Action Button */}
          <div className="flex flex-col justify-end">
            <button
              onClick={handleRunComparison}
              disabled={comparing || selectedEvidenceIds.length < 2}
              className={`btn ${
                selectedEvidenceIds.length >= 2 ? 'btn-primary' : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              } flex items-center justify-center gap-2 w-full py-2.5 font-medium`}
            >
              {comparing ? (
                <>
                  <RotateCcw className="animate-spin" size={16} />
                  Evaluating Cross-Correlations...
                </>
              ) : (
                <>
                  <GitCompare size={16} />
                  Run Cross-Evidence Check ({selectedEvidenceIds.length} Selected)
                </>
              )}
            </button>
          </div>
        </div>

        {/* Evidence Selection Grid */}
        <div className="mt-5 pt-5 border-t border-gray-200">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
              3. Check Evidence Items to Compare (Minimum 2 required)
            </span>
            <div className="flex items-center gap-3 text-xs">
              <button
                type="button"
                onClick={handleSelectAll}
                disabled={caseEvidence.length === 0}
                className="text-blue-600 hover:text-blue-800 font-medium"
              >
                Select All ({caseEvidence.length})
              </button>
              <span className="text-gray-300">|</span>
              <button
                type="button"
                onClick={handleClearSelection}
                disabled={selectedEvidenceIds.length === 0}
                className="text-gray-600 hover:text-gray-800"
              >
                Clear
              </button>
            </div>
          </div>

          {loadingEvidence ? (
            <div className="py-8 text-center text-gray-500 text-sm">
              <RotateCcw className="animate-spin inline-block mr-2" size={16} />
              Loading case evidence catalog...
            </div>
          ) : caseEvidence.length === 0 ? (
            <div className="p-6 text-center bg-gray-50 rounded-lg border border-dashed border-gray-300 text-gray-500 text-sm">
              <Layers size={24} className="mx-auto mb-2 text-gray-400" />
              No evidence files registered in this case yet.{' '}
              {selectedCaseId && (
                <button
                  onClick={() => onNavigate('evidence-upload', selectedCaseId)}
                  className="text-blue-600 underline font-medium"
                >
                  Upload Evidence Now
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {caseEvidence.map((ev) => {
                const isSelected = selectedEvidenceIds.includes(ev.id);
                return (
                  <div
                    key={ev.id}
                    onClick={() => handleToggleEvidence(ev.id)}
                    className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 select-none ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-50/50 ring-1 ring-indigo-500'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}} // Controlled by container onClick
                      className="mt-1 h-4 w-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-xs font-mono font-bold text-gray-800">
                          {ev.evidence_number}
                        </span>
                        <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                          {ev.detected_file_type}
                        </span>
                      </div>
                      <p className="text-xs font-medium text-gray-900 truncate mt-0.5">
                        {ev.original_filename}
                      </p>
                      <p className="text-[11px] text-gray-500 font-mono mt-0.5 truncate">
                        {(ev.file_size / 1024).toFixed(1)} KB • {ev.sha256_hash.substring(0, 12)}...
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Comparison Results */}
      {comparisonResult && (
        <div className="space-y-6">
          {/* Executive Summary Metric Banners */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
              <span className="text-xs text-gray-500 font-medium">Overall Alignment</span>
              <div className="mt-1.5 flex items-center gap-2">
                {comparisonResult.summary.overall_status === 'consistent' ? (
                  <CheckCircle2 size={20} className="text-emerald-600" />
                ) : comparisonResult.summary.overall_status === 'inconsistencies_detected' ? (
                  <ShieldAlert size={20} className="text-amber-600" />
                ) : (
                  <HelpCircle size={20} className="text-gray-500" />
                )}
                <span className="text-sm font-bold text-gray-900 capitalize">
                  {comparisonResult.summary.overall_status.replace(/_/g, ' ')}
                </span>
              </div>
            </div>

            <div className="card p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
              <span className="text-xs text-gray-500 font-medium">Items Cross-Examined</span>
              <div className="mt-1.5 text-xl font-bold text-gray-900">
                {comparisonResult.compared_evidence_ids.length}{' '}
                <span className="text-xs text-gray-400 font-normal">Files</span>
              </div>
            </div>

            <div className="card p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
              <span className="text-xs text-gray-500 font-medium">Consistent Dimensions</span>
              <div className="mt-1.5 text-xl font-bold text-emerald-700">
                {comparisonResult.summary.consistent_count}{' '}
                <span className="text-xs text-gray-400 font-normal">
                  / {comparisonResult.summary.total_fields_evaluated}
                </span>
              </div>
            </div>

            <div className="card p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
              <span className="text-xs text-gray-500 font-medium">Inconsistencies Flagged</span>
              <div className="mt-1.5 text-xl font-bold text-red-600">
                {comparisonResult.summary.inconsistent_count}{' '}
                <span className="text-xs text-gray-400 font-normal">Requiring review</span>
              </div>
            </div>
          </div>

          {/* Chronological Unified Forensic Timeline */}
          <div className="card bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-4 pb-2 border-b border-gray-100">
              <Calendar size={18} className="text-blue-600" />
              <h2 className="text-base font-bold text-gray-900">
                Unified Chronological Event Timeline
              </h2>
              <span className="text-xs text-gray-500 ml-auto">
                {comparisonResult.timeline.length} sequenced timeline points
              </span>
            </div>

            <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200">
              {comparisonResult.timeline.map((evt, idx) => (
                <div key={idx} className="relative group">
                  {/* Timeline dot */}
                  <div
                    className={`absolute -left-6 top-1.5 w-3 h-3 rounded-full border-2 border-white shadow-sm ${
                      evt.event_type.includes('Capture')
                        ? 'bg-blue-600 ring-2 ring-blue-100'
                        : evt.event_type.includes('Modification')
                        ? 'bg-amber-500'
                        : 'bg-emerald-600'
                    }`}
                  />
                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 hover:border-blue-300 transition-colors">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-mono font-bold text-gray-900">
                        {evt.timestamp_str}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-gray-200 text-gray-700">
                          {evt.event_type}
                        </span>
                        <span className="text-[10px] font-mono font-bold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">
                          {evt.evidence_number}
                        </span>
                      </div>
                    </div>
                    <div className="text-xs font-medium text-gray-800 mt-1">
                      {evt.filename}
                    </div>
                    <p className="text-xs text-gray-600 mt-0.5">{evt.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Forensic Comparison Matrix Table */}
          <div className="card bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
            <div className="p-5 border-b border-gray-200">
              <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                <GitCompare size={18} className="text-indigo-600" />
                Comparative Forensic Matrix
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Evaluation of metadata alignment, device consistency, and potential anomalies across selected evidence.
              </p>
            </div>

            <div className="divide-y divide-gray-200">
              {comparisonResult.comparison_matrix.map((field) => (
                <div key={field.field_id} className="p-5 hover:bg-gray-50/50 transition-colors">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2">
                      {getDimensionIcon(field.field_id)}
                      <span className="text-sm font-bold text-gray-900">{field.field_label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge
                        status={field.status.replace(/_/g, ' ').toUpperCase()}
                        variant={getStatusBadgeVariant(field.status)}
                      />
                      {field.delta_or_diff && (
                        <span className="text-xs font-mono bg-gray-100 text-gray-700 px-2 py-0.5 rounded border border-gray-200">
                          {field.delta_or_diff}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Observed Values per Evidence */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 my-2.5">
                    {Object.entries(field.values_by_evidence).map(([evNum, val]) => (
                      <div
                        key={evNum}
                        className="p-2 bg-gray-50 rounded border border-gray-200 text-xs font-mono"
                      >
                        <span className="font-bold text-indigo-700 block text-[11px] mb-0.5">
                          {evNum}:
                        </span>
                        <span className="text-gray-800 break-words">{String(val)}</span>
                      </div>
                    ))}
                  </div>

                  {/* Explainable Findings & Plausible Causes */}
                  <div className="mt-3 text-xs bg-blue-50/50 p-3 rounded-lg border border-blue-100 space-y-2">
                    <div>
                      <span className="font-semibold text-blue-900">
                        {field.finding_title}:{' '}
                      </span>
                      <span className="text-blue-950">{field.explanation}</span>
                    </div>

                    {field.plausible_causes && field.plausible_causes.length > 0 && (
                      <div className="pt-2 border-t border-blue-100/60">
                        <span className="font-semibold text-blue-900 block mb-1">
                          Plausible Alternative Explanations (spec.md §FR-08):
                        </span>
                        <ul className="list-disc pl-4 space-y-0.5 text-blue-900/90 text-[11px]">
                          {field.plausible_causes.map((cause, cIdx) => (
                            <li key={cIdx}>{cause}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Compared Evidence Summary Cards */}
          <div className="card bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 mb-3 flex items-center gap-2">
              <Layers size={16} className="text-gray-600" />
              Extracted Attribute Registry
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {comparisonResult.evidence_summaries.map((summary) => (
                <div
                  key={summary.evidence_id}
                  className="p-4 rounded-lg border border-gray-200 bg-gray-50/50 text-xs space-y-2"
                >
                  <div className="flex items-center justify-between border-b border-gray-200 pb-2">
                    <span className="font-mono font-bold text-indigo-700">
                      {summary.evidence_number}
                    </span>
                    <button
                      onClick={() => onNavigate('evidence-details', undefined, summary.evidence_id)}
                      className="text-blue-600 hover:text-blue-800 font-medium flex items-center gap-0.5"
                    >
                      Inspect <ChevronRight size={12} />
                    </button>
                  </div>

                  <div className="font-medium text-gray-900 truncate">
                    {summary.original_filename}
                  </div>

                  <div className="grid grid-cols-2 gap-1 text-[11px] text-gray-600 pt-1">
                    <div>
                      <span className="text-gray-400 block">Device:</span>
                      <span className="font-medium text-gray-800">{summary.device_label}</span>
                    </div>
                    <div>
                      <span className="text-gray-400 block">Format / Res:</span>
                      <span className="font-medium text-gray-800">
                        {summary.dimensions || summary.file_type}
                      </span>
                    </div>
                    <div className="col-span-2 pt-1">
                      <span className="text-gray-400 block">Capture Time:</span>
                      <span className="font-mono text-gray-800">
                        {summary.capture_timestamp_raw || 'No EXIF datetime'}
                      </span>
                    </div>
                    {summary.software_footprint && (
                      <div className="col-span-2 pt-1 text-red-600">
                        <span className="font-semibold block">Software Footprint:</span>
                        <span>{summary.software_footprint}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Statutory Forensic Limitations Disclaimer (spec.md §FR-08) */}
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-xs flex items-start gap-3">
            <Info size={18} className="shrink-0 mt-0.5 text-amber-700" />
            <div className="space-y-1">
              <span className="font-bold text-amber-950 uppercase tracking-wider block">
                Forensic Analysis Boundaries & Guidelines
              </span>
              <p className="leading-relaxed">{comparisonResult.limitations}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
