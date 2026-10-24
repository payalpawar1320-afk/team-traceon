# EvidenceGuard AI — Project Specification

## 1. Project Overview

**Project Name:** EvidenceGuard AI  
**Hackathon:** Cyber Hackathon Bihar Police 2026  
**Problem Statement:** PS-5 — Digital Evidence Authenticity and Integrity Verification Platform.

EvidenceGuard AI is a prototype forensic platform designed to help authorized investigators examine digital evidence, verify file integrity, identify potential signs of manipulation, compare information across evidence files, and generate structured forensic reports.

The platform will support image, video/CCTV, and audio evidence where technically feasible. It will preserve original evidence, record integrity information, display explainable findings, and maintain an audit trail of important actions.

**Important:** This is a hackathon prototype. It must not claim to be a certified forensic tool or production-ready police system.

## 2. Main Objectives

1. Create and manage investigation cases.
2. Upload and securely store digital evidence.
3. Preserve original uploaded files without modifying their bytes.
4. Calculate and verify SHA-256 hashes.
5. Extract available image metadata and identify suspicious inconsistencies.
6. Perform feasible image manipulation checks.
7. Inspect video/CCTV files for potential frame and timestamp anomalies.
8. Implement basic audio integrity checks where feasible.
9. Compare metadata and timestamps across related evidence files.
10. Display explainable, evidence-linked findings.
11. Generate downloadable PDF reports.
12. Maintain an audit log of important user actions.
13. Provide a professional, simple, investigator-friendly interface.

## 3. Technology Stack

Use the following stack unless the existing repository already has a suitable implementation.

### Frontend
- React.js
- TypeScript
- Vite
- CSS or the styling system already present in the project
- Recharts for appropriate charts, if needed

### Backend
- Python
- FastAPI
- Pydantic for request validation

### Database and File Storage
- SQLite for the local hackathon prototype
- SQLAlchemy or another appropriate database layer
- Local file storage outside publicly accessible frontend directories
- Keep the database layer modular so PostgreSQL can be introduced later

### Forensic and Utility Libraries
- `hashlib` for SHA-256
- Pillow for image processing
- ExifTool, if available and configured, for extended metadata extraction
- OpenCV for video and frame analysis
- FFmpeg/FFprobe for supported media inspection
- ReportLab for PDF reports
- Pytest for backend testing

Use additional libraries only when justified. Check existing dependencies before installing new ones.

## 4. Functional Requirements

### FR-01: Dashboard

Create a dashboard that provides a clear overview of:
- Total cases created.
- Total evidence files registered.
- Recent investigation activity.
- Findings requiring review.
- Recent reports.
- Quick actions for creating a case and adding evidence.

All displayed statistics must come from actual application data. Do not invent case counts, findings, accuracy scores, or other performance metrics.

### FR-02: Case Management

Users should be able to:
- Create a case with a unique case ID.
- Add a case title, description, and creation date.
- View a list of cases.
- Search and open a case.
- View evidence and analysis results associated with a case.
- View case activity and reports.

Validate all input on the backend. Do not expose one case's information to an unauthorized user.

### FR-03: Evidence Upload and Preservation

Support common evidence formats, subject to validated library support.

Initial formats may include:
- Images: JPG, JPEG, PNG.
- Videos: MP4, MOV, AVI, where supported.
- Audio: WAV, MP3, where supported.

Requirements:
- Validate file size, extension, MIME type, and file signature where practical.
- Reject unsupported or malformed files safely.
- Generate random internal storage filenames.
- Prevent path traversal and unsafe file paths.
- Store evidence outside public frontend directories.
- Associate each file with a case and unique evidence ID.
- Record original filename, detected file type, size, upload time, and SHA-256 hash.
- Preserve the original file bytes.
- Perform analysis on temporary copies or derived data rather than modifying the original.
- Handle failed uploads without leaving misleading database records or incomplete evidence.

Use configurable file-size limits and explain any unsupported format.

### FR-04: SHA-256 Integrity Verification

For every successfully registered evidence file:
1. Calculate its SHA-256 hash from the original bytes.
2. Store the hash and calculation time.
3. Display the hash on the evidence details page.
4. Allow the file to be checked again.
5. Compare the recalculated hash against the previously recorded hash.
6. Display whether the current bytes match the recorded reference.

Possible statuses:
- **Match:** The current file bytes match the recorded reference hash.
- **Mismatch:** The current file bytes differ from the recorded reference hash.
- **Not checked:** No comparison has been performed.
- **Check failed:** Verification could not be completed.

A matching hash does not prove that the file was authentic before its first registration. It proves byte equality with the selected reference.

### FR-05: Image Metadata and Manipulation Indicators

Extract available metadata, such as:
- File format and dimensions.
- EXIF camera make and model, when present.
- Capture date/time, when present.
- GPS coordinates, when present.
- Software or editing information, when present.
- File modification information where available.

Implement feasible checks for:
- Missing or inconsistent metadata.
- Conflicting timestamps.
- Potential editing-software traces.
- Error Level Analysis (ELA), where technically appropriate.
- Other simple, explainable image consistency checks if they can be validated.

Display the extracted properties and explain why a result may require review.

Limitations:
- Metadata can be missing, altered, or removed during normal processing.
- ELA and other image checks may produce false positives.
- A suspicious indicator alone does not establish that an image was manipulated.
- Do not claim to detect every type of image forgery.

### FR-06: Video and CCTV Analysis

For supported video files, implement feasible checks such as:
- Video duration, resolution, frame rate, and codec information.
- Frame extraction at selected intervals.
- Detection of exact duplicate frames within the inspected sample.
- Potentially irregular timestamps or frame sequences when reliable information is available.
- Comparison of selected frames for review.
- Identification of processing errors and unsupported media.

Show relevant timestamps and frame references for findings whenever possible.

Do not claim that duplicate frames automatically prove tampering. Repeated frames may occur naturally in CCTV footage or during encoding.

Distinguish:
- A detected indicator.
- No indicator detected by the implemented check.
- Not checked.
- Check unavailable.
- Analysis failed.

Do not attempt to reconstruct missing footage or claim reliable detection of inserted, deleted, or reordered frames unless the relevant method is implemented and tested.

### FR-07: Audio Analysis

Implement basic audio inspection only where feasible and testable.

Potential checks include:
- File format, duration, sample rate, and channel count.
- Available metadata.
- Basic waveform or signal inspection.
- Documented discontinuity or consistency checks, where justified.
- Audio/video timestamp comparison when usable information exists.

AI-generated voice or voice-tampering detection is optional and must not be represented as functional unless a suitable model is actually integrated and tested.

Do not identify a speaker or claim that a voice is fake based only on unsupported assumptions.

If reliable analysis is unavailable, display **Check unavailable** and explain the limitation.

### FR-08: Cross-Evidence Consistency

Provide a feature that compares selected evidence items within the same case.

Where information is available, compare:
- Capture timestamps.
- Time zones and timestamp precision, when known.
- Device metadata.
- File properties.
- Related video frame timestamps.
- Audio/video timing information.
- Other explicitly supported properties.

Show:
- The evidence IDs being compared.
- The fields compared.
- The observed values.
- Any inconsistency.
- A short explanation.
- Limitations and possible alternative explanations.

Do not assume that different timestamps prove manipulation. Account for missing metadata, clock differences, time-zone ambiguity, and normal file processing.

### FR-09: Analysis Results and Findings

Every analysis result should include:
- Case ID.
- Evidence ID.
- Analysis type.
- Date and time of analysis.
- Result status.
- Finding description.
- Relevant metadata, frame, or timestamp when available.
- Limitations or reason for an unavailable result.
- Analysis error information where appropriate.

Use clear status labels:
- Indicator detected.
- No indicator detected by this check.
- Not checked.
- Check unavailable.
- Analysis failed.

Do not use fake confidence percentages or uncalibrated fake-probability scores. Only display a confidence value if the method supports it, its meaning is documented, and it is properly validated.

### FR-10: PDF Forensic Reports

Generate a downloadable PDF report for a case or selected evidence.

Include:
- Project name and report generation date.
- Case ID and case details.
- Evidence IDs and available file details.
- Recorded SHA-256 hashes.
- Integrity verification results.
- Analysis methods actually executed.
- Findings and relevant evidence references.
- Important timestamps and metadata, where available.
- Limitations and unavailable checks.
- Audit history relevant to the report.

Reports must distinguish observed facts from possible interpretations.

Do not claim that the PDF is digitally signed, legally certified, or tamper-proof unless those capabilities are explicitly implemented and validated.

## 5. Application Pages

Create these pages or equivalent routes:

1. **Dashboard** — overview and recent activity.
2. **Create Case** — form to register an investigation.
3. **My Cases** — searchable case list.
4. **Case Details** — case information, evidence, findings, and reports.
5. **Evidence Upload** — validated file upload.
6. **Evidence Details** — file properties, hash, and analysis history.
7. **Analysis Results** — findings with explanations.
8. **Integrity Verification** — recorded versus recalculated hash.
9. **Cross-Evidence Check** — compare related evidence properties.
10. **Reports** — generate and access authorized reports.
11. **Audit Log** — important application events.
12. **Settings and Help** — supported formats, configuration, and limitations.

Ensure navigation works. Do not create decorative buttons that do nothing.

## 6. Security and Privacy Requirements

Security is a primary requirement because the concept concerns sensitive digital evidence.

### File Security
- Never place uploaded evidence in a publicly served directory.
- Do not expose unrestricted filesystem paths.
- Generate internal storage names instead of trusting user-supplied filenames.
- Validate all uploads on the server.
- Enforce configurable size limits.
- Prevent path traversal and unsafe file handling.
- Never execute uploaded files.
- Avoid loading untrusted media into unsafe processing workflows.
- Use timeouts and sensible resource limits for media analysis.
- Keep original evidence separate from derived files and analysis outputs.

### Access Control
- Protect all case, evidence, analysis, report, and audit endpoints.
- Perform authorization checks on the server for every protected operation.
- If authentication is implemented, use a standard secure password-hashing approach.
- Do not store plaintext passwords.
- Do not hardcode credentials or secret keys.
- Restrict CORS to the intended frontend origins.
- Do not rely only on frontend route protection.

If full authentication and authorization are not implemented, clearly document this limitation and keep the prototype local or otherwise restricted. Do not claim multi-user security without testing it.

### Privacy
- Use synthetic or non-sensitive sample evidence during development.
- Do not upload sensitive evidence to public AI APIs or external services.
- Do not add external analytics or tracking.
- Avoid logging file contents, passwords, tokens, GPS coordinates, or other sensitive details unnecessarily.
- Do not expose evidence or reports through public URLs.
- Store secrets in environment variables and exclude local environment files from version control.

### Integrity and Audit
Record relevant actions such as:
- Case creation.
- Evidence registration.
- Hash calculation.
- Integrity verification.
- Analysis start and completion.
- Report generation.
- Report access or download, where implemented.
- Evidence deletion, where permitted.

Include timestamps, relevant record IDs, and the action result. Restrict audit-log access appropriately.

Do not call a normal editable database audit table an immutable or tamper-proof ledger. Document the actual protection implemented.

### Encryption
Implement encryption only if it can be done correctly within the project scope. Never claim encryption at rest or end-to-end encryption unless it is implemented, configured, and verified.

## 7. Database Design

Use a modular data model. Suggested entities:

### Cases
- `id`
- `case_number`
- `title`
- `description`
- `created_at`
- `updated_at`
- `status`

### Evidence
- `id`
- `case_id`
- `original_filename`
- `storage_filename`
- `storage_path` (internal only; never expose publicly)
- `detected_file_type`
- `file_size`
- `sha256_hash`
- `uploaded_at`
- `metadata_json` or an equivalent structured representation

### Analysis Results
- `id`
- `case_id`
- `evidence_id`
- `analysis_type`
- `status`
- `findings_json` or structured findings
- `limitations`
- `error_summary`, when appropriate
- `created_at`

### Integrity Checks
- `id`
- `evidence_id`
- `recorded_hash`
- `recalculated_hash`
- `result`
- `checked_at`

### Audit Events
- `id`
- `case_id`, when applicable
- `evidence_id`, when applicable
- `actor_id`, when authentication exists
- `action`
- `result`
- `created_at`
- Minimal non-sensitive details

### Reports
- `id`
- `case_id`
- `report_path` (internal only)
- `generated_at`
- `report_status`

Use proper foreign keys, validation, transactions where appropriate, and database migrations or an equivalent controlled schema-update process.

Do not store the same information redundantly without a clear reason.

## 8. Backend API Expectations

Use a clear REST API structure. Suggested endpoints:

- `GET /api/health`
- `GET /api/cases`
- `POST /api/cases`
- `GET /api/cases/{case_id}`
- `POST /api/cases/{case_id}/evidence`
- `GET /api/evidence/{evidence_id}`
- `POST /api/evidence/{evidence_id}/verify-integrity`
- `POST /api/evidence/{evidence_id}/analyze`
- `POST /api/cases/{case_id}/compare-evidence`
- `GET /api/cases/{case_id}/analysis-results`
- `POST /api/cases/{case_id}/reports`
- `GET /api/cases/{case_id}/reports`
- `GET /api/audit-log`

These are proposed routes, not a requirement to duplicate an existing working API. Adapt them to the repository while maintaining consistent validation, authorization, error responses, and documentation.

Use FastAPI's API documentation during development. Do not expose unrestricted file access through generic path parameters.

## 9. Frontend Design Requirements

Create a professional, practical forensic dashboard suitable for a police-investigation workflow.

### Visual Style
- White or very light grey background.
- Dark navy sidebar and header.
- Muted blue as a restrained accent.
- Clear tables and readable status labels.
- Simple, consistent icons.
- Standard sans-serif typography.
- Good spacing and alignment.
- Responsive layout for common laptop and desktop screens.

### Avoid
- Neon colours.
- Glowing effects.
- Excessive gradients.
- Glassmorphism.
- Decorative AI illustrations.
- Animated backgrounds.
- Oversized cards with little useful information.
- Fake statistics or unsupported accuracy claims.
- Decorative controls that do not work.

### Usability
- Use meaningful labels.
- Provide loading, empty, success, and error states.
- Show validation messages close to relevant inputs.
- Confirm destructive actions.
- Make hash values easy to copy.
- Make evidence IDs and analysis statuses easy to identify.
- Show clear explanations and limitations alongside findings.
- Ensure the interface does not treat an anomaly as conclusive proof of tampering.

## 10. Error Handling and Reliability

- Validate inputs on both frontend and backend.
- Return useful HTTP error codes and messages.
- Handle unsupported file formats gracefully.
- Handle corrupted or unreadable media.
- Use timeouts and resource limits for expensive operations.
- Prevent duplicate or partial records after failed uploads.
- Do not silently ignore failed analysis.
- Store an appropriate failure status.
- Avoid returning stack traces or sensitive filesystem details to users.
- Keep application logs useful without including sensitive evidence data.

## 11. Testing Requirements

Create tests for the most important operations.

### Case Management
- Valid case creation.
- Invalid input rejection.
- Case retrieval and not-found handling.

### Evidence Upload
- Supported file upload.
- Unsupported file rejection.
- Oversized file rejection.
- Invalid or malformed file handling.
- Safe storage naming.
- Preservation of original bytes.

### Integrity
- Repeat hash calculation returns the same result for unchanged bytes.
- A modified copy produces a different hash.
- Integrity comparison returns the correct status.

### Analysis
- Valid image metadata extraction.
- Missing metadata handling.
- Unsupported or corrupted image handling.
- Video analysis for supported sample files.
- Clear unavailable status for unimplemented checks.
- Correct handling of analysis failures.

### Reports and Audit
- PDF generation.
- Correct case and evidence references in reports.
- Audit entries for important successful and failed actions.
- Authorization tests for protected resources if authentication exists.

Use synthetic test evidence. Do not report tests as passing unless they have actually been executed.

## 12. Repository and Configuration Rules

Before changing the project:
1. Inspect the existing repository structure.
2. Read this entire `SPEC.md`.
3. Identify the current frontend, backend, database, and working features.
4. Identify missing features and technical risks.
5. Reuse working code wherever appropriate.

Maintain a useful `.gitignore`. Exclude, where applicable:
- `.env` and secret files.
- Virtual environments.
- `node_modules`.
- Python cache files.
- Local evidence storage.
- Generated sensitive reports.
- Local database files containing evidence records.
- Application logs.
- Temporary media and analysis files.
- Build outputs where appropriate.

Provide an `.env.example` containing placeholders only, not real secrets.

Add a README with installation steps, development commands, configuration instructions, supported formats, tests, limitations, and known incomplete features.

## 13. Implementation Order

Build incrementally in the following order:

### Phase 1 — Repository Inspection and Application Foundation
- Inspect existing code.
- Confirm the frontend/backend structure.
- Configure the local development environment.
- Establish consistent layout and navigation.
- Add health checks and basic tests.
- Do not rewrite working components without a reason.

### Phase 2 — Case Management
- Implement case creation, listing, and detail views.
- Add database models and validation.
- Test case operations.

### Phase 3 — Secure Evidence Upload and Integrity
- Implement server-side upload validation.
- Preserve original bytes.
- Store evidence outside public directories.
- Calculate SHA-256 hashes.
- Implement integrity verification and tests.

### Phase 4 — Image Analysis
- Extract image metadata.
- Implement selected, explainable image checks.
- Display findings and limitations.

### Phase 5 — Video and CCTV Analysis
- Extract supported video properties.
- Implement feasible frame and timestamp checks.
- Display timestamps and sample-frame references.

### Phase 6 — Audio Analysis
- Implement basic inspection if feasible.
- Clearly identify unavailable or experimental checks.

### Phase 7 — Cross-Evidence Consistency
- Compare supported metadata and timestamps.
- Present inconsistencies with explanations and evidence references.

### Phase 8 — Findings, Audit, and Reports
- Integrate analysis results.
- Record audit events.
- Generate PDF reports.
- Test report accuracy and access restrictions.

### Phase 9 — Security Review and Documentation
- Test upload validation and access restrictions.
- Review CORS and secret handling.
- Verify that sensitive files are not publicly served.
- Run automated tests.
- Document limitations and remaining risks.

## 14. Demo and Deployment Boundaries

The first target is a reliable local hackathon prototype using synthetic evidence.

Do not deploy sensitive real evidence to public hosting during development.

If a public demo is needed:
- Use synthetic cases and files only.
- Do not expose unrestricted upload or report endpoints.
- Do not expose the local database or filesystem.
- Configure secrets outside source control.
- Review authentication, authorization, upload limits, CORS, and storage before deployment.
- Clearly label the demo as a prototype.

A local SQLite database and local file storage are acceptable for the initial prototype. Do not claim they are a complete production deployment architecture.

## 15. Final Development Principles

1. Accuracy and explainability are more important than the number of features.
2. Preserve originals and clearly distinguish them from derived analysis files.
3. Every finding should reference the evidence and check that produced it.
4. An indicator is not proof of tampering.
5. A matching hash does not establish original authenticity.
6. Never invent metrics, test results, detection capabilities, or security claims.
7. Mark incomplete or unsupported features honestly.
8. Prioritize privacy and controlled access.
9. Keep the UI professional, clear, and practical.
10. Build and test one phase at a time.

**Final instruction:** The purpose of EvidenceGuard AI is to help investigators inspect digital evidence systematically and understand potential integrity issues. It must support human review rather than automatically declare evidence genuine or fake.
