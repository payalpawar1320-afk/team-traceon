import React, { useState, useEffect, useCallback } from 'react';
import type {
  PageId,
  EvidenceItem,
  ImageForensicAnalysisResponse,
  VideoForensicAnalysisResponse,
  AudioForensicAnalysisResponse,
  VideoFrameSample,
} from '../types';
import {
  fetchAllEvidence,
  runImageAnalysis,
  runVideoAnalysis,
  runAudioAnalysis,
  fetchEvidenceAnalyses,
  getEvidenceDownloadUrl,
} from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import {
  FileSearch,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Camera,
  Layers,
  MapPin,
  Clock,
  Sliders,
  Info,
  Maximize2,
  FileCode,
  ArrowRight,
  Film,
  Video,
  SplitSquareVertical,
  Volume2,
  Activity,
  FileAudio,
  Cpu,
} from 'lucide-react';


interface AnalysisResultsPageProps {
  initialEvidenceId?: number | null;
  onNavigate: (page: PageId, caseIdentifier?: string | number, evidenceId?: number) => void;
}

export const AnalysisResultsPage: React.FC<AnalysisResultsPageProps> = ({
  initialEvidenceId,
  onNavigate,
}) => {
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<number | ''>(
    initialEvidenceId || ''
  );
  const [currentEvidence, setCurrentEvidence] = useState<EvidenceItem | null>(null);

  // Analysis Results
  const [imageResult, setImageResult] = useState<ImageForensicAnalysisResponse | null>(null);
  const [videoResult, setVideoResult] = useState<VideoForensicAnalysisResponse | null>(null);
  const [audioResult, setAudioResult] = useState<AudioForensicAnalysisResponse | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Image ELA Controls
  const [elaQuality, setElaQuality] = useState<number>(92);
  const [elaScale, setElaScale] = useState<number>(15);
  const [overlayOpacity, setOverlayOpacity] = useState<number>(50);
  const [imageTab, setImageTab] = useState<'ai' | 'ela' | 'exif' | 'findings'>('ai');
  const [exifSearch, setExifSearch] = useState<string>('');

  // Video CCTV Controls
  const [videoTab, setVideoTab] = useState<'frames' | 'duplicates' | 'findings'>('frames');
  const [sampleFramesCount, setSampleFramesCount] = useState<number>(20);
  const [selectedFrameA, setSelectedFrameA] = useState<VideoFrameSample | null>(null);
  const [selectedFrameB, setSelectedFrameB] = useState<VideoFrameSample | null>(null);

  // Audio Acoustic Controls
  const [audioTab, setAudioTab] = useState<'waveform' | 'metadata' | 'findings'>('waveform');
  const [targetWaveformPoints, setTargetWaveformPoints] = useState<number>(100);

  // 1. Load media evidence list (images, videos, audios)
  useEffect(() => {
    async function loadMedia() {
      try {
        const [images, videos, audios] = await Promise.all([
          fetchAllEvidence({ fileType: 'image' }),
          fetchAllEvidence({ fileType: 'video' }),
          fetchAllEvidence({ fileType: 'audio' }),
        ]);
        const combined = [...images, ...videos, ...audios];
        setEvidenceList(combined);

        if (initialEvidenceId) {
          const found = combined.find((e) => e.id === Number(initialEvidenceId));
          if (found) {
            setSelectedEvidenceId(found.id);
            setCurrentEvidence(found);
          }
        } else if (combined.length > 0 && selectedEvidenceId === '') {
          setSelectedEvidenceId(combined[0].id);
          setCurrentEvidence(combined[0]);
        }
      } catch (err) {
        console.error('Failed to load evidence list:', err);
      } finally {
        setLoading(false);
      }
    }
    loadMedia();
  }, [initialEvidenceId]);

  // 2. Load existing analysis or execute if selected
  const loadAnalysis = useCallback(
    async (ev: EvidenceItem) => {
      setError(null);
      setImageResult(null);
      setVideoResult(null);
      setAudioResult(null);
      setSelectedFrameA(null);
      setSelectedFrameB(null);

      try {
        const history = await fetchEvidenceAnalyses(ev.id);
        if (ev.detected_file_type === 'image') {
          const imgRecord = history.find((h) => h.analysis_type === 'image_forensics');
          if (imgRecord) {
            setImageResult(imgRecord as ImageForensicAnalysisResponse);
          } else {
            setAnalyzing(true);
            const res = await runImageAnalysis(ev.id, { quality: elaQuality, scale: elaScale });
            setImageResult(res);
          }
        } else if (ev.detected_file_type === 'video') {
          const vidRecord = history.find((h) => h.analysis_type === 'video_forensics');
          if (vidRecord) {
            const vRes = vidRecord as unknown as VideoForensicAnalysisResponse;
            setVideoResult(vRes);
            if (vRes.video_report?.sampled_frames?.length > 0) {
              setSelectedFrameA(vRes.video_report.sampled_frames[0]);
              if (vRes.video_report.sampled_frames.length > 1) {
                setSelectedFrameB(vRes.video_report.sampled_frames[1]);
              }
            }
          } else {
            setAnalyzing(true);
            const res = await runVideoAnalysis(ev.id, { targetSampleFrames: sampleFramesCount });
            setVideoResult(res);
            if (res.video_report?.sampled_frames?.length > 0) {
              setSelectedFrameA(res.video_report.sampled_frames[0]);
              if (res.video_report.sampled_frames.length > 1) {
                setSelectedFrameB(res.video_report.sampled_frames[1]);
              }
            }
          }
        } else if (ev.detected_file_type === 'audio') {
          const audRecord = history.find((h) => h.analysis_type === 'audio_forensics');
          if (audRecord) {
            setAudioResult(audRecord as unknown as AudioForensicAnalysisResponse);
          } else {
            setAnalyzing(true);
            const res = await runAudioAnalysis(ev.id, { targetWaveformPoints });
            setAudioResult(res);
          }
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Analysis retrieval failed.');
      } finally {
        setAnalyzing(false);
      }
    },
    [elaQuality, elaScale, sampleFramesCount, targetWaveformPoints]
  );

  useEffect(() => {
    if (selectedEvidenceId !== '') {
      const ev = evidenceList.find((e) => e.id === Number(selectedEvidenceId));
      if (ev) {
        setCurrentEvidence(ev);
        loadAnalysis(ev);
      }
    }
  }, [selectedEvidenceId, evidenceList, loadAnalysis]);

  const handleRunAnalysis = async () => {
    if (!currentEvidence) return;
    setAnalyzing(true);
    setError(null);
    try {
      if (currentEvidence.detected_file_type === 'image') {
        const res = await runImageAnalysis(currentEvidence.id, {
          quality: elaQuality,
          scale: elaScale,
        });
        setImageResult(res);
      } else if (currentEvidence.detected_file_type === 'video') {
        const res = await runVideoAnalysis(currentEvidence.id, {
          targetSampleFrames: sampleFramesCount,
        });
        setVideoResult(res);
        if (res.video_report?.sampled_frames?.length > 0) {
          setSelectedFrameA(res.video_report.sampled_frames[0]);
          if (res.video_report.sampled_frames.length > 1) {
            setSelectedFrameB(res.video_report.sampled_frames[1]);
          }
        }
      } else if (currentEvidence.detected_file_type === 'audio') {
        const res = await runAudioAnalysis(currentEvidence.id, {
          targetWaveformPoints,
        });
        setAudioResult(res);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Analysis failed.');
    } finally {
      setAnalyzing(false);
    }
  };

  const isVideo = currentEvidence?.detected_file_type === 'video';
  const isAudio = currentEvidence?.detected_file_type === 'audio';
  const isImage = currentEvidence?.detected_file_type === 'image';
  const originalMediaUrl = currentEvidence ? getEvidenceDownloadUrl(currentEvidence.id) : '';

  // Image reports
  const meta = imageResult?.metadata_report;
  const ela = imageResult?.ela_report;
  const aiReport = imageResult?.ai_detection_report;
  const elaImageUrl = ela?.ela_url || '';

  // Video reports
  const vReport = videoResult?.video_report;

  // Audio reports
  const aReport = audioResult?.audio_report;

  // Filter raw exif entries
  const filteredExif = meta?.raw_exif
    ? Object.entries(meta.raw_exif).filter(
        ([k, v]) =>
          k.toLowerCase().includes(exifSearch.toLowerCase()) ||
          v.toLowerCase().includes(exifSearch.toLowerCase())
      )
    : [];

  const totalIndicators = isAudio
    ? audioResult?.total_indicators ?? 0
    : isVideo
    ? videoResult?.total_indicators ?? 0
    : imageResult?.total_indicators ?? 0;

  const currentStatus = isAudio
    ? audioResult?.status ?? 'Not analyzed'
    : isVideo
    ? videoResult?.status ?? 'Not analyzed'
    : imageResult?.status ?? 'Not analyzed';

  const currentLimitations = isAudio
    ? audioResult?.limitations ?? ''
    : isVideo
    ? videoResult?.limitations ?? ''
    : imageResult?.limitations ?? '';

  return (
    <div>
      {/* Page Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Digital Evidence Forensic Workstation</h1>
          <p className="page-subtitle">
            Scientific verification of image metadata, Error Level Analysis (FR-05), CCTV frame sequence inspection (FR-06), and acoustic signal forensics (FR-07).
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          style={{ fontSize: '12px' }}
          onClick={handleRunAnalysis}
          disabled={analyzing || !selectedEvidenceId}
        >
          <RefreshCw size={13} className={analyzing ? 'spin' : ''} />
          <span>{analyzing ? 'Executing Inspection...' : 'Run Forensic Examination'}</span>
        </button>
      </div>

      <div className="notice-box notice-info" style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span className="badge badge-primary" style={{ padding: '3px 8px', fontSize: '11px', fontWeight: 700 }}>STEP 4 OF 5</span>
        <span style={{ fontSize: '12px' }}>
          <strong>Deep Media Examination:</strong> Select any ingested evidence file to execute automated tampering checks (Image EXIF &amp; ELA heatmaps, Video CCTV duplicate/frozen frames, or Audio waveform &amp; clipping analysis).
        </span>
      </div>

      {error && (
        <div
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            padding: '12px 16px',
            borderRadius: '4px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '13px',
          }}
        >
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Selector & Top Bar */}
      <div className="card" style={{ marginBottom: '20px', padding: '16px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '280px' }}>
            <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
              Select Registered Media Evidence for Examination:
            </label>
            <select
              className="form-input"
              value={selectedEvidenceId}
              onChange={(e) => setSelectedEvidenceId(Number(e.target.value))}
              disabled={analyzing}
            >
              {evidenceList.map((item) => (
                <option key={item.id} value={item.id}>
                  [{item.detected_file_type.toUpperCase()}] {item.evidence_number} — {item.original_filename} ({(item.file_size / 1024).toFixed(1)} KB)
                </option>
              ))}
            </select>
          </div>

          {currentEvidence && (
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '16px' }}>
              <span className="badge badge-neutral" style={{ textTransform: 'uppercase' }}>
                {currentEvidence.detected_file_type} Evidence
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '12px', padding: '6px 12px' }}
                onClick={() => onNavigate('evidence-details', currentEvidence.case_id, currentEvidence.id)}
              >
                <span>View Full Dossier</span>
                <ArrowRight size={12} />
              </button>
            </div>
          )}
        </div>
      </div>

      {loading || (analyzing && !imageResult && !videoResult && !audioResult) ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <RefreshCw size={28} className="spin" style={{ color: 'var(--primary-blue)', marginBottom: '12px' }} />
          <p style={{ fontSize: '14px', fontWeight: 500 }}>
            {isAudio
              ? 'Decoding audio stream, checking clipping & generating waveform envelope...'
              : isVideo
              ? 'Decoding video stream and extracting CCTV frame samples...'
              : 'Extracting EXIF metadata and computing ELA compression heatmaps...'}
          </p>
        </div>
      ) : (!imageResult && !videoResult && !audioResult) ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <FileSearch size={36} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <p style={{ fontSize: '14px' }}>No analysis executed yet. Click "Run Forensic Examination" above to inspect.</p>
        </div>
      ) : (
        <>
          {/* Status Verdict Banner */}
          <div
            style={{
              background: totalIndicators > 0 ? '#fffbeb' : '#f0fdf4',
              border: `1px solid ${totalIndicators > 0 ? '#fde68a' : '#bbf7d0'}`,
              color: totalIndicators > 0 ? '#92400e' : '#166534',
              padding: '16px 20px',
              borderRadius: '4px',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              {totalIndicators > 0 ? (
                <ShieldAlert size={22} color="#d97706" />
              ) : (
                <ShieldCheck size={22} color="#16a34a" />
              )}
              <div>
                <strong style={{ fontSize: '14px' }}>Forensic Finding: {currentStatus}</strong>
                <div style={{ fontSize: '12px', marginTop: '2px' }}>
                  {totalIndicators === 0
                    ? isAudio
                      ? 'Continuous audio signal with no 0 dBFS clipping or silence drop anomalies.'
                      : isVideo
                      ? 'Continuous frame sequence with no duplicate/frozen frame anomalies.'
                      : 'No suspicious EXIF or compression anomalies detected.'
                    : `${totalIndicators} potential anomaly indicator(s) flagged for investigator scrutiny.`}
                </div>
              </div>
            </div>

            <StatusBadge
              status={totalIndicators === 0 ? 'NO INDICATOR DETECTED' : `${totalIndicators} INDICATOR(S)`}
              variant={totalIndicators === 0 ? 'success' : 'warning'}
            />
          </div>

          {/* ========================================================= */}
          {/*                     VIDEO / CCTV FORENSICS (FR-06)         */}
          {/* ========================================================= */}
          {isVideo && vReport && (
            <div>
              {/* Video Properties Overview Grid */}
              <div className="stats-grid" style={{ marginBottom: '20px' }}>
                <div className="stat-card">
                  <div>
                    <div className="stat-card-label">Duration & Length</div>
                    <div className="stat-card-val">{vReport.duration_sec}s</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {vReport.total_frames} total frames recorded
                    </div>
                  </div>
                  <Clock size={22} color="var(--text-muted)" />
                </div>

                <div className="stat-card">
                  <div>
                    <div className="stat-card-label">Resolution & Stream</div>
                    <div className="stat-card-val">
                      {vReport.width} × {vReport.height}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Codec: {vReport.codec}
                    </div>
                  </div>
                  <Film size={22} color="var(--text-muted)" />
                </div>

                <div className="stat-card">
                  <div>
                    <div className="stat-card-label">Frame Rate (FPS)</div>
                    <div className="stat-card-val">{vReport.fps} FPS</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {vReport.fps < 12 ? 'CCTV low-fps profile' : 'Standard video stream'}
                    </div>
                  </div>
                  <Video size={22} color="var(--text-muted)" />
                </div>

                <div className="stat-card">
                  <div>
                    <div className="stat-card-label">Duplicate / Freeze Status</div>
                    <div style={{ marginTop: '4px' }}>
                      <StatusBadge
                        status={
                          vReport.is_frozen_detected
                            ? 'FROZEN FRAMES DETECTED'
                            : vReport.duplicate_frames_count > 0
                            ? 'REPEATED FRAMES'
                            : 'CONTINUOUS'
                        }
                        variant={vReport.is_frozen_detected ? 'danger' : vReport.duplicate_frames_count > 0 ? 'warning' : 'success'}
                      />
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      {vReport.duplicate_frames_count} duplicate frames ({vReport.duplicate_percentage}%)
                    </div>
                  </div>
                  <ShieldCheck size={22} color={vReport.is_frozen_detected ? '#dc2626' : '#16a34a'} />
                </div>
              </div>

              {/* Video Tabs */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                <button
                  className={`btn ${videoTab === 'frames' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setVideoTab('frames')}
                >
                  <Film size={13} />
                  <span>Sampled Frame Sequence ({vReport.sampled_frames_count} Frames)</span>
                </button>
                <button
                  className={`btn ${videoTab === 'duplicates' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setVideoTab('duplicates')}
                >
                  <SplitSquareVertical size={13} />
                  <span>Frame Comparator & Repetition ({vReport.duplicate_groups.length} Groups)</span>
                </button>
                <button
                  className={`btn ${videoTab === 'findings' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setVideoTab('findings')}
                >
                  <FileSearch size={13} />
                  <span>CCTV Continuity Findings ({vReport.findings.length})</span>
                </button>
              </div>

              {/* TAB 1: SAMPLED FRAME SEQUENCE TIMELINE STRIP */}
              {videoTab === 'frames' && (
                <div>
                  <div className="card" style={{ marginBottom: '20px' }}>
                    <div className="card-header">
                      <div>
                        <span className="card-title">CCTV Footage Sampled Frame Sequence</span>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                          Click any two frames to load them into the side-by-side comparator below.
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Sample Density:</span>
                        <select
                          className="form-input"
                          value={sampleFramesCount}
                          onChange={(e) => setSampleFramesCount(Number(e.target.value))}
                          style={{ fontSize: '12px', padding: '4px 8px', width: '90px' }}
                        >
                          <option value="10">10 Frames</option>
                          <option value="20">20 Frames</option>
                          <option value="30">30 Frames</option>
                        </select>
                      </div>
                    </div>

                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                        gap: '12px',
                        padding: '8px 0',
                      }}
                    >
                      {vReport.sampled_frames.map((frame) => {
                        const isA = selectedFrameA?.frame_index === frame.frame_index;
                        const isB = selectedFrameB?.frame_index === frame.frame_index;

                        return (
                          <div
                            key={frame.frame_index}
                            onClick={() => {
                              if (!selectedFrameA || (selectedFrameA && selectedFrameB)) {
                                setSelectedFrameA(frame);
                                setSelectedFrameB(null);
                              } else {
                                setSelectedFrameB(frame);
                              }
                            }}
                            style={{
                              border: isA
                                ? '2px solid #2563eb'
                                : isB
                                ? '2px solid #7c3aed'
                                : frame.is_duplicate
                                ? '2px solid #f59e0b'
                                : '1px solid #e2e8f0',
                              borderRadius: '4px',
                              overflow: 'hidden',
                              background: '#ffffff',
                              cursor: 'pointer',
                              position: 'relative',
                            }}
                          >
                            <img
                              src={frame.thumbnail_url}
                              alt={`Frame ${frame.frame_index}`}
                              style={{ width: '100%', height: '110px', objectFit: 'cover', display: 'block', background: '#0f172a' }}
                            />

                            <div style={{ padding: '8px' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: 600 }}>
                                <span>Frame #{frame.frame_index}</span>
                                <span className="mono" style={{ color: 'var(--text-muted)' }}>
                                  {frame.timestamp_sec.toFixed(2)}s
                                </span>
                              </div>

                              <div style={{ marginTop: '4px' }}>
                                {frame.is_duplicate ? (
                                  <span className="badge badge-warning" style={{ fontSize: '9px', padding: '1px 4px' }}>
                                    DUPLICATE OF #{frame.duplicate_of_index}
                                  </span>
                                ) : (
                                  <span className="badge badge-neutral" style={{ fontSize: '9px', padding: '1px 4px' }}>
                                    UNIQUE
                                  </span>
                                )}

                                {isA && (
                                  <span className="badge badge-primary" style={{ fontSize: '9px', padding: '1px 4px', marginLeft: '4px' }}>
                                    COMPARATOR [A]
                                  </span>
                                )}
                                {isB && (
                                  <span className="badge badge-neutral" style={{ fontSize: '9px', padding: '1px 4px', marginLeft: '4px', background: '#7c3aed', color: '#fff' }}>
                                    COMPARATOR [B]
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Side-by-Side Comparator Card */}
                  <div className="card">
                    <div className="card-header">
                      <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <SplitSquareVertical size={16} color="#2563eb" />
                        <span>Interactive Frame Pair Comparator</span>
                      </div>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        Select two frames above to examine fine visual differences side-by-side
                      </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
                      {/* Frame A */}
                      <div style={{ border: '1px solid #bfdbfe', borderRadius: '4px', padding: '12px', background: '#eff6ff' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <strong style={{ fontSize: '13px', color: '#1e40af' }}>Frame A Reference</strong>
                          {selectedFrameA && (
                            <span className="mono" style={{ fontSize: '12px', color: '#1e40af' }}>
                              #{selectedFrameA.frame_index} ({selectedFrameA.timestamp_sec.toFixed(2)}s)
                            </span>
                          )}
                        </div>
                        {selectedFrameA ? (
                          <img
                            src={selectedFrameA.thumbnail_url}
                            alt="Frame A"
                            style={{ width: '100%', maxHeight: '280px', objectFit: 'contain', borderRadius: '4px', background: '#0f172a' }}
                          />
                        ) : (
                          <div style={{ textAlign: 'center', padding: '40px', color: '#64748b', fontSize: '13px' }}>
                            Click a frame above to assign Frame A
                          </div>
                        )}
                      </div>

                      {/* Frame B */}
                      <div style={{ border: '1px solid #ddd6fe', borderRadius: '4px', padding: '12px', background: '#f5f3ff' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <strong style={{ fontSize: '13px', color: '#5b21b6' }}>Frame B Reference</strong>
                          {selectedFrameB && (
                            <span className="mono" style={{ fontSize: '12px', color: '#5b21b6' }}>
                              #{selectedFrameB.frame_index} ({selectedFrameB.timestamp_sec.toFixed(2)}s)
                            </span>
                          )}
                        </div>
                        {selectedFrameB ? (
                          <img
                            src={selectedFrameB.thumbnail_url}
                            alt="Frame B"
                            style={{ width: '100%', maxHeight: '280px', objectFit: 'contain', borderRadius: '4px', background: '#0f172a' }}
                          />
                        ) : (
                          <div style={{ textAlign: 'center', padding: '40px', color: '#64748b', fontSize: '13px' }}>
                            Click another frame above to assign Frame B
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: DUPLICATE / FROZEN FRAME AUDIT */}
              {videoTab === 'duplicates' && (
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">Duplicate & Frozen Frame Audit Log</span>
                    <span className="badge badge-neutral">
                      {vReport.duplicate_groups.length} Repeated Sequences Identified
                    </span>
                  </div>

                  {vReport.duplicate_groups.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '36px', color: 'var(--text-muted)' }}>
                      <ShieldCheck size={36} color="#16a34a" style={{ marginBottom: '8px' }} />
                      <p style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-main)', marginBottom: '4px' }}>
                        No Identical Frames Detected
                      </p>
                      <p style={{ fontSize: '12px' }}>
                        The sampled frame sequence shows dynamic pixel variation with zero identical frame matches.
                      </p>
                    </div>
                  ) : (
                    <div className="table-container" style={{ border: 'none' }}>
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Primary Frame</th>
                            <th>Repetition Type</th>
                            <th>Duplicate Frame Indices</th>
                            <th>Repeat Timestamps (s)</th>
                            <th>Duration of Repetition</th>
                          </tr>
                        </thead>
                        <tbody>
                          {vReport.duplicate_groups.map((group, idx) => {
                            const timeSpan = group.timestamps_sec.length > 1
                              ? (group.timestamps_sec[group.timestamps_sec.length - 1] - group.timestamps_sec[0]).toFixed(2)
                              : '0.00';

                            return (
                              <tr key={idx}>
                                <td style={{ fontWeight: 600 }}>
                                  Frame #{group.primary_frame_index} ({group.timestamps_sec[0]}s)
                                </td>
                                <td>
                                  {group.is_consecutive ? (
                                    <span className="badge badge-danger">CONSECUTIVE FREEZE</span>
                                  ) : (
                                    <span className="badge badge-warning">PERIODIC REPEAT</span>
                                  )}
                                </td>
                                <td className="mono" style={{ fontSize: '12px' }}>
                                  {group.duplicate_frame_indices.map((i) => `#${i}`).join(', ')}
                                </td>
                                <td className="mono" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                                  {group.timestamps_sec.map((t) => `${t}s`).join(', ')}
                                </td>
                                <td style={{ fontWeight: 500, color: group.is_consecutive ? '#dc2626' : 'var(--text-main)' }}>
                                  ~{timeSpan}s span
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: CCTV CONTINUITY FINDINGS */}
              {videoTab === 'findings' && (
                <div className="card" style={{ marginBottom: '20px' }}>
                  <div className="card-header">
                    <span className="card-title">Forensic CCTV Inspection Observations</span>
                    <span className="badge badge-neutral">{vReport.findings.length} Findings</span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '8px 0' }}>
                    {vReport.findings.map((finding, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '14px 16px',
                          borderRadius: '4px',
                          border: '1px solid #e2e8f0',
                          borderLeftWidth: '4px',
                          borderLeftColor:
                            finding.severity === 'high'
                              ? '#dc2626'
                              : finding.severity === 'medium'
                              ? '#f59e0b'
                              : '#3b82f6',
                          background: '#f8fafc',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span
                            className={`badge ${
                              finding.severity === 'high'
                                ? 'badge-danger'
                                : finding.severity === 'medium'
                                ? 'badge-warning'
                                : 'badge-neutral'
                            }`}
                          >
                            {finding.severity.toUpperCase()}
                          </span>
                          <strong style={{ fontSize: '13px', color: '#0f172a' }}>{finding.title}</strong>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                            {finding.category}
                          </span>
                        </div>
                        <p style={{ fontSize: '13px', color: '#334155', margin: '4px 0 0', lineHeight: 1.5 }}>
                          {finding.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ========================================================= */}
          {/*                     AUDIO FORENSICS (FR-07)                */}
          {/* ========================================================= */}
          {isAudio && aReport && (
            <div>
              {/* Audio Properties Overview Grid */}
              <div className="stats-grid" style={{ marginBottom: '20px' }}>
                <div className="stat-card">
                  <div>
                    <div className="stat-card-label">Duration & Channels</div>
                    <div className="stat-card-val">{aReport.duration_sec}s</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {aReport.channel_mode} ({aReport.channels} ch) • {aReport.sample_rate_hz} Hz
                    </div>
                  </div>
                  <Clock size={22} color="var(--text-muted)" />
                </div>

                <div className="stat-card">
                  <div>
                    <div className="stat-card-label">Encoding & Bit Depth</div>
                    <div className="stat-card-val">{aReport.format}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {aReport.bit_depth}-bit {aReport.bitrate_kbps ? `• ${aReport.bitrate_kbps} kbps` : '• Uncompressed PCM'}
                    </div>
                  </div>
                  <FileAudio size={22} color="var(--text-muted)" />
                </div>

                <div className="stat-card">
                  <div>
                    <div className="stat-card-label">Signal Dynamics</div>
                    <div className="stat-card-val">
                      {aReport.peak_amplitude != null ? aReport.peak_amplitude.toFixed(2) : 'N/A'}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      RMS Level: {aReport.rms_dbfs != null ? `${aReport.rms_dbfs.toFixed(1)} dBFS` : 'N/A'}
                    </div>
                  </div>
                  <Activity size={22} color="var(--text-muted)" />
                </div>

                <div className="stat-card">
                  <div>
                    <div className="stat-card-label">Clipping & Discontinuity</div>
                    <div style={{ marginTop: '4px' }}>
                      <StatusBadge
                        status={
                          aReport.is_clipped
                            ? 'CLIPPED (0 dBFS)'
                            : aReport.silence_drop_count > 0
                            ? 'SILENCE DROPS'
                            : 'SIGNAL CLEAN'
                        }
                        variant={aReport.is_clipped ? 'danger' : aReport.silence_drop_count > 0 ? 'warning' : 'success'}
                      />
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      {aReport.clipped_samples_count} clipped • {aReport.silence_drop_count} silence drops
                    </div>
                  </div>
                  <ShieldCheck size={22} color={aReport.is_clipped ? '#dc2626' : '#16a34a'} />
                </div>
              </div>

              {/* Native Audio Playback Card */}
              <div className="card" style={{ marginBottom: '20px', padding: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Volume2 size={16} color="#2563eb" />
                    <span style={{ fontWeight: 600, fontSize: '13px' }}>Acoustic Evidence Auditory Playback</span>
                  </div>
                  <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Streaming direct byte feed from secure storage
                  </span>
                </div>
                <audio controls src={originalMediaUrl} style={{ width: '100%', height: '42px', outline: 'none' }} />
              </div>

              {/* Audio Navigation Tabs */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                <button
                  className={`btn ${audioTab === 'waveform' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setAudioTab('waveform')}
                >
                  <Activity size={13} />
                  <span>Waveform & Envelope Inspection</span>
                </button>
                <button
                  className={`btn ${audioTab === 'metadata' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setAudioTab('metadata')}
                >
                  <FileCode size={13} />
                  <span>Container, ID3 & Software Traces</span>
                </button>
                <button
                  className={`btn ${audioTab === 'findings' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setAudioTab('findings')}
                >
                  <FileSearch size={13} />
                  <span>Acoustic Findings ({aReport.findings.length})</span>
                </button>
              </div>

              {/* TAB 1: WAVEFORM & ENVELOPE */}
              {audioTab === 'waveform' && (
                <div className="card" style={{ marginBottom: '20px' }}>
                  <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Activity size={16} color="#2563eb" />
                      <span className="card-title">Sampled Peak Envelope Waveform</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '11px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Resolution:</span>
                        {[50, 100, 200].map((pts) => (
                          <button
                            key={pts}
                            type="button"
                            className={`btn ${targetWaveformPoints === pts ? 'btn-primary' : 'btn-secondary'}`}
                            style={{ padding: '2px 6px', fontSize: '10px', height: '22px' }}
                            onClick={() => {
                              setTargetWaveformPoints(pts);
                              if (currentEvidence) {
                                runAudioAnalysis(currentEvidence.id, { targetWaveformPoints: pts }).then(setAudioResult);
                              }
                            }}
                          >
                            {pts} pts
                          </button>
                        ))}
                      </div>

                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '10px', height: '10px', background: '#38bdf8', display: 'inline-block', borderRadius: '2px' }} />
                        Normal Range
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '10px', height: '10px', background: '#ef4444', display: 'inline-block', borderRadius: '2px' }} />
                        0 dBFS Clipping
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '10px', height: '10px', background: '#f59e0b', display: 'inline-block', borderRadius: '2px' }} />
                        Silence Drop
                      </span>
                    </div>
                  </div>

                  {/* SVG Waveform Visualizer */}
                  <div style={{ background: '#0f172a', borderRadius: '4px', padding: '16px 20px', position: 'relative' }}>
                    <svg viewBox="0 0 800 160" style={{ width: '100%', height: '180px', display: 'block' }}>
                      {/* Grid Lines */}
                      <line x1="40" y1="20" x2="800" y2="20" stroke="#1e293b" strokeDasharray="3 3" />
                      <line x1="40" y1="50" x2="800" y2="50" stroke="#1e293b" strokeDasharray="3 3" />
                      <line x1="40" y1="80" x2="800" y2="80" stroke="#334155" strokeWidth="1" />
                      <line x1="40" y1="110" x2="800" y2="110" stroke="#1e293b" strokeDasharray="3 3" />
                      <line x1="40" y1="140" x2="800" y2="140" stroke="#1e293b" strokeDasharray="3 3" />

                      {/* Amplitude labels */}
                      <text x="8" y="24" fill="#64748b" fontSize="9" fontFamily="monospace">+1.0</text>
                      <text x="8" y="54" fill="#64748b" fontSize="9" fontFamily="monospace">+0.5</text>
                      <text x="8" y="83" fill="#94a3b8" fontSize="9" fontFamily="monospace"> 0.0</text>
                      <text x="8" y="114" fill="#64748b" fontSize="9" fontFamily="monospace">-0.5</text>
                      <text x="8" y="144" fill="#64748b" fontSize="9" fontFamily="monospace">-1.0</text>

                      {/* Render Bars */}
                      {aReport.waveform_peaks.map((p, idx) => {
                        const total = aReport.waveform_peaks.length;
                        const x = 40 + (idx / total) * 750;
                        const barWidth = Math.max(2, (750 / total) - 1.5);
                        const maxAmp = Math.min(1.0, Math.abs(p.max_amplitude));
                        const minAmp = Math.min(1.0, Math.abs(p.min_amplitude));
                        const topY = 80 - maxAmp * 58;
                        const bottomY = 80 + minAmp * 58;
                        const height = Math.max(2, bottomY - topY);

                        const isClipped = maxAmp >= 0.98 || minAmp >= 0.98;
                        const isZeroDrop = maxAmp < 0.005 && minAmp < 0.005;
                        const fill = isClipped ? '#ef4444' : isZeroDrop ? '#f59e0b' : '#38bdf8';

                        return (
                          <rect
                            key={idx}
                            x={x}
                            y={topY}
                            width={barWidth}
                            height={height}
                            fill={fill}
                            rx={1}
                          >
                            <title>{`Time: ${p.time_sec}s | Peak: +${maxAmp.toFixed(3)} / -${minAmp.toFixed(3)}`}</title>
                          </rect>
                        );
                      })}
                    </svg>

                    {/* Timeline labels */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', paddingLeft: '40px', marginTop: '6px', fontSize: '10px', color: '#94a3b8', fontFamily: 'monospace' }}>
                      <span>0.0s</span>
                      <span>{(aReport.duration_sec * 0.25).toFixed(2)}s</span>
                      <span>{(aReport.duration_sec * 0.5).toFixed(2)}s</span>
                      <span>{(aReport.duration_sec * 0.75).toFixed(2)}s</span>
                      <span>{aReport.duration_sec.toFixed(2)}s</span>
                    </div>
                  </div>

                  {/* Summary Bar */}
                  <div style={{ padding: '12px 16px', background: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '24px', flexWrap: 'wrap', fontSize: '12px' }}>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Peak Envelope Points: </span>
                      <strong className="mono">{aReport.waveform_peaks.length} samples</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Signal Clipping: </span>
                      <strong style={{ color: aReport.is_clipped ? '#dc2626' : '#16a34a' }}>
                        {aReport.is_clipped ? `Detected (${aReport.clipped_samples_count} clipped frames)` : 'None detected'}
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Silence Discontinuities: </span>
                      <strong style={{ color: aReport.silence_drop_count > 0 ? '#b45309' : '#16a34a' }}>
                        {aReport.silence_drop_count} anomalous silence gap(s)
                      </strong>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: CONTAINER, ID3 & SOFTWARE TRACES */}
              {audioTab === 'metadata' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '20px' }}>
                  {/* Software signature warning card */}
                  {aReport.software_signature && (
                    <div
                      style={{
                        padding: '16px',
                        background: '#fef2f2',
                        border: '1px solid #fecaca',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                      }}
                    >
                      <ShieldAlert size={24} color="#dc2626" />
                      <div>
                        <strong style={{ color: '#991b1b', fontSize: '14px' }}>
                          Editing Software Trace Identified: {aReport.software_signature}
                        </strong>
                        <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#7f1d1d' }}>
                          The audio container or ID3 headers contain explicit signatures of digital audio workstation (DAW) editing software.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Container parameters */}
                  <div className="card">
                    <div className="card-header">
                      <span className="card-title">Acoustic Technical Stream Parameters</span>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                      <table className="data-table">
                        <tbody>
                          <tr>
                            <td style={{ fontWeight: 600, width: '220px' }}>Container Format</td>
                            <td className="mono">{aReport.format}</td>
                          </tr>
                          <tr>
                            <td style={{ fontWeight: 600 }}>Sampling Rate</td>
                            <td className="mono">{aReport.sample_rate_hz} Hz ({aReport.sample_rate_hz >= 44100 ? 'CD / Studio Standard' : 'Telephone / Voice Standard'})</td>
                          </tr>
                          <tr>
                            <td style={{ fontWeight: 600 }}>Channel Configuration</td>
                            <td className="mono">{aReport.channel_mode} ({aReport.channels} channels)</td>
                          </tr>
                          <tr>
                            <td style={{ fontWeight: 600 }}>Quantization Bit Depth</td>
                            <td className="mono">{aReport.bit_depth}-bit</td>
                          </tr>
                          {aReport.bitrate_kbps && (
                            <tr>
                              <td style={{ fontWeight: 600 }}>Compression Bitrate</td>
                              <td className="mono">{aReport.bitrate_kbps} kbps</td>
                            </tr>
                          )}
                          <tr>
                            <td style={{ fontWeight: 600 }}>Calculated RMS Power</td>
                            <td className="mono">{aReport.rms_dbfs != null ? `${aReport.rms_dbfs} dBFS` : 'N/A'}</td>
                          </tr>
                          <tr>
                            <td style={{ fontWeight: 600 }}>Peak Signal Level</td>
                            <td className="mono">{aReport.peak_amplitude != null ? `${aReport.peak_amplitude} (${(aReport.peak_amplitude * 100).toFixed(1)}% of full scale)` : 'N/A'}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* ID3 Tags Table */}
                  <div className="card">
                    <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="card-title">Embedded ID3 Metadata Headers</span>
                      <span className="badge badge-neutral">
                        {Object.keys(aReport.id3_tags).length} Tag(s) Present
                      </span>
                    </div>

                    {Object.keys(aReport.id3_tags).length === 0 ? (
                      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                        No ID3v2 tags present in audio stream headers (typical for raw PCM WAV or clean voice recorders).
                      </div>
                    ) : (
                      <div style={{ overflowX: 'auto' }}>
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th style={{ width: '220px' }}>ID3 Frame Key</th>
                              <th>Decoded Value</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(aReport.id3_tags).map(([k, v]) => (
                              <tr key={k}>
                                <td style={{ fontWeight: 600 }}>{k}</td>
                                <td className="mono">{v}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 3: FINDINGS */}
              {audioTab === 'findings' && (
                <div className="card" style={{ marginBottom: '20px' }}>
                  <div className="card-header">
                    <span className="card-title">Forensic Acoustic Analysis Observations</span>
                    <span className="badge badge-neutral">{aReport.findings.length} Findings</span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '8px 0' }}>
                    {aReport.findings.map((finding, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '14px 16px',
                          borderRadius: '4px',
                          border: '1px solid #e2e8f0',
                          borderLeftWidth: '4px',
                          borderLeftColor:
                            finding.severity === 'high'
                              ? '#dc2626'
                              : finding.severity === 'medium'
                              ? '#f59e0b'
                              : '#3b82f6',
                          background: '#f8fafc',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span
                            className={`badge ${
                              finding.severity === 'high'
                                ? 'badge-danger'
                                : finding.severity === 'medium'
                                ? 'badge-warning'
                                : 'badge-neutral'
                            }`}
                          >
                            {finding.severity.toUpperCase()}
                          </span>
                          <strong style={{ fontSize: '13px', color: '#0f172a' }}>{finding.title}</strong>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                            {finding.category}
                          </span>
                        </div>
                        <p style={{ fontSize: '13px', color: '#334155', margin: '4px 0 0', lineHeight: 1.5 }}>
                          {finding.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ========================================================= */}
          {/*                     IMAGE FORENSICS (FR-05)                */}
          {/* ========================================================= */}
          {isImage && meta && (
            <div>
              {/* Navigation Tabs */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                <button
                  className={`btn ${imageTab === 'ai' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setImageTab('ai')}
                >
                  <Cpu size={13} />
                  <span>AI vs Real Media Classifier</span>
                </button>
                <button
                  className={`btn ${imageTab === 'ela' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setImageTab('ela')}
                >
                  <Sliders size={13} />
                  <span>Error Level Analysis (ELA)</span>
                </button>
                <button
                  className={`btn ${imageTab === 'exif' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setImageTab('exif')}
                >
                  <Camera size={13} />
                  <span>Camera & EXIF Metadata ({meta.has_exif ? 'Found' : 'Absent'})</span>
                </button>
                <button
                  className={`btn ${imageTab === 'findings' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                  onClick={() => setImageTab('findings')}
                >
                  <FileSearch size={13} />
                  <span>Explainable Findings ({meta.findings.length + (ela?.findings.length || 0) + (aiReport?.findings.length || 0)})</span>
                </button>
              </div>

              {/* TAB 0: AI VS REAL CLASSIFIER */}
              {imageTab === 'ai' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '20px' }}>
                  {aiReport ? (
                    <>
                      {/* Top Classification Banner */}
                      <div
                        className="card"
                        style={{
                          padding: '20px',
                          borderLeftWidth: '5px',
                          borderLeftColor: aiReport.is_ai_generated ? '#dc2626' : '#16a34a',
                          background: aiReport.is_ai_generated ? '#fef2f2' : '#f0fdf4',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                              <span
                                className={`badge ${aiReport.is_ai_generated ? 'badge-danger' : 'badge-success'}`}
                                style={{ fontSize: '12px', padding: '4px 10px', fontWeight: 700 }}
                              >
                                {aiReport.is_ai_generated ? 'INDICATOR FOUND: LIKELY AI-GENERATED' : 'NO AI INDICATOR FOUND (CAMERA-CONSISTENT)'}
                              </span>
                              <span style={{ fontSize: '12px', color: '#64748b' }}>
                                Model: <strong>{aiReport.model_name}</strong>
                              </span>
                            </div>
                            <h3 style={{ fontSize: '16px', fontWeight: 700, margin: '4px 0', color: aiReport.is_ai_generated ? '#991b1b' : '#166534' }}>
                              {aiReport.prediction}
                            </h3>
                            <p style={{ fontSize: '13px', color: '#334155', margin: '4px 0 0', maxWidth: '700px' }}>
                              {aiReport.is_ai_generated
                                ? `Neural feature representations align with synthetic benchmark patterns (uncalibrated model score: ${aiReport.probability_ai_pct}%). Does not prove synthetic origin.`
                                : `Neural feature representations align with physical camera benchmark patterns (uncalibrated model score: ${aiReport.probability_real_pct}%).`}
                            </p>
                          </div>

                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: '28px', fontWeight: 800, color: aiReport.is_ai_generated ? '#dc2626' : '#16a34a' }}>
                              {aiReport.is_ai_generated ? `${aiReport.probability_ai_pct}%` : `${aiReport.probability_real_pct}%`}
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                              Model Decision Score (Uncalibrated)
                            </div>
                          </div>
                        </div>

                        {/* Probability Split Bar */}
                        <div style={{ marginTop: '16px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
                            <span style={{ color: '#dc2626' }}>AI Decision Score (Uncalibrated): {aiReport.probability_ai_pct}%</span>
                            <span style={{ color: '#16a34a' }}>Camera-Capture Consistency (Uncalibrated): {aiReport.probability_real_pct}%</span>
                          </div>
                          <div style={{ height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                            <div style={{ width: `${aiReport.probability_ai_pct}%`, background: '#dc2626' }} />
                            <div style={{ width: `${aiReport.probability_real_pct}%`, background: '#16a34a' }} />
                          </div>
                        </div>
                      </div>

                      {/* Empirical Validation Limitation Warning */}
                      <div
                        className="notice-box notice-warning"
                        style={{
                          padding: '14px 18px',
                          borderRadius: '8px',
                          background: '#fffbeb',
                          border: '1px solid #fde68a',
                          color: '#92400e',
                          fontSize: '12px',
                          lineHeight: 1.6,
                        }}
                      >
                        <div style={{ fontWeight: 700, marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <AlertTriangle size={15} color="#b45309" />
                          <span>Forensic Evaluation Disclosure &amp; Calibration Warning</span>
                        </div>
                        <div>
                          <strong>Uncalibrated Heuristic:</strong> The displayed percentages are uncalibrated sigmoid transformations of neural logits, not empirical Bayesian probabilities.
                          Independent testing on 200 non-training out-of-domain images (AI-vs-Real dataset) produced <strong>54.5% overall accuracy</strong> with a <strong>61.0% false-positive rate</strong> on authentic photographs.
                          In legal and investigative contexts, this output must be treated as a heuristic indicator, never as standalone proof of authenticity or generation.
                        </div>
                      </div>

                      {/* Diagnostic Breakdown Grid */}
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
                        <div className="card" style={{ padding: '16px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                            <Cpu size={16} color="#2563eb" />
                            <span style={{ fontWeight: 600, fontSize: '13px' }}>Neural Architecture</span>
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                            <div>Model: <strong>{aiReport.model_name}</strong></div>
                            <div>Weights: <strong>CIFAKE Benchmark (120,000 images)</strong></div>
                            <div>Raw Output Logit: <span className="mono">{aiReport.raw_logit}</span></div>
                            <div>Score Type: <strong>Uncalibrated Sigmoid</strong></div>
                          </div>
                        </div>

                        <div className="card" style={{ padding: '16px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                            <Activity size={16} color="#7c3aed" />
                            <span style={{ fontWeight: 600, fontSize: '13px' }}>2D-FFT Spectral Energy Metric</span>
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                            <div>High-Freq Elevation: <strong>{aiReport.fft_anomaly_detected ? 'High Ratio Detected' : 'Standard Continuous Attenuation'}</strong></div>
                            <div>High-to-Center Ratio: <span className="mono">{aiReport.fft_outer_center_ratio}</span></div>
                            <div>Forensic Context: <strong>High ratios also occur from natural textures; does not prove AI.</strong></div>
                          </div>
                        </div>

                        <div className="card" style={{ padding: '16px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                            <Camera size={16} color="#059669" />
                            <span style={{ fontWeight: 600, fontSize: '13px' }}>Hardware Sensor Profile</span>
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                            <div>EXIF Sensor Tag: <strong>{meta.camera_make ? `${meta.camera_make} ${meta.camera_model || ''}` : 'No Camera Tag'}</strong></div>
                            <div>Software Signature: <strong>{meta.software || 'None Detected'}</strong></div>
                            <div>Provenance: <strong>{meta.has_exif ? 'Embedded Optical EXIF' : 'Stripped / Synthetic'}</strong></div>
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="card" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      <Cpu size={32} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
                      <p style={{ margin: 0 }}>Click "Run Forensic Examination" above to execute the AI vs Real classifier on this evidence item.</p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 1: ELA */}
              {imageTab === 'ela' && (
                <div>
                  <div className="card" style={{ marginBottom: '16px', padding: '14px 18px' }}>
                    <div style={{ display: 'flex', gap: '24px', alignItems: 'center', flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 600 }}>ELA Heatmap Overlay Opacity:</span>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={overlayOpacity}
                          onChange={(e) => setOverlayOpacity(Number(e.target.value))}
                          style={{ cursor: 'pointer', width: '130px' }}
                        />
                        <span className="mono" style={{ fontSize: '12px', width: '36px' }}>
                          {overlayOpacity}%
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 600 }}>Resave Quality:</span>
                        <select
                          className="form-input"
                          value={elaQuality}
                          onChange={(e) => setElaQuality(Number(e.target.value))}
                          style={{ fontSize: '12px', padding: '4px 8px', width: '80px' }}
                        >
                          <option value="90">90%</option>
                          <option value="92">92%</option>
                          <option value="95">95%</option>
                        </select>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 600 }}>Scale Factor:</span>
                        <select
                          className="form-input"
                          value={elaScale}
                          onChange={(e) => setElaScale(Number(e.target.value))}
                          style={{ fontSize: '12px', padding: '4px 8px', width: '80px' }}
                        >
                          <option value="10">10x</option>
                          <option value="15">15x</option>
                          <option value="20">20x</option>
                        </select>
                      </div>

                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ fontSize: '11px', padding: '4px 10px', marginLeft: 'auto' }}
                        onClick={handleRunAnalysis}
                        disabled={analyzing}
                      >
                        <span>Re-calculate ELA</span>
                      </button>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '16px', marginBottom: '20px' }}>
                    <div className="card" style={{ marginBottom: 0 }}>
                      <div className="card-header">
                        <span className="card-title">1. Original Evidence Bytes</span>
                      </div>
                      <div style={{ background: '#0f172a', borderRadius: '4px', padding: '16px', textAlign: 'center', minHeight: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <img
                          src={originalMediaUrl}
                          alt="Original Evidence"
                          style={{ maxHeight: '340px', maxWidth: '100%', objectFit: 'contain', borderRadius: '4px' }}
                        />
                      </div>
                    </div>

                    <div className="card" style={{ marginBottom: 0 }}>
                      <div className="card-header">
                        <span className="card-title">2. Blended Forensic Inspection</span>
                        <span className="badge badge-neutral">{overlayOpacity}% Overlay</span>
                      </div>
                      <div style={{ background: '#0f172a', borderRadius: '4px', padding: '16px', textAlign: 'center', minHeight: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                        <div style={{ position: 'relative', display: 'inline-block', maxHeight: '340px', maxWidth: '100%' }}>
                          <img
                            src={originalMediaUrl}
                            alt="Original Base"
                            style={{ maxHeight: '340px', maxWidth: '100%', objectFit: 'contain', borderRadius: '4px', display: 'block' }}
                          />
                          {elaImageUrl && (
                            <img
                              src={elaImageUrl}
                              alt="ELA Heatmap Overlay"
                              style={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                width: '100%',
                                height: '100%',
                                objectFit: 'contain',
                                borderRadius: '4px',
                                opacity: overlayOpacity / 100,
                                mixBlendMode: 'screen',
                                pointerEvents: 'none',
                              }}
                            />
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="card" style={{ marginBottom: 0 }}>
                      <div className="card-header">
                        <span className="card-title">3. Error Level Difference Heatmap</span>
                        <span className="badge badge-neutral">{elaScale}x Amplification</span>
                      </div>
                      <div style={{ background: '#000000', borderRadius: '4px', padding: '16px', textAlign: 'center', minHeight: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {elaImageUrl ? (
                          <img
                            src={elaImageUrl}
                            alt="Pure ELA Heatmap"
                            style={{ maxHeight: '340px', maxWidth: '100%', objectFit: 'contain', borderRadius: '4px' }}
                          />
                        ) : (
                          <span style={{ color: '#64748b', fontSize: '13px' }}>ELA heatmap pending calculation</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {ela && (
                    <div className="stats-grid" style={{ marginBottom: '20px' }}>
                      <div className="stat-card">
                        <div>
                          <div className="stat-card-label">Mean Error Rate</div>
                          <div className="stat-card-val">{ela.mean_error}</div>
                        </div>
                        <Layers size={22} color="var(--text-muted)" />
                      </div>

                      <div className="stat-card">
                        <div>
                          <div className="stat-card-label">Max Pixel Delta</div>
                          <div className="stat-card-val">{ela.max_error} / 255</div>
                        </div>
                        <Maximize2 size={22} color="var(--text-muted)" />
                      </div>

                      <div className="stat-card">
                        <div>
                          <div className="stat-card-label">Quadrant Variance</div>
                          <div className="stat-card-val" style={{ color: ela.variance > 15 ? '#d97706' : 'var(--text-main)' }}>
                            {ela.variance}
                          </div>
                        </div>
                        <Sliders size={22} color="var(--text-muted)" />
                      </div>

                      <div className="stat-card">
                        <div>
                          <div className="stat-card-label">Compression Verdict</div>
                          <div style={{ marginTop: '4px' }}>
                            <StatusBadge
                              status={ela.indicator_detected ? 'ANOMALY FLAGGED' : 'CONSISTENT'}
                              variant={ela.indicator_detected ? 'warning' : 'success'}
                            />
                          </div>
                        </div>
                        <ShieldCheck size={22} color={ela.indicator_detected ? '#d97706' : '#16a34a'} />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: EXIF */}
              {imageTab === 'exif' && (
                <div>
                  <div className="stats-grid" style={{ marginBottom: '20px' }}>
                    <div className="stat-card">
                      <div>
                        <div className="stat-card-label">Camera Hardware</div>
                        <div className="stat-card-val" style={{ fontSize: '15px' }}>
                          {meta.camera_make ? `${meta.camera_make} ${meta.camera_model || ''}` : 'No Make/Model Tag'}
                        </div>
                      </div>
                      <Camera size={22} color="var(--text-muted)" />
                    </div>

                    <div className="stat-card">
                      <div>
                        <div className="stat-card-label">Software Signature</div>
                        <div className="stat-card-val" style={{ fontSize: '14px', color: meta.software ? '#d97706' : 'var(--text-main)' }}>
                          {meta.software || 'No Software Tag'}
                        </div>
                      </div>
                      <FileCode size={22} color="var(--text-muted)" />
                    </div>

                    <div className="stat-card">
                      <div>
                        <div className="stat-card-label">Capture Timestamp</div>
                        <div className="stat-card-val" style={{ fontSize: '14px' }}>
                          {meta.capture_date || 'No Date Tag'}
                        </div>
                      </div>
                      <Clock size={22} color="var(--text-muted)" />
                    </div>

                    <div className="stat-card">
                      <div>
                        <div className="stat-card-label">Embedded GPS</div>
                        <div className="stat-card-val" style={{ fontSize: '14px' }}>
                          {meta.gps ? `${meta.gps.latitude.toFixed(4)}, ${meta.gps.longitude.toFixed(4)}` : 'No Coordinates'}
                        </div>
                      </div>
                      <MapPin size={22} color="var(--text-muted)" />
                    </div>
                  </div>

                  <div className="card">
                    <div className="card-header">
                      <span className="card-title">Extracted EXIF Key-Value Dictionary</span>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Search EXIF tags..."
                        value={exifSearch}
                        onChange={(e) => setExifSearch(e.target.value)}
                        style={{ fontSize: '12px', padding: '4px 10px', width: '200px' }}
                      />
                    </div>

                    {filteredExif.length === 0 ? (
                      <p style={{ fontSize: '13px', color: 'var(--text-muted)', textAlign: 'center', padding: '24px' }}>
                        {meta.has_exif ? 'No matching tags found.' : 'No EXIF metadata was found embedded in this image.'}
                      </p>
                    ) : (
                      <div className="table-container" style={{ border: 'none', maxHeight: '360px', overflowY: 'auto' }}>
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th style={{ width: '220px' }}>EXIF Tag Name</th>
                              <th>Recorded Value</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredExif.map(([tag, val]) => (
                              <tr key={tag}>
                                <td style={{ fontWeight: 600, fontSize: '12px', color: '#1e293b' }}>{tag}</td>
                                <td className="mono" style={{ fontSize: '12px', wordBreak: 'break-all' }}>
                                  {val}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 3: FINDINGS */}
              {imageTab === 'findings' && (
                <div className="card" style={{ marginBottom: '20px' }}>
                  <div className="card-header">
                    <span className="card-title">Categorized Forensic Findings & Indicators</span>
                    <span className="badge badge-neutral">
                      {meta.findings.length + (ela?.findings.length || 0)} Total Observations
                    </span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '8px 0' }}>
                    {[...meta.findings, ...(ela?.findings || [])].map((finding, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '14px 16px',
                          borderRadius: '4px',
                          border: '1px solid #e2e8f0',
                          borderLeftWidth: '4px',
                          borderLeftColor:
                            finding.severity === 'high'
                              ? '#dc2626'
                              : finding.severity === 'medium'
                              ? '#f59e0b'
                              : '#3b82f6',
                          background: '#f8fafc',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span
                            className={`badge ${
                              finding.severity === 'high'
                                ? 'badge-danger'
                                : finding.severity === 'medium'
                                ? 'badge-warning'
                                : 'badge-neutral'
                            }`}
                          >
                            {finding.severity.toUpperCase()}
                          </span>
                          <strong style={{ fontSize: '13px', color: '#0f172a' }}>{finding.title}</strong>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                            {finding.category}
                          </span>
                        </div>
                        <p style={{ fontSize: '13px', color: '#334155', margin: '4px 0 0', lineHeight: 1.5 }}>
                          {finding.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Forensic Ethics & Limitations Box (Mandatory spec.md FR-05 & FR-06) */}
          <div
            style={{
              background: '#f1f5f9',
              border: '1px solid #e2e8f0',
              borderRadius: '4px',
              padding: '14px 18px',
              fontSize: '12px',
              color: '#475569',
              display: 'flex',
              gap: '10px',
              alignItems: 'flex-start',
            }}
          >
            <Info size={16} color="#2563eb" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong>Forensic Ethics & Prototype Disclaimer:</strong>
              <div style={{ marginTop: '4px', lineHeight: 1.5 }}>{currentLimitations}</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
