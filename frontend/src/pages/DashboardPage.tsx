import React, { useState, useEffect } from 'react';
import type { HealthResponse, PageId, CaseStats, CaseSummary } from '../types';
import { fetchCaseStats, fetchCases } from '../api/client';
import {
  FolderPlus,
  Upload,
  ShieldCheck,
  FileSearch,
  FileText,
  GitCompare,
  ClipboardList,
  FolderOpen,
  Clock,
  User,
  ArrowRight,
  HelpCircle,
  CheckCircle2,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';

interface DashboardPageProps {
  health: HealthResponse | null;
  onNavigate: (page: PageId, caseIdentifier?: string | number) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ health, onNavigate }) => {
  const [stats, setStats] = useState<CaseStats | null>(null);
  const [recentCases, setRecentCases] = useState<CaseSummary[]>([]);
  const [loadingData, setLoadingData] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;
    const loadDashboardData = async () => {
      try {
        const [statsData, casesData] = await Promise.all([
          fetchCaseStats().catch(() => null),
          fetchCases().catch(() => []),
        ]);
        if (mounted) {
          if (statsData) setStats(statsData);
          if (casesData) setRecentCases(casesData.slice(0, 5));
        }
      } finally {
        if (mounted) setLoadingData(false);
      }
    };
    loadDashboardData();
    return () => {
      mounted = false;
    };
  }, []);

  const formatDate = (isoStr: string) => {
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div>
      {/* 1. TRACEON Official Hero Section with Blurred Background */}
      <div className="traceon-hero-container">
        {/* Layer 1: Blurred Background Image (10px blur) */}
        <div className="traceon-hero-bg" aria-hidden="true" />
        
        {/* Layer 2: Ambient Dark Overlay for Maximum Contrast & Readability */}
        <div className="traceon-hero-overlay" aria-hidden="true" />

        {/* Layer 3: Foreground Content (Sharp Logo, Typography, and Actions) */}
        <div className="traceon-hero-content">
          <div className="traceon-hero-top">
            <div className="traceon-hero-brand-lockup">
              <div className="traceon-logo-group">
                <img
                  src="/branding/traceon_logo.png"
                  alt="TRACEON Forensic Platform"
                  className="traceon-hero-logo"
                />
                <span className="traceon-hero-brand-name">TRACEON</span>
              </div>
              <div className="traceon-brand-details">
                <div className="traceon-brand-title-row">
                  <span className="traceon-hero-subtitle-badge">
                    Digital Evidence Integrity and Forensic Analysis
                  </span>
                </div>
                <div className="traceon-brand-tagline-row">
                  <span className="traceon-tagline-text">
                    Trace the Evidence. Trust the Process.
                  </span>
                  <span className="traceon-terminal-label">
                    • National Cyber Investigation Terminal
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h1 className="traceon-headline">
              Every File Has a Story. Find the Evidence.
            </h1>
            <p className="traceon-desc">
              Examine digital evidence, review integrity checks, and bring investigation findings together in one traceable workflow.
            </p>
          </div>

          <div className="traceon-hero-actions">
            <button
              onClick={() => onNavigate('create-case')}
              className="traceon-btn-primary"
              title="Initiate a new investigation case"
            >
              <FolderPlus size={16} />
              <span>Start Investigation</span>
            </button>
            <button
              onClick={() => {
                const el = document.getElementById('dashboard-workflow');
                if (el) {
                  el.scrollIntoView({ behavior: 'smooth' });
                } else {
                  onNavigate('my-cases');
                }
              }}
              className="traceon-btn-secondary"
              title="Explore the 5-step forensic workflow and case directory"
            >
              <span>Explore Dashboard</span>
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      </div>

      {/* 2. Guided 5-Step Forensic Workflow Panel */}
      <div id="dashboard-workflow" className="workflow-panel">
        <div className="workflow-header">
          <div>
            <div className="workflow-header-title">
              <Sparkles size={18} color="#470447" />
              <span>How It Works: 5-Step Forensic Workflow</span>
            </div>
            <div className="workflow-header-subtitle">
              Follow this step-by-step sequence to process any digital evidence from intake to final court report.
            </div>
          </div>
          <span className="badge badge-neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <HelpCircle size={12} /> Standard Operating Procedure
          </span>
        </div>

        {/* 5 Step Cards */}
        <div className="workflow-grid">
          {/* Step 1 */}
          <div
            onClick={() => onNavigate('create-case')}
            className="workflow-step-card"
            title="Click to register a new police case container"
          >
            <div>
              <div className="workflow-step-top">
                <span className="workflow-step-number" style={{ backgroundColor: '#470447' }}>1</span>
                <FolderPlus size={18} color="#470447" />
              </div>
              <div className="workflow-step-title">Register Case</div>
              <div className="workflow-step-desc">
                Create official case container with FIR number, incident type, and officer ID.
              </div>
            </div>
            <div className="workflow-step-action" style={{ color: '#470447' }}>
              <span>Start Step 1</span>
              <ChevronRight size={13} />
            </div>
          </div>

          {/* Step 2 */}
          <div
            onClick={() => onNavigate('evidence-upload')}
            className="workflow-step-card"
            title="Click to upload image, video, or audio evidence"
          >
            <div>
              <div className="workflow-step-top">
                <span className="workflow-step-number" style={{ backgroundColor: '#470447' }}>2</span>
                <Upload size={18} color="#470447" />
              </div>
              <div className="workflow-step-title">Ingest Media</div>
              <div className="workflow-step-desc">
                Upload images, CCTV video, or audio files. Computes baseline SHA-256 hash.
              </div>
            </div>
            <div className="workflow-step-action" style={{ color: '#470447' }}>
              <span>Go to Step 2</span>
              <ChevronRight size={13} />
            </div>
          </div>

          {/* Step 3 */}
          <div
            onClick={() => onNavigate('integrity-check')}
            className="workflow-step-card"
            title="Click to re-verify cryptographic hash integrity"
          >
            <div>
              <div className="workflow-step-top">
                <span className="workflow-step-number" style={{ backgroundColor: '#470447' }}>3</span>
                <ShieldCheck size={18} color="#470447" />
              </div>
              <div className="workflow-step-title">Verify Hashes</div>
              <div className="workflow-step-desc">
                Recalculate SHA-256 byte digests on-demand to prove files were not altered.
              </div>
            </div>
            <div className="workflow-step-action" style={{ color: '#470447' }}>
              <span>Go to Step 3</span>
              <ChevronRight size={13} />
            </div>
          </div>

          {/* Step 4 */}
          <div
            onClick={() => onNavigate('analysis-results')}
            className="workflow-step-card"
            title="Click to view deep forensics, ELA, and CCTV duplicate frames"
          >
            <div>
              <div className="workflow-step-top">
                <span className="workflow-step-number" style={{ backgroundColor: '#470447' }}>4</span>
                <FileSearch size={18} color="#470447" />
              </div>
              <div className="workflow-step-title">Forensics & ELA</div>
              <div className="workflow-step-desc">
                Detect Photoshop editing, ELA compression heatmaps, frozen video frames, and waveforms.
              </div>
            </div>
            <div className="workflow-step-action" style={{ color: '#470447' }}>
              <span>Go to Step 4</span>
              <ChevronRight size={13} />
            </div>
          </div>

          {/* Step 5 */}
          <div
            onClick={() => onNavigate('reports')}
            className="workflow-step-card"
            title="Click to generate official court-admissible PDF report"
          >
            <div>
              <div className="workflow-step-top">
                <span className="workflow-step-number" style={{ backgroundColor: '#470447' }}>5</span>
                <FileText size={18} color="#470447" />
              </div>
              <div className="workflow-step-title">Court PDF Report</div>
              <div className="workflow-step-desc">
                Generate official ReportLab PDF with verified SHA-256 digests and audit logs.
              </div>
            </div>
            <div className="workflow-step-action" style={{ color: '#470447' }}>
              <span>Go to Step 5</span>
              <ChevronRight size={13} />
            </div>
          </div>
        </div>
      </div>

      {/* 3. Metrics Metric Cards */}
      <div className="stats-grid">
        <div
          onClick={() => onNavigate('my-cases')}
          className="stat-card"
          style={{ cursor: 'pointer' }}
        >
          <div>
            <div className="stat-card-label">Active Inquiries</div>
            <div className="stat-card-val">
              {loadingData ? '...' : (stats?.active_cases ?? 0)}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--primary-blue)', marginTop: '4px', fontWeight: 600 }}>
              Total Cases: {stats?.total_cases ?? 0} &rarr;
            </div>
          </div>
          <FolderOpen size={24} color="#0284c7" />
        </div>

        <div
          onClick={() => onNavigate('evidence-upload')}
          className="stat-card"
          style={{ cursor: 'pointer' }}
        >
          <div>
            <div className="stat-card-label">Registered Media</div>
            <div className="stat-card-val">
              {loadingData ? '...' : (stats?.total_evidence ?? 0)}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Preserved in private storage
            </div>
          </div>
          <Upload size={24} color="#4f46e5" />
        </div>

        <div
          onClick={() => onNavigate('integrity-check')}
          className="stat-card"
          style={{ cursor: 'pointer' }}
        >
          <div>
            <div className="stat-card-label">SHA-256 Verifications</div>
            <div className="stat-card-val" style={{ color: '#166534' }}>
              {loadingData ? '...' : (stats?.total_evidence ?? 0)}
            </div>
            <div style={{ fontSize: '11px', color: '#166534', marginTop: '4px', fontWeight: 600 }}>
              Audit Hashes on Demand &rarr;
            </div>
          </div>
          <ShieldCheck size={24} color="#16a34a" />
        </div>

        <div className="stat-card">
          <div>
            <div className="stat-card-label">System Health</div>
            <div style={{ marginTop: '6px' }}>
              <StatusBadge status={health?.status === 'healthy' ? 'System Operational' : 'Offline / Checking'} />
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px' }}>
              API v{health?.version || '1.0.0'} (Local SQLite)
            </div>
          </div>
          <CheckCircle2 size={24} color={health?.status === 'healthy' ? '#16a34a' : '#d97706'} />
        </div>
      </div>

      {/* 4. Quick Navigation Bar */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '24px' }}>
        <div style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.5px', marginBottom: '12px' }}>
          Quick Access Functions
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <button onClick={() => onNavigate('create-case')} className="btn btn-primary" style={{ fontSize: '12px', padding: '6px 12px' }}>
            <FolderPlus size={14} /> 1. Register Case
          </button>
          <button onClick={() => onNavigate('evidence-upload')} className="btn btn-secondary" style={{ fontSize: '12px', padding: '6px 12px' }}>
            <Upload size={14} /> 2. Upload Evidence
          </button>
          <button onClick={() => onNavigate('integrity-check')} className="btn btn-secondary" style={{ fontSize: '12px', padding: '6px 12px' }}>
            <ShieldCheck size={14} /> 3. Verify Hashes
          </button>
          <button onClick={() => onNavigate('analysis-results')} className="btn btn-secondary" style={{ fontSize: '12px', padding: '6px 12px' }}>
            <FileSearch size={14} /> 4. Forensic Analysis
          </button>
          <button onClick={() => onNavigate('cross-check')} className="btn btn-secondary" style={{ fontSize: '12px', padding: '6px 12px' }}>
            <GitCompare size={14} /> Cross-Evidence Check
          </button>
          <button onClick={() => onNavigate('reports')} className="btn btn-secondary" style={{ fontSize: '12px', padding: '6px 12px' }}>
            <FileText size={14} /> 5. PDF Reports
          </button>
          <button onClick={() => onNavigate('audit-log')} className="btn btn-secondary" style={{ fontSize: '12px', padding: '6px 12px' }}>
            <ClipboardList size={14} /> Chain of Custody Log
          </button>
        </div>
      </div>

      {/* 5. Recent Cases Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="card-header" style={{ padding: '16px 20px', margin: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FolderOpen size={16} color="var(--primary-blue)" />
            <h2 className="card-title" style={{ margin: 0 }}>Recent Investigation Cases</h2>
          </div>
          <button
            onClick={() => onNavigate('my-cases')}
            className="btn btn-secondary"
            style={{ fontSize: '12px', padding: '4px 10px' }}
          >
            View All Cases <ArrowRight size={12} />
          </button>
        </div>

        {recentCases.length === 0 ? (
          <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <FolderOpen size={36} style={{ margin: '0 auto 10px auto', opacity: 0.5 }} />
            <p style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '14px' }}>No investigation cases registered yet.</p>
            <p style={{ fontSize: '12px', marginTop: '4px' }}>Follow Step 1 above to register your first investigation case container.</p>
            <button
              onClick={() => onNavigate('create-case')}
              className="btn btn-primary"
              style={{ marginTop: '16px', fontSize: '12px' }}
            >
              <FolderPlus size={14} /> Register First Case
            </button>
          </div>
        ) : (
          <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Case Identifier</th>
                  <th>Title / Incident</th>
                  <th>Investigating Officer</th>
                  <th>Evidence</th>
                  <th>Status</th>
                  <th>Registered</th>
                  <th style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {recentCases.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <span className="mono" style={{ fontWeight: 700, color: 'var(--primary-blue)' }}>{c.case_number}</span>
                    </td>
                    <td style={{ fontWeight: 500 }}>{c.title}</td>
                    <td style={{ fontSize: '12px' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <User size={13} color="#94a3b8" />
                        {c.investigator_name}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{c.evidence_count} item(s)</td>
                    <td>
                      <StatusBadge status={c.status.toUpperCase()} />
                    </td>
                    <td className="mono" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={12} color="#94a3b8" />
                        {formatDate(c.created_at)}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => onNavigate('case-details', c.id)}
                        className="btn btn-secondary"
                        style={{ fontSize: '11px', padding: '3px 8px' }}
                      >
                        Open Case &rarr;
                      </button>
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
