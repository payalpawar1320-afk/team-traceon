import React from 'react';
import type { PageId } from '../types';
import { Clock, ArrowRight } from 'lucide-react';

interface PhasePlaceholderProps {
  pageId: PageId;
  title: string;
  phaseNumber: number;
  phaseName: string;
  description: string;
  plannedFeatures: string[];
  onNavigate: (page: PageId) => void;
}

export const PhasePlaceholderPage: React.FC<PhasePlaceholderProps> = ({
  title,
  phaseNumber,
  phaseName,
  description,
  plannedFeatures,
  onNavigate,
}) => {
  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">{title}</h1>
        <p className="page-subtitle">{description}</p>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={16} color="#2563eb" />
            <span>Scheduled for Implementation in Phase {phaseNumber}: {phaseName}</span>
          </div>
          <span className="badge badge-neutral">Phase {phaseNumber} Roadmap</span>
        </div>

        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '16px' }}>
          This component has been structured in the Phase 1 application skeleton. Its complete interactive workflow
          will be built and tested during Phase {phaseNumber} following approval of the application foundation.
        </p>

        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '4px', border: '1px solid #e2e8f0', marginBottom: '20px' }}>
          <strong style={{ fontSize: '13px', display: 'block', marginBottom: '8px' }}>
            Phase {phaseNumber} Implementation Scope:
          </strong>
          <ul style={{ paddingLeft: '20px', fontSize: '13px', color: '#334155' }}>
            {plannedFeatures.map((feat, idx) => (
              <li key={idx} style={{ marginBottom: '6px' }}>{feat}</li>
            ))}
          </ul>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            className="btn btn-secondary"
            onClick={() => onNavigate('dashboard')}
          >
            <span>Return to Dashboard</span>
          </button>
          <button
            className="btn btn-primary"
            onClick={() => onNavigate('settings')}
          >
            <span>View System Capabilities & Settings</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
};
