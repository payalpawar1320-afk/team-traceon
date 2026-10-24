import React from 'react';
import {
  LayoutDashboard,
  FolderPlus,
  Folder,
  Upload,
  ShieldCheck,
  FileSearch,
  Layers,
  FileText,
  ClipboardList,
  Settings,
} from 'lucide-react';
import type { PageId } from '../types';

interface SidebarProps {
  currentPage: PageId;
  onNavigate: (page: PageId) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentPage, onNavigate }) => {
  return (
    <aside className="sidebar">
      {/* Header with Official TRACEON Logo */}
      <div className="sidebar-header" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '16px 18px', background: '#e2e8f0', borderBottom: '1px solid #cbd5e1' }}>
        <img
          src="/branding/traceon_logo.png"
          alt="TRACEON"
          style={{
            width: '38px',
            height: '38px',
            objectFit: 'contain',
            borderRadius: '6px',
            border: '1.5px solid #94a3b8',
            background: '#0f172a',
            padding: '2px',
            flexShrink: 0,
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}
        />
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className="sidebar-title" style={{ letterSpacing: '0.6px', fontWeight: 800, fontSize: '16px', color: '#0f172a' }}>
              TRACEON
            </span>
            <span
              style={{
                background: '#e0f2fe',
                border: '1px solid #bae6fd',
                color: '#0284c7',
                fontSize: '9px',
                fontWeight: 700,
                letterSpacing: '0.6px',
                padding: '1px 5px',
                borderRadius: '3px',
              }}
            >
              CORE
            </span>
          </div>
          <div className="sidebar-subtitle" style={{ fontSize: '10px', color: '#475569', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 500 }}>
            Digital Evidence Integrity
          </div>
        </div>
      </div>

      {/* Navigation Sections */}
      <nav className="sidebar-nav">
        <div className="nav-section-title">Home</div>
        <button
          className={`nav-item ${currentPage === 'dashboard' ? 'active' : ''}`}
          onClick={() => onNavigate('dashboard')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
        >
          <LayoutDashboard size={16} />
          <span>Dashboard Overview</span>
        </button>

        <div className="nav-section-title">Investigation Workflow (1 &rarr; 5)</div>
        <button
          className={`nav-item ${currentPage === 'create-case' ? 'active' : ''}`}
          onClick={() => onNavigate('create-case')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
          title="Step 1: Register an official investigation case"
        >
          <FolderPlus size={16} />
          <span>1. Register Case</span>
        </button>
        <button
          className={`nav-item ${currentPage === 'evidence-upload' ? 'active' : ''}`}
          onClick={() => onNavigate('evidence-upload')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
          title="Step 2: Ingest digital evidence with SHA-256 baseline"
        >
          <Upload size={16} />
          <span>2. Ingest Evidence</span>
        </button>
        <button
          className={`nav-item ${currentPage === 'integrity-check' ? 'active' : ''}`}
          onClick={() => onNavigate('integrity-check')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
          title="Step 3: Recalculate and verify SHA-256 hash match"
        >
          <ShieldCheck size={16} />
          <span>3. Verify SHA-256</span>
        </button>
        <button
          className={`nav-item ${currentPage === 'analysis-results' ? 'active' : ''}`}
          onClick={() => onNavigate('analysis-results')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
          title="Step 4: Image ELA, CCTV duplicate frames & audio waveforms"
        >
          <FileSearch size={16} />
          <span>4. Forensic Analysis</span>
        </button>
        <button
          className={`nav-item ${currentPage === 'cross-check' ? 'active' : ''}`}
          onClick={() => onNavigate('cross-check')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
          title="Compare multiple evidence items within the same case"
        >
          <Layers size={16} />
          <span>Cross-Evidence Check</span>
        </button>
        <button
          className={`nav-item ${currentPage === 'reports' ? 'active' : ''}`}
          onClick={() => onNavigate('reports')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
          title="Step 5: Generate and download court-ready PDF examination report"
        >
          <FileText size={16} />
          <span>5. Court PDF Reports</span>
        </button>

        <div className="nav-section-title">Case Registry & Chain of Custody</div>
        <button
          className={`nav-item ${currentPage === 'my-cases' ? 'active' : ''}`}
          onClick={() => onNavigate('my-cases')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
        >
          <Folder size={16} />
          <span>Cases Directory</span>
        </button>
        <button
          className={`nav-item ${currentPage === 'audit-log' ? 'active' : ''}`}
          onClick={() => onNavigate('audit-log')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
        >
          <ClipboardList size={16} />
          <span>Chain of Custody Log</span>
        </button>

        <div className="nav-section-title">System & Help</div>
        <button
          className={`nav-item ${currentPage === 'settings' ? 'active' : ''}`}
          onClick={() => onNavigate('settings')}
          type="button"
          style={{ width: '100%', border: 'none', textAlign: 'left' }}
        >
          <Settings size={16} />
          <span>Settings & Standards</span>
        </button>
      </nav>

      {/* Footer */}
      <div className="sidebar-footer" style={{ padding: '14px 16px', borderTop: '1px solid #cbd5e1', background: '#d5dde6' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <strong style={{ color: '#0f172a', fontSize: '11px', letterSpacing: '0.4px' }}>TRACEON Platform</strong>
          <span style={{ fontSize: '9px', background: '#cbd5e1', border: '1px solid #94a3b8', padding: '1px 5px', borderRadius: '3px', color: '#1e293b', fontWeight: 700 }}>v1.2</span>
        </div>
        <div style={{ fontSize: '10px', color: '#475569', marginTop: '2px', fontWeight: 500 }}>
          Trace the Evidence. Trust the Process.
        </div>
      </div>
    </aside>
  );
};
