# EvidenceGuard AI — Digital Evidence Platform

**Cyber Hackathon Bihar Police 2026**  
**Problem Statement:** PS-5 — Digital Evidence Authenticity and Integrity Verification Platform  
**Status:** All 9 Phases Implemented & Verified (Version 1.0.0)

---

## 1. Project Overview

EvidenceGuard AI is a digital forensic verification platform prototype designed to assist authorized law enforcement investigators and digital forensics units. Built for the **Cyber Hackathon Bihar Police 2026 (Problem Statement 5)**, the platform provides an explainable workflow for registering criminal cases, securely ingesting multi-modal digital evidence, cryptographically verifying byte-level integrity with SHA-256, extracting and evaluating hardware/software metadata, detecting manipulation anomalies across images, CCTV video, and audio recordings, performing cross-evidence timeline and consistency analysis, maintaining a chain-of-custody audit log, and generating structured forensic PDF examination reports.

> **Forensic Ethics & Prototype Disclaimer (spec.md §FR-10 & §15):**  
> This platform is an investigation support prototype and is not a certified judicial forensic laboratory tool. Cryptographic SHA-256 hash verifications confirm byte-level equality with the reference baseline recorded at intake; they do not establish the antecedent authenticity of a file prior to registration. Forensic indicators (such as ELA variances, duplicate CCTV frames, timestamp deltas, and audio clipping) represent anomalies that require corroborating human inquiry and do not automatically prove malicious tampering or fabrication.

---

## 2. Technology Stack

### Backend
- **Python 3.14+**
- **FastAPI**: Modern, asynchronous web framework with automatic OpenAPI documentation.
- **SQLAlchemy 2.0**: Relational ORM supporting local SQLite development and seamless PostgreSQL migration.
- **Pydantic v2**: Request validation and typed schemas.
- **ReportLab 5.1**: Automated forensic PDF document compiler.
- **OpenCV & NumPy**: Video frame extraction and continuity auditing.
- **Pillow (PIL)**: Image metadata extraction and Error Level Analysis (ELA).
- **Pytest**: Comprehensive automated unit, integration, and security test suite.

### Frontend
- **React 18** with **TypeScript** and **Vite**
- **Vanilla CSS Design System**: Custom police-investigator interface matching `spec.md §9` (light background `#f8fafc`, dark navy sidebar `#0f172a`, restrained blue accents `#1e40af`, readable tabular layouts, zero distracting neon/glassmorphism).
- **Lucide React**: Forensic and law-enforcement icons.

---

## 3. Architecture & Repository Structure

```text
cyber/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py            # Environment configuration & directory provisioning
│   │   ├── database.py          # Database engine & session management
│   │   ├── main.py              # FastAPI application, security headers & exception handling
│   │   ├── models/              # SQLAlchemy database entities
│   │   │   ├── case.py          # Investigation Cases
│   │   │   ├── evidence.py      # Digital Evidence registry
│   │   │   ├── integrity.py     # SHA-256 check history
│   │   │   ├── analysis.py      # Forensic analysis results
│   │   │   ├── audit.py         # Chain of Custody audit events
│   │   │   └── report.py        # PDF report records
│   │   ├── routers/             # REST API controllers
│   │   │   ├── health.py        # Diagnostic health probe
│   │   │   ├── cases.py         # Case management & cross-evidence API
│   │   │   ├── evidence.py      # Secure evidence ingestion & integrity verification
│   │   │   ├── analysis.py      # Image, Video & Audio forensic analysis API
│   │   │   ├── reports.py       # PDF report generation & secure download API
│   │   │   └── audit.py         # Chain of custody audit query API
│   │   ├── schemas/             # Pydantic validation & transfer schemas
│   │   │   ├── case.py
│   │   │   ├── evidence.py
│   │   │   ├── analysis.py
│   │   │   ├── cross_evidence.py
│   │   │   ├── report.py
│   │   │   └── audit.py
│   │   └── utils/               # Forensic processing engines
│   │       ├── forensics.py     # Magic bytes inspection & SHA-256 calculation
│   │       ├── image_analysis.py# EXIF parser & ELA heatmap generator
│   │       ├── video_analysis.py# OpenCV frame sampler & duplicate detector
│   │       ├── audio_analysis.py# Waveform sampler, clipping & silence checker
│   │       ├── cross_evidence.py# Cross-evidence multi-dimensional comparator
│   │       └── pdf_report.py    # ReportLab structured PDF generator
│   ├── storage/                 # Isolated local evidence storage (gitignored)
│   │   ├── evidence/            # Original preserved evidence bytes
│   │   ├── derived/             # Derived analysis artifacts (ELA maps, thumbnails)
│   │   └── reports/             # Generated forensic PDF reports
│   ├── tests/                   # 55 passing automated pytest tests
│   │   ├── test_health.py
│   │   ├── test_cases.py
│   │   ├── test_evidence.py
│   │   ├── test_image_analysis.py
│   │   ├── test_video_analysis.py
│   │   ├── test_audio_analysis.py
│   │   ├── test_cross_evidence.py
│   │   ├── test_reports_and_audit.py
│   │   └── test_security_review.py
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # Strongly-typed API client routines
│   │   ├── components/          # Reusable UI components (Sidebar, Topbar, StatusBadge)
│   │   ├── pages/               # Functional investigator pages
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── CreateCasePage.tsx
│   │   │   ├── MyCasesPage.tsx
│   │   │   ├── CaseDetailPage.tsx
│   │   │   ├── EvidenceUploadPage.tsx
│   │   │   ├── EvidenceDetailPage.tsx
│   │   │   ├── IntegrityCheckPage.tsx
│   │   │   ├── AnalysisResultsPage.tsx
│   │   │   ├── CrossCheckPage.tsx
│   │   │   ├── ReportsPage.tsx
│   │   │   ├── AuditLogPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   ├── types.ts             # TypeScript interfaces
│   │   ├── index.css            # Law enforcement UI design system
│   │   └── App.tsx              # Top-level client routing
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── .env.example
├── .gitignore
├── spec.md
└── README.md
```

---

## 4. Supported Evidence Formats

| Format | Extensions | Magic Bytes Validation | Supported Forensic Checks |
|---|---|---|---|
| **Images** | `.jpg`, `.jpeg`, `.png` | Verified (`FF D8 FF`, `89 50 4E 47`) | EXIF extraction, camera make/model, capture dates, GPS coords, software signatures, Error Level Analysis (ELA) |
| **Video / CCTV** | `.mp4`, `.mov`, `.avi` | Verified (`ftyp`, `moov`, `RIFF AVI`) | Duration, resolution, FPS, codec, frame extraction, exact duplicate & frozen frame detection |
| **Audio** | `.wav`, `.mp3` | Verified (`RIFF WAVE`, `ID3` / `FF FB`) | Sample rate, channels, bit depth, DAW editing software tags, 0 dBFS clipping detection, digital zero silence drop, SVG waveform envelope |

---

## 5. Security & Privacy Safeguards (spec.md §6 & Phase 9)

1. **Storage Isolation**: Uploaded evidence files are never stored in a publicly accessible directory or web root. Internal files are assigned UUID-based storage filenames.
2. **Byte Preservation**: Analysis is performed strictly on temporary buffers and in-memory streams; original uploaded evidence bytes are never altered.
3. **Magic Bytes Validation**: Files are checked against true binary signatures to block disguised or malicious executables (`.exe`, `.sh`, `.php`, `.bat`).
4. **Path Traversal Protection**: Filenames and asset endpoints are sanitized to eliminate directory traversal vectors (`../`, `..\`).
5. **Configurable Limits**: Ingestion enforces configurable file size limits (`MAX_UPLOAD_SIZE_BYTES=100MB`).
6. **Security Headers**: All HTTP responses include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, and `Referrer-Policy: strict-origin-when-cross-origin`.
7. **Safe Error Handling**: Internal Python tracebacks and filesystem paths are masked from API error responses.
8. **Transparent Audit Logging**: Audit events are persistently stored in the local relational database without false claims of blockchain immutability.

---

## 6. Setup and Installation

### Backend

1. **Activate virtual environment:**
   ```bash
   # Windows PowerShell:
   backend\venv\Scripts\Activate.ps1
   # Windows CMD:
   backend\venv\Scripts\activate.bat
   ```

2. **Install dependencies:**
   ```bash
   python -m pip install -r backend/requirements.txt
   ```

3. **Configure environment:**
   ```bash
   copy .env.example .env
   ```

4. **Run automated test suite (55 tests):**
   ```bash
   backend\venv\Scripts\python -m pytest backend\tests
   ```

5. **Start backend API server:**
   ```bash
   backend\venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload --port 8000
   ```
   Interactive Swagger docs: `http://127.0.0.1:8000/docs`  
   Health check: `http://127.0.0.1:8000/api/health`

### Frontend

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Compile production build:**
   ```bash
   cmd /c "npm run build"
   ```

3. **Start frontend development server:**
   ```bash
   cmd /c "npm run dev"
   ```
   Investigator Portal: `http://localhost:5173`

---

## 7. Implementation Roadmap — Completed Milestones

| Phase | Milestone | Status | Key Deliverables |
|---|---|---|---|
| **Phase 1** | **Foundation & Diagnostics** | ✅ **Complete** | FastAPI backend, React/TS UI, SQLite schema, `/api/health`, security headers middleware |
| **Phase 2** | **Case Management** | ✅ **Complete** | Case CRUD, auto-generated police case numbers (`CASE-2026-XXXX`), search & status filters |
| **Phase 3** | **Evidence Upload & Integrity** | ✅ **Complete** | Magic-bytes inspection, isolated storage, SHA-256 baseline hashing, on-demand integrity verification |
| **Phase 4** | **Image Forensics** | ✅ **Complete** | EXIF camera metadata, GPS extraction, software footprint detection, ELA heatmap generation |
| **Phase 5** | **Video / CCTV Forensics** | ✅ **Complete** | Video properties extraction, frame sampling, duplicate & frozen frame detection, side-by-side comparator |
| **Phase 6** | **Audio Forensics** | ✅ **Complete** | Waveform peak sampling, 0 dBFS clipping detection, silence drop detection, DAW footprint checks |
| **Phase 7** | **Cross-Evidence Consistency** | ✅ **Complete** | Multi-evidence timeline sequencing, device alignment, GPS proximity, timestamp divergence analysis |
| **Phase 8** | **Reports & Audit Log** | ✅ **Complete** | ReportLab structured forensic PDF generation, secure PDF downloads, filterable chain-of-custody audit log |
| **Phase 9** | **Security Review & Hardening** | ✅ **Complete** | Path-traversal tests, dangerous file rejection, security headers validation, 55 automated tests passing |

---

## 8. Limitations & Boundaries (spec.md §14 & §15)

1. **Local Prototype Architecture**: This project uses a local SQLite database and local filesystem storage appropriate for a hackathon prototype. Production deployment would require PostgreSQL, dedicated object storage (e.g., S3/MinIO), and hardened IAM access control.
2. **Explainability over Black-Box AI**: The system avoids uncalibrated "fake probability" percentages. Findings represent explainable anomalies (e.g. metadata tags, compression deltas, clipping counts).
3. **Legal Admissibility**: Generated PDF reports and audit tables are intended for investigative support and do not replace certified 65B affidavits or formal laboratory examinations.
