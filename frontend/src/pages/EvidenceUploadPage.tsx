import React, { useState, useEffect, useRef } from 'react';
import type { PageId, CaseSummary, EvidenceItem } from '../types';
import { fetchCases, uploadEvidence } from '../api/client';
import {
  Upload,
  FileCheck2,
  AlertTriangle,
  FileImage,
  FileVideo,
  FileAudio,
  Folder,
  User,
  ShieldCheck,
  Copy,
  Check,
  ArrowRight,
  RefreshCw,
  Files,
  File as FileIcon,
  X,
  Plus,
} from 'lucide-react';

interface EvidenceUploadPageProps {
  initialCaseId?: string | number | null;
  initialMode?: 'single' | 'batch';
  onNavigate: (page: PageId, caseId?: string | number, evidenceId?: number) => void;
}

interface BatchItemStatus {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  evidence?: EvidenceItem;
  error?: string;
}

export const EvidenceUploadPage: React.FC<EvidenceUploadPageProps> = ({
  initialCaseId,
  initialMode,
  onNavigate,
}) => {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<number | ''>(
    initialCaseId ? Number(initialCaseId) : ''
  );
  const [investigatorName, setInvestigatorName] = useState<string>('');
  
  // Upload Mode: 'single' or 'batch'
  const [uploadMode, setUploadMode] = useState<'single' | 'batch'>(() => {
    if (initialMode) return initialMode;
    const pref = typeof window !== 'undefined' ? sessionStorage.getItem('preferredUploadMode') : null;
    if (pref === 'batch' || pref === 'single') {
      sessionStorage.removeItem('preferredUploadMode');
      return pref;
    }
    return 'single';
  });

  // Single Upload States
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [uploadedEvidence, setUploadedEvidence] = useState<EvidenceItem | null>(null);

  // Batch Upload States
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [batchQueue, setBatchQueue] = useState<BatchItemStatus[]>([]);
  const [batchSuccessItems, setBatchSuccessItems] = useState<EvidenceItem[]>([]);

  const [dragOver, setDragOver] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<boolean>(false);

  const singleFileInputRef = useRef<HTMLInputElement>(null);
  const batchFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function loadCases() {
      try {
        const list = await fetchCases();
        setCases(list);
        if (initialCaseId) {
          const numId = Number(initialCaseId);
          setSelectedCaseId(numId);
          const found = list.find((c) => c.id === numId);
          if (found) {
            setInvestigatorName(found.investigator_name);
          }
        } else if (list.length > 0 && selectedCaseId === '') {
          setSelectedCaseId(list[0].id);
          setInvestigatorName(list[0].investigator_name);
        }
      } catch (err) {
        console.error('Failed to load cases:', err);
      }
    }
    loadCases();
  }, [initialCaseId]);

  const handleCaseChange = (caseId: number) => {
    setSelectedCaseId(caseId);
    const found = cases.find((c) => c.id === caseId);
    if (found) {
      setInvestigatorName(found.investigator_name);
    }
  };

  const validateFile = (fileToValidate: File): string | null => {
    const maxSizeBytes = 100 * 1024 * 1024;
    if (fileToValidate.size > maxSizeBytes) {
      return `File size exceeds 100 MB limit (${(fileToValidate.size / (1024 * 1024)).toFixed(1)} MB).`;
    }
    const ext = '.' + fileToValidate.name.split('.').pop()?.toLowerCase();
    const allowed = ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi', '.wav', '.mp3'];
    if (!allowed.includes(ext)) {
      return `Unsupported format '${ext}'. Digital evidence must be JPG, PNG, MP4, MOV, AVI, WAV, or MP3.`;
    }
    return null;
  };

  // --- Single Upload Handlers ---
  const handleSingleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const err = validateFile(e.dataTransfer.files[0]);
      if (err) {
        setError(err);
        return;
      }
      setError(null);
      setUploadedEvidence(null);
      setSingleFile(e.dataTransfer.files[0]);
    }
  };

  const handleSingleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const err = validateFile(e.target.files[0]);
      if (err) {
        setError(err);
        return;
      }
      setError(null);
      setUploadedEvidence(null);
      setSingleFile(e.target.files[0]);
    }
  };

  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCaseId) {
      setError('Please select an active investigation case.');
      return;
    }
    if (!singleFile) {
      setError('Please choose or drop an evidence media file to ingest.');
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const result = await uploadEvidence(Number(selectedCaseId), singleFile, investigatorName);
      setUploadedEvidence(result);
      setSingleFile(null);
      if (singleFileInputRef.current) {
        singleFileInputRef.current.value = '';
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Evidence upload failed.');
    } finally {
      setIsUploading(false);
    }
  };

  // --- Batch Upload Handlers ---
  const handleBatchFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addBatchFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleBatchFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addBatchFiles(Array.from(e.target.files));
    }
  };

  const addBatchFiles = (newFiles: File[]) => {
    setError(null);
    setBatchSuccessItems([]);
    const validFiles: File[] = [];
    const errors: string[] = [];

    newFiles.forEach((f) => {
      const err = validateFile(f);
      if (err) {
        errors.push(`${f.name}: ${err}`);
      } else {
        if (!batchFiles.some((existing) => existing.name === f.name && existing.size === f.size)) {
          validFiles.push(f);
        }
      }
    });

    if (errors.length > 0) {
      setError(errors.slice(0, 3).join(' | '));
    }

    const updated = [...batchFiles, ...validFiles];
    setBatchFiles(updated);
    setBatchQueue(updated.map((f) => ({ file: f, status: 'pending' })));
  };

  const removeBatchFile = (index: number) => {
    const updated = batchFiles.filter((_, i) => i !== index);
    setBatchFiles(updated);
    setBatchQueue(updated.map((f) => ({ file: f, status: 'pending' })));
  };

  const clearBatchFiles = () => {
    setBatchFiles([]);
    setBatchQueue([]);
    setError(null);
    if (batchFileInputRef.current) {
      batchFileInputRef.current.value = '';
    }
  };

  const handleBatchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCaseId) {
      setError('Please select an active investigation case.');
      return;
    }
    if (batchFiles.length === 0) {
      setError('Please select at least one evidence image or media file to ingest.');
      return;
    }

    setIsUploading(true);
    setError(null);
    setBatchSuccessItems([]);

    const succeeded: EvidenceItem[] = [];
    const currentQueue: BatchItemStatus[] = batchFiles.map((f) => ({ file: f, status: 'pending' }));
    setBatchQueue([...currentQueue]);

    for (let i = 0; i < batchFiles.length; i++) {
      const file = batchFiles[i];
      currentQueue[i] = { file, status: 'uploading' };
      setBatchQueue([...currentQueue]);

      try {
        const item = await uploadEvidence(Number(selectedCaseId), file, investigatorName);
        succeeded.push(item);
        currentQueue[i] = { file, status: 'success', evidence: item };
        setBatchQueue([...currentQueue]);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        currentQueue[i] = { file, status: 'error', error: msg };
        setBatchQueue([...currentQueue]);
      }
    }

    setBatchSuccessItems(succeeded);
    setIsUploading(false);

    if (succeeded.length === batchFiles.length) {
      setBatchFiles([]);
    }
  };

  const copyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase();
    if (['jpg', 'jpeg', 'png'].includes(ext || '')) {
      return <FileImage size={24} color="#2563eb" />;
    }
    if (['mp4', 'mov', 'avi'].includes(ext || '')) {
      return <FileVideo size={24} color="#7c3aed" />;
    }
    if (['wav', 'mp3'].includes(ext || '')) {
      return <FileAudio size={24} color="#059669" />;
    }
    return <Upload size={24} color="#2563eb" />;
  };

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 className="page-title">Digital Evidence Ingestion</h1>
          <p className="page-subtitle">
            Secure, byte-preserving intake of digital media with cryptographic SHA-256 baseline hashing (FR-03 &amp; FR-04).
          </p>
        </div>

        {/* Quick Mode Toggle Action Buttons */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            type="button"
            className={uploadMode === 'single' ? 'btn btn-secondary' : 'btn btn-secondary'}
            onClick={() => {
              setUploadMode('single');
              setError(null);
            }}
            disabled={isUploading}
            style={{
              fontSize: '12px',
              padding: '6px 12px',
              fontWeight: uploadMode === 'single' ? 700 : 500,
              background: uploadMode === 'single' ? '#f1f5f9' : '#ffffff',
              borderColor: uploadMode === 'single' ? '#0f172a' : '#cbd5e1',
              color: '#0f172a',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <FileIcon size={14} />
            <span>Single File</span>
          </button>

          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setUploadMode('batch');
              setError(null);
              setTimeout(() => batchFileInputRef.current?.click(), 80);
            }}
            disabled={isUploading}
            style={{
              fontSize: '12px',
              padding: '6px 14px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Upload multiple photos or evidence files at once"
          >
            <Files size={14} />
            <span>+ Add Multiple Images</span>
          </button>
        </div>
      </div>

      <div className="notice-box notice-info" style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span className="badge badge-primary" style={{ padding: '3px 8px', fontSize: '11px', fontWeight: 700 }}>STEP 2 OF 5</span>
        <span style={{ fontSize: '12px' }}>
          <strong>Secure Media Ingestion:</strong> Select the target case and upload seized media (single file or multiple images at once). Original bytes are preserved in protected storage and an unalterable baseline SHA-256 hash is calculated.
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
          <AlertTriangle size={18} style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </div>
      )}

      {/* Single Upload Success Banner */}
      {uploadedEvidence && (
        <div
          style={{
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            color: '#166534',
            padding: '20px',
            borderRadius: '4px',
            marginBottom: '24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <FileCheck2 size={20} color="#16a34a" />
            <strong style={{ fontSize: '15px' }}>Evidence Registered Successfully</strong>
            <span className="badge badge-success" style={{ marginLeft: 'auto' }}>
              SHA-256 HASH VERIFIED
            </span>
          </div>

          <p style={{ fontSize: '13px', marginBottom: '14px', color: '#14532d' }}>
            The file bytes have been stored unmodified in protected isolated storage. Baseline cryptographic digest calculated:
          </p>

          <div
            style={{
              background: '#ffffff',
              border: '1px solid #dcfce7',
              borderRadius: '4px',
              padding: '12px 16px',
              marginBottom: '16px',
              fontSize: '13px',
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', marginBottom: '6px' }}>
              <span style={{ color: '#4b5563', fontWeight: 500 }}>Evidence Number:</span>
              <span style={{ fontWeight: 600, color: '#111827' }}>{uploadedEvidence.evidence_number}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', marginBottom: '6px' }}>
              <span style={{ color: '#4b5563', fontWeight: 500 }}>Original Filename:</span>
              <span style={{ fontWeight: 500, color: '#111827' }}>{uploadedEvidence.original_filename}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', marginBottom: '6px' }}>
              <span style={{ color: '#4b5563', fontWeight: 500 }}>File Type & Size:</span>
              <span>
                <span className="badge badge-neutral" style={{ marginRight: '8px' }}>
                  {uploadedEvidence.detected_file_type.toUpperCase()}
                </span>
                {(uploadedEvidence.file_size / 1024).toFixed(1)} KB ({uploadedEvidence.file_size.toLocaleString()} bytes)
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px', alignItems: 'center' }}>
              <span style={{ color: '#4b5563', fontWeight: 500 }}>SHA-256 Digest:</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="mono" style={{ fontSize: '12px', background: '#f8fafc', padding: '2px 8px', borderRadius: '3px', border: '1px solid #e2e8f0' }}>
                  {uploadedEvidence.sha256_hash}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: '2px 8px', fontSize: '11px' }}
                  onClick={() => copyHash(uploadedEvidence.sha256_hash)}
                  title="Copy SHA-256"
                >
                  {copiedHash ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
                  <span>{copiedHash ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button
              className="btn btn-primary"
              style={{ fontSize: '12px' }}
              onClick={() => onNavigate('evidence-details', undefined, uploadedEvidence.id)}
            >
              <span>Examine Evidence Dossier</span>
              <ArrowRight size={13} />
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: '12px' }}
              onClick={() => onNavigate('integrity-check')}
            >
              <ShieldCheck size={13} />
              <span>Open Integrity Dashboard</span>
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: '12px' }}
              onClick={() => {
                setUploadedEvidence(null);
                setSingleFile(null);
              }}
            >
              <span>Upload Another File</span>
            </button>
          </div>
        </div>
      )}

      {/* Batch Upload Success Banner */}
      {batchSuccessItems.length > 0 && (
        <div
          style={{
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            color: '#166534',
            padding: '20px',
            borderRadius: '4px',
            marginBottom: '24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <FileCheck2 size={20} color="#16a34a" />
            <strong style={{ fontSize: '15px' }}>
              Batch Ingestion Completed: {batchSuccessItems.length} Evidence Items Registered
            </strong>
            <span className="badge badge-success" style={{ marginLeft: 'auto' }}>
              ALL SHA-256 HASHES VERIFIED
            </span>
          </div>

          <p style={{ fontSize: '13px', marginBottom: '14px', color: '#14532d' }}>
            All selected media files have been securely stored with calculated baseline cryptographic digests:
          </p>

          <div style={{ background: '#ffffff', border: '1px solid #dcfce7', borderRadius: '4px', padding: '10px 14px', marginBottom: '16px', maxHeight: '200px', overflowY: 'auto' }}>
            {batchSuccessItems.map((item, idx) => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 0',
                  borderBottom: idx < batchSuccessItems.length - 1 ? '1px solid #f1f5f9' : 'none',
                  fontSize: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="badge badge-neutral" style={{ fontSize: '10px' }}>{item.detected_file_type.toUpperCase()}</span>
                  <span style={{ fontWeight: 600 }}>{item.evidence_number}</span>
                  <span style={{ color: '#64748b' }}>({item.original_filename})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="mono" style={{ fontSize: '11px', color: '#475569' }}>
                    {item.sha256_hash.slice(0, 16)}...{item.sha256_hash.slice(-8)}
                  </span>
                  <span className="badge badge-success" style={{ fontSize: '10px' }}>VERIFIED</span>
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {selectedCaseId && (
              <button
                className="btn btn-primary"
                style={{ fontSize: '12px' }}
                onClick={() => onNavigate('case-details', selectedCaseId)}
              >
                <span>View Case Evidence Manifest</span>
                <ArrowRight size={13} />
              </button>
            )}
            <button
              className="btn btn-secondary"
              style={{ fontSize: '12px' }}
              onClick={() => onNavigate('integrity-check')}
            >
              <ShieldCheck size={13} />
              <span>Verify Hashes in Integrity Dashboard</span>
            </button>
            <button
              className="btn btn-secondary"
              style={{ fontSize: '12px' }}
              onClick={() => {
                setBatchSuccessItems([]);
                setBatchFiles([]);
                setBatchQueue([]);
              }}
            >
              <span>Upload More Files</span>
            </button>
          </div>
        </div>
      )}

      {/* Intake Form Card */}
      <div className="card">
        {/* Mode Selector Tabs */}
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #e2e8f0', paddingBottom: '14px', marginBottom: '20px' }}>
          <button
            type="button"
            onClick={() => {
              setUploadMode('single');
              setError(null);
            }}
            disabled={isUploading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              fontSize: '13px',
              fontWeight: uploadMode === 'single' ? 600 : 500,
              background: uploadMode === 'single' ? '#0f172a' : '#f1f5f9',
              color: uploadMode === 'single' ? '#ffffff' : '#475569',
              border: 'none',
              borderRadius: '6px',
              cursor: isUploading ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <FileIcon size={15} />
            <span>Single File Ingestion</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setUploadMode('batch');
              setError(null);
            }}
            disabled={isUploading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              fontSize: '13px',
              fontWeight: uploadMode === 'batch' ? 600 : 500,
              background: uploadMode === 'batch' ? '#0f172a' : '#f1f5f9',
              color: uploadMode === 'batch' ? '#ffffff' : '#475569',
              border: 'none',
              borderRadius: '6px',
              cursor: isUploading ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Files size={15} />
            <span>Batch Upload (Multiple Images / Files)</span>
            <span
              style={{
                background: uploadMode === 'batch' ? '#334155' : '#e2e8f0',
                color: uploadMode === 'batch' ? '#f8fafc' : '#0f172a',
                fontSize: '10px',
                fontWeight: 700,
                padding: '1px 6px',
                borderRadius: '10px',
                marginLeft: '4px',
              }}
            >
              MULTI-IMAGE
            </span>
          </button>
        </div>

        {/* Target Investigation Case */}
        <div className="form-group">
          <label className="form-label" htmlFor="case-select">
            <Folder size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: '-2px' }} />
            Associate with Investigation Case *
          </label>
          <select
            id="case-select"
            className="form-input"
            value={selectedCaseId}
            onChange={(e) => handleCaseChange(Number(e.target.value))}
            disabled={isUploading}
            required
          >
            <option value="" disabled>-- Select Investigation Case --</option>
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.case_number} — {c.title} ({c.status.toUpperCase()})
              </option>
            ))}
          </select>
          <div className="form-help">
            Every digital evidence file must be registered under an existing, authorized investigation case.
          </div>
        </div>

        {/* Investigating Officer */}
        <div className="form-group">
          <label className="form-label" htmlFor="investigator-name">
            <User size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: '-2px' }} />
            Intake Officer / Chain of Custody Actor
          </label>
          <input
            id="investigator-name"
            type="text"
            className="form-input"
            value={investigatorName}
            onChange={(e) => setInvestigatorName(e.target.value)}
            placeholder="e.g. Inspector R. Sharma (Cyber Cell)"
            disabled={isUploading}
          />
          <div className="form-help">
            The investigating officer name recorded in the permanent audit trail for this ingestion event.
          </div>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* MODE 1: SINGLE FILE INGESTION FORM                           */}
        {/* ------------------------------------------------------------- */}
        {uploadMode === 'single' ? (
          <form onSubmit={handleSingleSubmit}>
            <div className="form-group">
              <label className="form-label">Digital Evidence File *</label>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleSingleFileDrop}
                onClick={() => singleFileInputRef.current?.click()}
                style={{
                  border: dragOver ? '2px dashed var(--primary-blue)' : '2px dashed #cbd5e1',
                  borderRadius: '6px',
                  padding: '36px 20px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  background: dragOver ? '#eff6ff' : '#f8fafc',
                  transition: 'all 0.2s ease',
                }}
              >
                <input
                  ref={singleFileInputRef}
                  type="file"
                  style={{ display: 'none' }}
                  accept=".jpg,.jpeg,.png,.mp4,.mov,.avi,.wav,.mp3"
                  onChange={handleSingleFileSelect}
                  disabled={isUploading}
                />

                {singleFile ? (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px' }}>
                      {getFileIcon(singleFile.name)}
                    </div>
                    <div style={{ fontWeight: 600, fontSize: '14px', color: '#1e293b', marginBottom: '4px' }}>
                      {singleFile.name}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      {(singleFile.size / 1024).toFixed(1)} KB ({(singleFile.size / (1024 * 1024)).toFixed(2)} MB)
                    </div>
                    <span className="badge badge-success" style={{ marginTop: '8px' }}>
                      READY FOR FORENSIC HASHING
                    </span>
                  </div>
                ) : (
                  <div>
                    <Upload size={36} color="#64748b" style={{ marginBottom: '10px' }} />
                    <div style={{ fontWeight: 600, fontSize: '14px', color: '#1e293b', marginBottom: '4px' }}>
                      Drag and drop digital evidence here, or click to browse
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '420px', margin: '0 auto' }}>
                      Supported media: Image (JPG, PNG), Video (MP4, MOV, AVI), Audio (WAV, MP3). Maximum file size: 100 MB.
                    </div>
                    
                    <div
                      style={{
                        marginTop: '16px',
                        paddingTop: '12px',
                        borderTop: '1px dashed #cbd5e1',
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        gap: '8px',
                        flexWrap: 'wrap',
                      }}
                    >
                      <span style={{ fontSize: '12px', color: '#64748b' }}>
                        Have multiple images for this case?
                      </span>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{
                          fontSize: '11px',
                          padding: '4px 10px',
                          color: '#2563eb',
                          borderColor: '#93c5fd',
                          background: '#eff6ff',
                          fontWeight: 600,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setUploadMode('batch');
                          setTimeout(() => batchFileInputRef.current?.click(), 80);
                        }}
                      >
                        <Files size={12} />
                        <span>Switch to Add Multiple Images</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Protocol Guarantee Card */}
            <div
              style={{
                background: '#f1f5f9',
                border: '1px solid #e2e8f0',
                borderRadius: '4px',
                padding: '12px 16px',
                marginBottom: '20px',
                fontSize: '12px',
                color: '#475569',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', color: '#0f172a', fontWeight: 600 }}>
                <ShieldCheck size={14} color="#16a34a" />
                <span>Evidence Preservation & Chain-of-Custody Guarantee</span>
              </div>
              Original bytes are stored unmodified in private storage outside public directories. A SHA-256 digest is calculated synchronously at ingestion to serve as the legal reference baseline for all future authenticity and tamper verifications.
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isUploading || !singleFile || !selectedCaseId}
              >
                {isUploading ? (
                  <>
                    <RefreshCw size={14} className="spin" />
                    <span>Calculating SHA-256 & Registering...</span>
                  </>
                ) : (
                  <>
                    <Upload size={14} />
                    <span>Ingest & Calculate Baseline Hash</span>
                  </>
                )}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  if (selectedCaseId) {
                    onNavigate('case-details', selectedCaseId);
                  } else {
                    onNavigate('my-cases');
                  }
                }}
                disabled={isUploading}
              >
                <span>Cancel</span>
              </button>
            </div>
          </form>
        ) : (
          /* ------------------------------------------------------------- */
          /* MODE 2: BATCH / MULTIPLE IMAGES INGESTION FORM               */
          /* ------------------------------------------------------------- */
          <form onSubmit={handleBatchSubmit}>
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <label className="form-label" style={{ marginBottom: 0 }}>
                  Multiple Evidence Files (Batch Selection) *
                </label>
                {batchFiles.length > 0 && (
                  <span style={{ fontSize: '12px', color: '#4b5563', fontWeight: 500 }}>
                    {batchFiles.length} file(s) selected ({((batchFiles.reduce((acc, f) => acc + f.size, 0)) / (1024 * 1024)).toFixed(2)} MB)
                  </span>
                )}
              </div>

              {/* Multi-file Dropzone */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleBatchFileDrop}
                onClick={() => batchFileInputRef.current?.click()}
                style={{
                  border: dragOver ? '2px dashed var(--primary-blue)' : '2px dashed #cbd5e1',
                  borderRadius: '6px',
                  padding: '30px 20px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  background: dragOver ? '#eff6ff' : '#f8fafc',
                  transition: 'all 0.2s ease',
                  marginBottom: '14px',
                }}
              >
                <input
                  ref={batchFileInputRef}
                  type="file"
                  multiple
                  style={{ display: 'none' }}
                  accept=".jpg,.jpeg,.png,.mp4,.mov,.avi,.wav,.mp3"
                  onChange={handleBatchFileSelect}
                  disabled={isUploading}
                />

                <Files size={36} color="#475569" style={{ marginBottom: '8px' }} />
                <div style={{ fontWeight: 600, fontSize: '14px', color: '#1e293b', marginBottom: '4px' }}>
                  Select or drag multiple images & evidence files together
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '440px', margin: '0 auto 12px' }}>
                  Hold <kbd style={{ background: '#e2e8f0', padding: '1px 5px', borderRadius: '3px', fontSize: '11px' }}>Ctrl</kbd> or <kbd style={{ background: '#e2e8f0', padding: '1px 5px', borderRadius: '3px', fontSize: '11px' }}>Shift</kbd> in file dialog to pick multiple photos. Max 100 MB per file.
                </div>
                
                <div>
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ fontSize: '12px', padding: '6px 14px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      batchFileInputRef.current?.click();
                    }}
                    disabled={isUploading}
                  >
                    <Plus size={14} />
                    <span>Choose Multiple Images / Files</span>
                  </button>
                </div>
              </div>

              {/* Selected Files Preview Queue */}
              {batchFiles.length > 0 && (
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '12px', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', borderBottom: '1px solid #f1f5f9', paddingBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>
                      <Files size={15} color="#2563eb" />
                      <span>Ingestion Queue ({batchFiles.length} files)</span>
                    </div>
                    {!isUploading && (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ fontSize: '11px', padding: '3px 8px' }}
                          onClick={() => batchFileInputRef.current?.click()}
                        >
                          <Plus size={12} />
                          <span>Add More Files</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          style={{ fontSize: '11px', padding: '3px 8px', color: '#dc2626' }}
                          onClick={clearBatchFiles}
                        >
                          <X size={12} />
                          <span>Clear All</span>
                        </button>
                      </div>
                    )}
                  </div>

                  <div style={{ maxHeight: '220px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {batchQueue.map((item, idx) => (
                      <div
                        key={`${item.file.name}-${idx}`}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '8px 10px',
                          background: item.status === 'uploading' ? '#eff6ff' : item.status === 'success' ? '#f0fdf4' : item.status === 'error' ? '#fef2f2' : '#f8fafc',
                          border: '1px solid',
                          borderColor: item.status === 'uploading' ? '#bfdbfe' : item.status === 'success' ? '#bbf7d0' : item.status === 'error' ? '#fecaca' : '#f1f5f9',
                          borderRadius: '4px',
                          fontSize: '12px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                          <span style={{ color: '#64748b', fontSize: '11px', fontWeight: 600, width: '20px' }}>#{idx + 1}</span>
                          <span style={{ fontWeight: 500, color: '#1e293b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {item.file.name}
                          </span>
                          <span style={{ color: '#64748b', fontSize: '11px' }}>
                            ({(item.file.size / 1024).toFixed(1)} KB)
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          {item.status === 'pending' && (
                            <span className="badge badge-neutral" style={{ fontSize: '10px' }}>READY</span>
                          )}
                          {item.status === 'uploading' && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#2563eb', fontWeight: 600, fontSize: '11px' }}>
                              <RefreshCw size={12} className="spin" />
                              <span>Hashing &amp; Ingesting...</span>
                            </div>
                          )}
                          {item.status === 'success' && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontWeight: 600, color: '#16a34a', fontSize: '11px' }}>{item.evidence?.evidence_number}</span>
                              <span className="badge badge-success" style={{ fontSize: '10px' }}>VERIFIED</span>
                            </div>
                          )}
                          {item.status === 'error' && (
                            <span className="badge badge-danger" style={{ fontSize: '10px' }}>FAILED: {item.error}</span>
                          )}

                          {!isUploading && item.status === 'pending' && (
                            <button
                              type="button"
                              onClick={() => removeBatchFile(idx)}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', color: '#94a3b8' }}
                              title="Remove file"
                            >
                              <X size={14} />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Protocol Guarantee Card */}
            <div
              style={{
                background: '#f1f5f9',
                border: '1px solid #e2e8f0',
                borderRadius: '4px',
                padding: '12px 16px',
                marginBottom: '20px',
                fontSize: '12px',
                color: '#475569',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', color: '#0f172a', fontWeight: 600 }}>
                <ShieldCheck size={14} color="#16a34a" />
                <span>Batch Evidence Integrity Guarantee</span>
              </div>
              Each evidence item is assigned an individual police evidence number (`EVID-2026-XXXX`). Original file bytes are stored unmodified in isolated storage, and an immutable SHA-256 reference digest is computed synchronously for each item.
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isUploading || batchFiles.length === 0 || !selectedCaseId}
              >
                {isUploading ? (
                  <>
                    <RefreshCw size={14} className="spin" />
                    <span>Ingesting Batch Evidence ({batchQueue.filter((q) => q.status === 'success').length}/{batchFiles.length})...</span>
                  </>
                ) : (
                  <>
                    <Upload size={14} />
                    <span>Ingest All {batchFiles.length > 0 ? `${batchFiles.length} Evidence Items` : 'Selected Items'}</span>
                  </>
                )}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  if (selectedCaseId) {
                    onNavigate('case-details', selectedCaseId);
                  } else {
                    onNavigate('my-cases');
                  }
                }}
                disabled={isUploading}
              >
                <span>Cancel</span>
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
