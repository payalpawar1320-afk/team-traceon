import React from 'react';
import { RefreshCw, Server } from 'lucide-react';
import type { HealthResponse, PageId } from '../types';

interface TopbarProps {
  currentPage: PageId;
  health: HealthResponse | null;
  loadingHealth: boolean;
  onRefreshHealth: () => void;
}

const PAGE_TITLES: Record<PageId, string> = {
  dashboard: 'Forensic Operations Dashboard',
  'create-case': 'Register Investigation Case',
  'my-cases': 'Investigation Cases Directory',
  'case-details': 'Case Overview & Evidence Repository',
  'evidence-upload': 'Secure Evidence Ingestion',
  'evidence-details': 'Evidence Item Inspection',
  'analysis-results': 'Explainable Forensic Findings',
  'integrity-check': 'SHA-256 Byte Verification',
  'cross-check': 'Cross-Evidence Consistency Analysis',
  reports: 'Forensic PDF Report Generation',
  'audit-log': 'Chain-of-Custody & Audit Trail',
  settings: 'System Configuration & Limitations',
};

export const Topbar: React.FC<TopbarProps> = ({
  currentPage,
  health,
  loadingHealth,
  onRefreshHealth,
}) => {
  const currentTitle = PAGE_TITLES[currentPage] || 'Forensic Platform';

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <img
            src="/branding/traceon_logo.png"
            alt="TRACEON"
            style={{
              width: '24px',
              height: '24px',
              objectFit: 'contain',
              borderRadius: '4px',
              border: '1px solid #cbd5e1',
              background: '#0f172a',
              padding: '1.5px',
              flexShrink: 0,
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)'
            }}
          />
          <span style={{ fontWeight: 700, letterSpacing: '0.5px', color: '#0f172a' }}>TRACEON</span>
          <span style={{ color: '#94a3b8' }}>/</span>
          <span className="breadcrumb-current">{currentTitle}</span>
        </div>
      </div>

      <div className="topbar-right">
        {/* System Health Status Indicator */}
        <div
          className={`health-pill ${health?.status || 'unhealthy'}`}
          title={
            health
              ? `DB: ${health.database_connected ? 'Connected' : 'Disconnected'} | Storage: ${
                  health.storage_verified ? 'Verified' : 'Error'
                }`
              : 'Connecting to backend...'
          }
        >
          <span className={`indicator-dot ${health?.status || 'unhealthy'}`} />
          <Server size={12} style={{ marginLeft: 2 }} />
          <span>
            {health ? (health.status === 'healthy' ? 'System Operational' : 'Degraded') : 'Backend Offline'}
          </span>
          <button
            onClick={onRefreshHealth}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              padding: 0,
              marginLeft: 4,
              color: 'inherit',
            }}
            title="Refresh system health"
          >
            <RefreshCw size={11} className={loadingHealth ? 'spin' : ''} />
          </button>
        </div>

        {/* User Identity / Access Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
          <span
            style={{
              backgroundColor: '#f1f5f9',
              padding: '4px 8px',
              borderRadius: '4px',
              fontWeight: 600,
              color: '#334155',
              border: '1px solid #cbd5e1',
            }}
          >
            Investigator Terminal
          </span>
        </div>
      </div>
    </header>
  );
};
