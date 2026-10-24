import React from 'react';
import type { HealthResponse } from '../types';
import { Shield, FileType, Info } from 'lucide-react';

interface SettingsPageProps {
  health: HealthResponse | null;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ health }) => {
  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">System Settings & Forensic Specifications</h1>
        <p className="page-subtitle">
          Configuration parameters, supported media specifications, and forensic boundaries
        </p>
      </div>

      {/* Forensic Operating Principles */}
      <div className="card">
        <div className="card-header">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Shield size={16} color="#2563eb" />
            <span>Forensic Development Principles (SPEC.md §15)</span>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '14px', fontSize: '13px' }}>
          <div style={{ padding: '12px', background: '#f8fafc', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
            <strong>1. Accuracy Over Quantity</strong>
            <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
              Accuracy and explainability are prioritized over high feature volume. No uncalibrated confidence percentages.
            </p>
          </div>
          <div style={{ padding: '12px', background: '#f8fafc', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
            <strong>2. Byte Preservation</strong>
            <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
              Original evidence files are stored read-only and never modified. Analysis operates exclusively on derived data.
            </p>
          </div>
          <div style={{ padding: '12px', background: '#f8fafc', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
            <strong>3. Indicator ≠ Tampering</strong>
            <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
              A detected anomaly or duplicate frame is an indicator for human investigator review, not automated proof of forgery.
            </p>
          </div>
          <div style={{ padding: '12px', background: '#f8fafc', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
            <strong>4. Hash Integrity Limits</strong>
            <p style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
              A matching SHA-256 hash confirms byte equality with the ingestion reference; it does not prove authenticity prior to registration.
            </p>
          </div>
        </div>
      </div>

      {/* Supported Media Formats */}
      <div className="card">
        <div className="card-header">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileType size={16} color="#2563eb" />
            <span>Supported Evidence Media Specifications (SPEC.md §4)</span>
          </div>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Supported Formats</th>
                <th>Validation Method</th>
                <th>Forensic Scope</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Image Evidence</strong></td>
                <td><span className="mono">JPG, JPEG, PNG</span></td>
                <td>Magic byte header inspection & Pillow validation</td>
                <td>EXIF metadata, timestamp parsing, ELA error level analysis</td>
              </tr>
              <tr>
                <td><strong>Video / CCTV</strong></td>
                <td><span className="mono">MP4, MOV, AVI</span></td>
                <td>Container signature & frame probe</td>
                <td>Frame count, duration, timestamp anomalies, duplicate frame checks</td>
              </tr>
              <tr>
                <td><strong>Audio Evidence</strong></td>
                <td><span className="mono">WAV, MP3</span></td>
                <td>Header verification & waveform analysis</td>
                <td>Duration, sample rate, channel count, metadata consistency</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Active System Configurations */}
      <div className="card">
        <div className="card-header">
          <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Info size={16} color="#2563eb" />
            <span>Active Environment Settings</span>
          </div>
        </div>
        <div className="table-container">
          <table className="data-table">
            <tbody>
              <tr>
                <td style={{ width: '240px' }}><strong>Backend Host & Port</strong></td>
                <td className="mono">127.0.0.1:8000</td>
              </tr>
              <tr>
                <td><strong>Database Engine</strong></td>
                <td className="mono">SQLite (evidenceguard.db)</td>
              </tr>
              <tr>
                <td><strong>Max Upload File Limit</strong></td>
                <td className="mono">100 MB (104,857,600 bytes)</td>
              </tr>
              <tr>
                <td><strong>Hash Algorithm</strong></td>
                <td className="mono">SHA-256 (256-bit cryptographic digest)</td>
              </tr>
              <tr>
                <td><strong>System Version</strong></td>
                <td className="mono">v{health?.version || '0.1.0'}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
