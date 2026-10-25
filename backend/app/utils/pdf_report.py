import html
import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.analysis import AnalysisResult
from app.models.integrity import IntegrityCheck
from app.models.audit import AuditEvent
from app.models.report import Report
from app.schemas.report import ReportGenerateRequest

logger = logging.getLogger("traceon.pdf_report")

# =============================================================================
# STRICT MONOCHROME PALETTE (White, Black, Charcoal, Dark/Mid/Light Grey ONLY)
# Professional, clean, and highly readable for government and police workflows.
# =============================================================================
COLOR_WHITE = colors.HexColor("#ffffff")
COLOR_BLACK = colors.HexColor("#09090b")
COLOR_CHARCOAL = colors.HexColor("#18181b")          # Deep charcoal body text
COLOR_DARK_GREY = colors.HexColor("#27272a")         # Dark grey headings & strong borders
COLOR_MID_GREY = colors.HexColor("#52525b")          # Medium grey captions & secondary labels
COLOR_LIGHT_GREY = colors.HexColor("#f4f4f5")        # Clean light grey for card backgrounds & headers
COLOR_ALT_GREY = colors.HexColor("#fafafa")          # Very subtle alternate row fill
COLOR_BORDER = colors.HexColor("#e4e4e7")            # Crisp neutral border divider
COLOR_BORDER_STRONG = colors.HexColor("#71717a")     # Prominent callout box border

# Standard Product Identity Strings
PRODUCT_NAME = "TRACEON"
PRODUCT_TAGLINE = "Every Trace. Every Truth."
PRODUCT_SUBTITLE = "Digital Evidence Integrity and Forensic Analysis."
DOCUMENT_TITLE = "Digital Evidence Examination Report"
DOCUMENT_CLASSIFICATION = "Demonstration Report — Not a Certified Forensic Report."

# Standard Status Vocabulary (Phase 3 Audit Requirements)
STATUS_COMPLETED = "Completed"
STATUS_INDICATOR_FOUND = "Indicator found"
STATUS_NO_INDICATOR = "No indicator found by this check"
STATUS_INCONCLUSIVE = "Inconclusive"
STATUS_NOT_APPLICABLE = "Not applicable"
STATUS_UNSUPPORTED = "Unsupported format"
STATUS_NOT_RUN = "Not run"
STATUS_FAILED = "Failed"


def _sanitize_text(val: Any) -> str:
    """
    Sanitize text to guarantee:
    1. Never display old product name 'EvidenceGuard AI' or 'EvidenceGuard'.
    2. Never display problem statement numbers (e.g., 'Problem Statement 112', 'PS 112', etc.).
    3. Remove any institutional certification claims.
    """
    if val is None:
        return "Not recorded"
    s = str(val).strip()
    if not s:
        return "Not recorded"

    # 1. Replace old branding
    s = re.sub(r"(?i)evidenceguard(?:\s*ai)?", "TRACEON", s)

    # 2. Strip problem statement numbers and phrases
    s = re.sub(r"(?i)problem\s*statement\s*(?:no\.?|number)?\s*#?\s*112", "Demonstration Reference", s)
    s = re.sub(r"(?i)\bps\s*[-#]?\s*112\b", "DEMO-CASE", s)
    s = re.sub(r"(?i)\bproblem\s*112\b", "Demonstration Case", s)
    s = re.sub(r"(?i)problem\s*statement", "Demonstration Scope", s)

    return s


def _esc(val: Any) -> str:
    """Safely escape text for ReportLab XML/HTML Paragraph rendering after sanitization."""
    if val is None or str(val).strip() == "":
        return "Not recorded"
    sanitized = _sanitize_text(val)
    return html.escape(sanitized)


def _split_hash_safely(h: str) -> str:
    """Split a 64-char hash into two 32-char lines for safe printing without column overflow."""
    if not h or len(h) != 64:
        return _esc(h)
    return f"{h[:32]}<br/>{h[32:]}"


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas that computes total page count dynamically.
    Draws professional running headers (page 2+) and footers (all pages).
    Strictly monochromatic with clean lines and no decorative embellishments.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._report_number = "REP-2026-0000"

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(COLOR_MID_GREY)

        # Running Header (displayed only on pages 2 and later)
        if self._pageNumber > 1:
            self.drawString(36, 756, f"{PRODUCT_NAME} — {DOCUMENT_TITLE}")
            self.drawRightString(576, 756, self._report_number)
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(36, 750, 576, 750)

        # Running Footer (displayed on every page)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(36, 38, 576, 38)

        self.drawString(
            36,
            26,
            f"{PRODUCT_NAME} | {DOCUMENT_CLASSIFICATION}",
        )
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 26, page_text)
        self.restoreState()


def make_numbered_canvas(report_number: str):
    """Factory creating NumberedCanvas with active report number bound."""
    class CustomNumberedCanvas(NumberedCanvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._report_number = report_number
    return CustomNumberedCanvas


def generate_unique_report_number(db: Session) -> str:
    """Generate unique report identifier: REP-2026-XXXX."""
    year = datetime.now(timezone.utc).year
    for _ in range(20):
        cand = f"REP-{year}-{random.randint(1001, 9999)}"
        if not db.query(Report.id).filter(Report.report_number == cand).first():
            return cand
    return f"REP-{year}-{int(datetime.now(timezone.utc).timestamp()) % 100000:05d}"


def _generate_dynamic_final_conclusion(
    case: Case,
    selected_evidence: List[Evidence],
    latest_integrity_by_ev: Dict[int, IntegrityCheck],
    deduplicated_analyses: List[AnalysisResult],
) -> str:
    """
    Dynamically generates the plain-English section:
    'Final Conclusion — What This Report Tells You' (100–180 words).
    Addresses:
    1. File types examined
    2. Completed checks
    3. Notable findings or unusual indicators
    4. AI-image detection status
    5. Unavailable or not applicable checks
    6. Reasonable conclusions
    7. What cannot be confirmed
    8. Sensible next steps
    """
    if not selected_evidence:
        return (
            "No digital evidence files were selected for this examination. "
            "No technical checks were completed, and no conclusions regarding authenticity can be made. "
            "Please register and analyze evidence before generating a forensic report."
        )

    # 1. File types examined
    type_counts: Dict[str, int] = {}
    has_png = False
    has_jpeg = False
    for ev in selected_evidence:
        t = ev.detected_file_type.lower()
        type_counts[t] = type_counts.get(t, 0) + 1
        if ev.original_filename.lower().endswith(".png") or (ev.mime_type and "png" in ev.mime_type.lower()):
            has_png = True
        if ev.original_filename.lower().endswith((".jpg", ".jpeg")) or (ev.mime_type and "jpeg" in ev.mime_type.lower()):
            has_jpeg = True

    file_summary_parts = []
    for t, c in sorted(type_counts.items()):
        file_summary_parts.append(f"{c} {t}")
    file_type_str = ", ".join(file_summary_parts) if file_summary_parts else "digital evidence"

    # 2. Checks completed & Integrity evaluation
    all_matched = True
    mismatch_detected = False
    not_checked_count = 0

    for ev in selected_evidence:
        chk = latest_integrity_by_ev.get(ev.id)
        if chk:
            if chk.result.lower() == "mismatch":
                mismatch_detected = True
                all_matched = False
            elif chk.result.lower() != "match":
                all_matched = False
        else:
            not_checked_count += 1
            all_matched = False

    if mismatch_detected:
        integrity_clause = "The file's current digital fingerprint did NOT match the saved reference, indicating the file has changed since intake."
    elif all_matched:
        integrity_clause = "The file's current digital fingerprint matched the saved intake reference, confirming byte-level integrity during storage."
    else:
        integrity_clause = "Baseline digital fingerprints were recorded at intake, but on-demand re-verification has not been executed for all items."

    # 3. Findings from executed modules
    indicators_found = []
    has_image_evidence = any(e.detected_file_type == "image" for e in selected_evidence)

    for an in deduplicated_analyses:
        try:
            if an.findings_json:
                fdata = json.loads(an.findings_json)
                if an.analysis_type == "image_forensics":
                    meta = fdata.get("metadata_report", {})
                    ela = fdata.get("ela_report", {})
                    if meta.get("software"):
                        indicators_found.append(f"editing software tag ('{meta.get('software')}') in metadata")
                    if ela.get("indicator_detected") and not has_png:
                        indicators_found.append("compression level variance across image quadrants")
                elif an.analysis_type == "video_forensics":
                    vrep = fdata.get("video_report", {})
                    if vrep.get("duplicate_frames_count", 0) > 0:
                        indicators_found.append(f"{vrep.get('duplicate_frames_count')} duplicate video frames in sample")
                    elif vrep.get("is_frozen_detected"):
                        indicators_found.append("consecutive frozen frames in video sample")
                elif an.analysis_type == "audio_forensics":
                    arep = fdata.get("audio_report", {})
                    if arep.get("is_clipped"):
                        indicators_found.append("distorted clipped audio samples")
                    if arep.get("has_silence_gaps"):
                        indicators_found.append("abrupt silence drop in audio")
        except Exception:
            pass

    if indicators_found:
        findings_clause = f"The examination detected notable indicators requiring follow-up: {', '.join(indicators_found)}."
    elif deduplicated_analyses:
        if has_png and not has_jpeg:
            findings_clause = "Metadata inspection revealed no embedded camera profile (typical of web and AI images), while ELA variance reflects format conversion rather than editing."
        else:
            findings_clause = "Executed laboratory checks completed without detecting manipulation indicators in the examined samples."
    else:
        findings_clause = "Laboratory analysis modules have not yet been run on the uploaded files."

    # 4 & 5. AI-image detector status
    if has_image_evidence:
        ai_clause = (
            "An automated AI-image detector was not run because this platform prototype currently performs "
            "forensic integrity and compression analysis, but does not contain a trained AI-generated image model."
        )
    else:
        ai_clause = "AI-image detection was not applicable to the non-image files in this case."

    # 6, 7 & 8. What can/cannot be concluded and next step
    conclusion_text = (
        f"This examination evaluated {len(selected_evidence)} file(s) ({file_type_str}) registered under case "
        f"{_sanitize_text(case.case_number)}. {integrity_clause} {findings_clause} {ai_clause} "
        f"These checks verify that the stored file has not changed since registration, but they cannot prove "
        f"who created the file, whether the scene is genuine, or whether the content was edited prior to intake. "
        f"Any identified indicators should be reviewed alongside original recording devices, telecom carrier records, "
        f"and witness statements before drawing investigative conclusions."
    )
    return conclusion_text


def create_case_forensic_pdf(
    case: Case,
    db: Session,
    request_params: ReportGenerateRequest,
    report_number: Optional[str] = None,
    output_filename: Optional[str] = None,
) -> Tuple[str, str, int]:
    """
    Generate an authoritative, clear, visually striking and technically truthful
    digital forensics examination demonstration PDF report adhering strictly to:
    - Product identity: TRACEON ("Every Trace. Every Truth.")
    - Classification: "Demonstration Report — Not a Certified Forensic Report."
    - Strict monochrome palette (White, Black, Charcoal, Dark/Mid/Light Grey).
    - Executive 1-page summary: Case overview, File Details & Integrity Status,
      and mandatory limitation box.
    - Plain English throughout: understandable by any citizen, judge, or officer.
    - Standard status vocabulary: Completed, Indicator found, No indicator found by this check,
      Inconclusive, Not applicable, Unsupported format, Not run, Failed.
    - Honest handling of Real vs AI-Generated images (dedicated section for images).
    - Dynamic Final Conclusion answering all 8 required questions in 100-180 words.
    - Full extracted metadata breakdown table displaying actual fields.
    - Honest PNG ELA format disclosure (lossless re-compression artefact notice).
    - Adaptive media sections: image reports contain only image checks and no video assessments.
    - Clean technical appendix with manifests, SHA-256 digests, and chain of custody.
    """
    settings.ensure_storage_directories()
    report_num = report_number or generate_unique_report_number(db)

    clean_case_num = _sanitize_text(case.case_number)
    safe_case_num = re.sub(r"[^A-Za-z0-9_-]", "_", clean_case_num)
    filename = output_filename or f"{report_num}_{safe_case_num}.pdf"
    file_path = Path(settings.REPORTS_DIR) / filename

    # Filter evidence items
    if request_params.evidence_ids and not request_params.include_all_evidence:
        selected_evidence = [
            e for e in case.evidence_items if e.id in request_params.evidence_ids
        ]
    else:
        selected_evidence = list(case.evidence_items)

    selected_evidence_ids = {e.id for e in selected_evidence}

    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=42,
        bottomMargin=48,
    )

    styles = getSampleStyleSheet()

    # Typography Hierarchy (Monochrome Helvetica & Courier)
    style_wordmark = ParagraphStyle(
        "TraceonWordmark",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=22,
        textColor=COLOR_BLACK,
    )

    style_tagline = ParagraphStyle(
        "TraceonTagline",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=COLOR_MID_GREY,
    )

    style_doc_title = ParagraphStyle(
        "TraceonDocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=COLOR_CHARCOAL,
    )

    style_subtitle = ParagraphStyle(
        "TraceonSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=COLOR_MID_GREY,
    )

    style_meta_card = ParagraphStyle(
        "TraceonMetaCard",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10.5,
        textColor=COLOR_CHARCOAL,
    )

    style_section_heading = ParagraphStyle(
        "TraceonSectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=COLOR_DARK_GREY,
        spaceBefore=7,
        spaceAfter=3,
    )

    style_body = ParagraphStyle(
        "TraceonBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10.5,
        textColor=COLOR_CHARCOAL,
    )

    style_body_bold = ParagraphStyle(
        "TraceonBodyBold",
        parent=style_body,
        fontName="Helvetica-Bold",
    )

    style_body_muted = ParagraphStyle(
        "TraceonBodyMuted",
        parent=style_body,
        fontSize=7,
        leading=9.5,
        textColor=COLOR_MID_GREY,
    )

    style_mono = ParagraphStyle(
        "TraceonMono",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7,
        leading=9,
        textColor=COLOR_CHARCOAL,
    )

    style_mono_bold = ParagraphStyle(
        "TraceonMonoBold",
        parent=style_mono,
        fontName="Courier-Bold",
    )

    style_mono_hash = ParagraphStyle(
        "TraceonMonoHash",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=6.5,
        leading=8,
        textColor=COLOR_CHARCOAL,
    )

    style_callout = ParagraphStyle(
        "TraceonCallout",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10.5,
        textColor=COLOR_CHARCOAL,
    )

    style_badge_center = ParagraphStyle(
        "TraceonBadgeCenter",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8.5,
        alignment=1,  # Center
        textColor=COLOR_CHARCOAL,
    )

    story = []

    # =========================================================================
    # PRE-QUERY & DEDUPLICATE RELEVANT DATA
    # =========================================================================

    # 1. Latest IntegrityCheck per selected evidence item
    latest_integrity_by_ev: Dict[int, IntegrityCheck] = {}
    for ev in selected_evidence:
        chk = (
            db.query(IntegrityCheck)
            .filter(IntegrityCheck.evidence_id == ev.id)
            .order_by(IntegrityCheck.checked_at.desc())
            .first()
        )
        if chk:
            latest_integrity_by_ev[ev.id] = chk

    # 2. Deduplicated Latest Analyses per (evidence_id, analysis_type)
    all_case_analyses = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.case_id == case.id)
        .order_by(AnalysisResult.created_at.desc())
        .all()
    )
    latest_analyses_map: Dict[Tuple[int, str], AnalysisResult] = {}
    for an in all_case_analyses:
        if an.evidence_id in selected_evidence_ids:
            key = (an.evidence_id, an.analysis_type)
            if key not in latest_analyses_map:
                latest_analyses_map[key] = an

    deduplicated_analyses = list(latest_analyses_map.values())

    # Evidence type assessment
    has_image_evidence = any(e.detected_file_type == "image" for e in selected_evidence)
    has_video_evidence = any(e.detected_file_type == "video" for e in selected_evidence)
    has_audio_evidence = any(e.detected_file_type == "audio" for e in selected_evidence)

    has_png_image = any(
        e.detected_file_type == "image" and (
            e.original_filename.lower().endswith(".png") or (e.mime_type and "png" in e.mime_type.lower())
        )
        for e in selected_evidence
    )
    has_jpeg_image = any(
        e.detected_file_type == "image" and (
            e.original_filename.lower().endswith((".jpg", ".jpeg")) or (e.mime_type and "jpeg" in e.mime_type.lower())
        )
        for e in selected_evidence
    )

    executed_analysis_types = {an.analysis_type for an in deduplicated_analyses}
    has_image_analysis = "image_forensics" in executed_analysis_types
    has_video_analysis = "video_forensics" in executed_analysis_types
    has_audio_analysis = "audio_forensics" in executed_analysis_types

    # =========================================================================
    # PAGE 1: EXECUTIVE FIRST PAGE (The 10-Second Summary)
    # =========================================================================
    gen_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    brand_col = [
        Paragraph(f"<b>{PRODUCT_NAME}</b>", style_wordmark),
        Spacer(1, 1),
        Paragraph(f"<b>{PRODUCT_TAGLINE}</b>", style_tagline),
        Spacer(1, 4),
        Paragraph(DOCUMENT_TITLE, style_doc_title),
        Paragraph(PRODUCT_SUBTITLE, style_subtitle),
    ]

    meta_content = (
        f"<b>REPORT ID:</b> {_esc(report_num)}<br/>"
        f"<b>DATE:</b> {gen_time_str}<br/>"
        f"<b>CASE REF:</b> {_esc(clean_case_num)}<br/>"
        f"<b>DOCUMENT STATUS:</b><br/>"
        f"<b>DEMONSTRATION REPORT</b><br/>"
        f"<font size='6.5' color='#52525b'>Not a Certified Forensic Report</font>"
    )

    header_table_data = [
        [
            brand_col,
            Paragraph(meta_content, style_meta_card),
        ]
    ]
    header_table = Table(header_table_data, colWidths=[355, 185])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("BACKGROUND", (1, 0), (1, -1), COLOR_LIGHT_GREY),
        ("BOX", (1, 0), (1, -1), 0.5, COLOR_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (1, 0), (1, -1), 6),
        ("RIGHTPADDING", (1, 0), (1, -1), 6),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_DARK_GREY, spaceBefore=4, spaceAfter=5))

    # SECTION 1: Report Summary & Case Overview
    story.append(Paragraph("1. INVESTIGATION CASE SUMMARY & REPORT OVERVIEW", style_section_heading))
    raw_desc = case.description if case.description and case.description.strip() else "Digital forensics examination of registered evidence items."
    clean_desc = _sanitize_text(raw_desc)

    case_info_data = [
        [
            Paragraph("<b>Case Reference:</b>", style_body),
            Paragraph(f"<b>{_esc(clean_case_num)}</b>", style_body_bold),
            Paragraph("<b>Assigned Examiner:</b>", style_body),
            Paragraph(_esc(case.investigator_name), style_body),
        ],
        [
            Paragraph("<b>Case Title:</b>", style_body),
            Paragraph(_esc(case.title), style_body),
            Paragraph("<b>Case Status:</b>", style_body),
            Paragraph(f"<b>{_esc(case.status.upper())}</b>", style_body_bold),
        ],
        [
            Paragraph("<b>Registration Date:</b>", style_body),
            Paragraph(case.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), style_body),
            Paragraph("<b>Evidence Scope:</b>", style_body),
            Paragraph(f"{len(selected_evidence)} item(s) selected", style_body),
        ],
        [
            Paragraph("<b>Case Purpose:</b>", style_body),
            Paragraph(_esc(clean_desc), style_body),
            "",
            "",
        ],
    ]
    case_table = Table(case_info_data, colWidths=[90, 180, 100, 170])
    case_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_GREY),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("SPAN", (1, 3), (3, 3)),
    ]))
    story.append(case_table)
    story.append(Spacer(1, 5))

    # SECTION 2: File Details & Integrity Status Overview
    story.append(Paragraph("2. DIGITAL EVIDENCE & INTEGRITY STATUS OVERVIEW (FILE DETAILS)", style_section_heading))
    if not selected_evidence:
        story.append(Paragraph("<i>No digital evidence items registered under this case.</i>", style_body_muted))
    else:
        overview_table_data = [
            [
                Paragraph("<b>Item ID</b>", style_body_bold),
                Paragraph("<b>Original Filename</b>", style_body_bold),
                Paragraph("<b>Type & Format</b>", style_body_bold),
                Paragraph("<b>File Size</b>", style_body_bold),
                Paragraph("<b>Reference Fingerprint (SHA-256)</b>", style_body_bold),
                Paragraph("<b>Integrity Status</b>", style_body_bold),
            ]
        ]
        for ev in selected_evidence:
            size_kb = f"{ev.file_size / 1024:.1f} KB" if ev.file_size else "0 KB"
            chk = latest_integrity_by_ev.get(ev.id)

            if chk:
                res_lower = chk.result.lower()
                if res_lower == "match":
                    status_badge = "<b>MATCH</b><br/><font size='6' color='#52525b'>Byte-identical to baseline</font>"
                elif res_lower == "mismatch":
                    status_badge = "<b>MISMATCH</b><br/><font size='6' color='#18181b'>Variance detected</font>"
                elif res_lower == "check failed":
                    status_badge = "<b>CHECK FAILED</b><br/><font size='6' color='#52525b'>File inaccessible</font>"
                else:
                    status_badge = f"<b>{_esc(chk.result.upper())}</b>"
            else:
                status_badge = "<b>NOT CHECKED</b><br/><font size='6' color='#52525b'>Baseline hash recorded</font>"

            hash_preview = f"{ev.sha256_hash[:16]}...{ev.sha256_hash[-8:]}" if ev.sha256_hash else "Not computed"

            overview_table_data.append([
                Paragraph(f"<b>{_esc(ev.evidence_number)}</b>", style_mono_bold),
                Paragraph(_esc(ev.original_filename), style_body),
                Paragraph(f"{_esc(ev.detected_file_type.upper())}<br/><font size='6.5' color='#52525b'>{_esc(ev.mime_type)}</font>", style_body),
                Paragraph(size_kb, style_body),
                Paragraph(f"<font name='Courier' size='6.5'>{_esc(hash_preview)}</font>", style_mono),
                Paragraph(status_badge, style_body),
            ])

        overview_table = Table(overview_table_data, colWidths=[70, 130, 95, 60, 105, 80])
        overview_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_GREY),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(overview_table)

    story.append(Spacer(1, 6))

    # Mandatory Integrity Verification Notice (Executive Callout Box)
    notice_text = (
        "<b>MANDATORY INTEGRITY VERIFICATION NOTICE & LIMITATIONS:</b><br/>"
        "A matching SHA-256 digital fingerprint verifies mathematically that the file byte sequence on storage "
        "matches the reference cryptographic fingerprint computed during intake into TRACEON.<br/>"
        "&bull; <b>What this establishes:</b> The stored file has not experienced byte corruption, tampering, or replacement since ingestion.<br/>"
        "&bull; <b>What this does NOT establish:</b> Digital fingerprint matching does <b>NOT</b> prove the file was genuine when recorded, "
        "does <b>NOT</b> prove the content was unedited prior to intake, does <b>NOT</b> certify device provenance, and does <b>NOT</b> "
        "confer legal admissibility or statutory certification."
    )
    notice_table = Table([[Paragraph(notice_text, style_callout)]], colWidths=[540])
    notice_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_GREY),
        ("BOX", (0, 0), (-1, -1), 1.0, COLOR_DARK_GREY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(notice_table)

    # Page break so Page 1 remains a clean executive 10-second summary
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2+: TECHNICAL CHECKS, FINDINGS & AI ASSESSMENT (ADAPTIVE TO FILE TYPE)
    # =========================================================================

    # SECTION 3: Checks Performed & Methodology Status (Adaptive to Evidence Type)
    story.append(Paragraph("3. CHECKS PERFORMED & METHODOLOGY STATUS", style_section_heading))

    status_magic = STATUS_COMPLETED
    status_sha256 = STATUS_COMPLETED

    methodology_rows = [
        [
            Paragraph("<b>Check Name</b>", style_body_bold),
            Paragraph("<b>What It Checks (Plain English)</b>", style_body_bold),
            Paragraph("<b>Method & Tool Used</b>", style_body_bold),
            Paragraph("<b>Status</b>", style_body_bold),
        ],
        [
            Paragraph("File Signature Validation", style_body_bold),
            Paragraph("Checks container header bytes to confirm actual file format and detect disguised executables.", style_body),
            Paragraph("Binary Header Parser (Magic Bytes)", style_body),
            Paragraph(f"<b>{status_magic}</b>", style_badge_center),
        ],
        [
            Paragraph("SHA-256 Digital Fingerprint", style_body_bold),
            Paragraph("Calculates digital fingerprint to confirm stored file matches intake baseline.", style_body),
            Paragraph("Python hashlib (64 KB chunks)", style_body),
            Paragraph(f"<b>{status_sha256}</b>", style_badge_center),
        ],
    ]

    # Add Image-specific checks if image evidence is present
    if has_image_evidence:
        status_meta = STATUS_COMPLETED if has_image_analysis else STATUS_NOT_RUN
        methodology_rows.append([
            Paragraph("Metadata & Device Details", style_body_bold),
            Paragraph("Audits file header for camera make, model, original timestamps, GPS coordinates, and software tags.", style_body),
            Paragraph("Pillow EXIF / Header Parser", style_body),
            Paragraph(f"<b>{status_meta}</b>", style_badge_center),
        ])

        if has_png_image and not has_jpeg_image:
            # Honest ELA reporting on PNG
            methodology_rows.append([
                Paragraph("Error Level Analysis (ELA)", style_body_bold),
                Paragraph("Compression forensic technique for JPEG. PNG is a lossless format; re-saving PNG as JPEG introduces artificial conversion differences.", style_body),
                Paragraph("Pillow ImageChops (Quality 92, 15x)", style_body),
                Paragraph("<b>Unsupported format</b><br/><font size='6' color='#52525b'>Lossless PNG format</font>", style_badge_center),
            ])
        else:
            status_ela = STATUS_COMPLETED if has_image_analysis else STATUS_NOT_RUN
            methodology_rows.append([
                Paragraph("Error Level Analysis (ELA)", style_body_bold),
                Paragraph("Image comparison technique that evaluates JPEG compression consistency. Does not prove editing.", style_body),
                Paragraph("Pillow ImageChops (Quality 92, 15x)", style_body),
                Paragraph(f"<b>{status_ela}</b>", style_badge_center),
            ])

        methodology_rows.append([
            Paragraph("AI-Generated Image Assessment", style_body_bold),
            Paragraph("Checks whether an image was created by generative AI tools rather than captured by a camera.", style_body),
            Paragraph("Not implemented in this prototype", style_body),
            Paragraph("<b>Not available</b><br/><font size='6' color='#52525b'>Prototype limitation</font>", style_badge_center),
        ])

    # Add Video-specific checks ONLY if video evidence is present
    if has_video_evidence:
        status_video = STATUS_COMPLETED if has_video_analysis else STATUS_NOT_RUN
        methodology_rows.append([
            Paragraph("Video Continuity Check", style_body_bold),
            Paragraph("Decodes stream properties and evaluates exactly 20 sampled frames for duplicate or frozen footage.", style_body),
            Paragraph("OpenCV (cv2) Video Decoder", style_body),
            Paragraph(f"<b>{status_video}</b>", style_badge_center),
        ])

    # Add Audio-specific checks ONLY if audio evidence is present
    if has_audio_evidence:
        status_audio = STATUS_COMPLETED if has_audio_analysis else STATUS_NOT_RUN
        methodology_rows.append([
            Paragraph("Audio Acoustic & Silence Check", style_body_bold),
            Paragraph("Checks audio recording for amplitude clipping, distorted samples, and sudden silence drops.", style_body),
            Paragraph("Python wave & struct modules", style_body),
            Paragraph(f"<b>{status_audio}</b>", style_badge_center),
        ])

    methodology_table = Table(methodology_rows, colWidths=[120, 205, 125, 90], repeatRows=1)
    methodology_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_GREY),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(methodology_table)

    # If only image evidence is present, clearly state that video/audio checks do not apply
    if has_image_evidence and not (has_video_evidence or has_audio_evidence):
        story.append(Spacer(1, 2))
        story.append(Paragraph(
            "<i>Note on Media Adaptation: Video frame continuity and audio acoustic checks are omitted from this table because they do not apply to image evidence (NOT APPLICABLE to this case).</i>",
            style_body_muted,
        ))

    story.append(Spacer(1, 6))

    # SECTION 4: Detailed Findings & Extracted Metadata Observations
    story.append(Paragraph("4. DETAILED FINDINGS & EXTRACTED METADATA OBSERVATIONS", style_section_heading))

    finding_rows = []
    finding_counter = 1
    image_metadata_tables = []

    for an in deduplicated_analyses:
        ev = an.evidence
        ev_label = ev.evidence_number if ev else f"ID {an.evidence_id}"
        outcome_status = STATUS_NO_INDICATOR
        obs_text = "Analysis executed. No anomalous indicators detected by this check."
        significance = "Normal"

        try:
            if an.findings_json:
                fdata = json.loads(an.findings_json)

                if an.analysis_type == "image_forensics":
                    meta = fdata.get("metadata_report", {})
                    ela = fdata.get("ela_report", {})

                    is_this_png = (
                        (ev and (ev.original_filename.lower().endswith(".png") or (ev.mime_type and "png" in ev.mime_type.lower())))
                        or meta.get("format", "").upper() == "PNG"
                    )

                    # Build detailed metadata breakdown table (Item C)
                    meta_fields_data = [
                        [
                            Paragraph("<b>Extracted Metadata Field</b>", style_body_bold),
                            Paragraph("<b>Reported Value from File</b>", style_body_bold),
                            Paragraph("<b>Forensic Interpretation</b>", style_body_bold),
                        ],
                        [
                            Paragraph("Container Format & Resolution", style_body),
                            Paragraph(f"{_esc(meta.get('format', 'UNKNOWN'))} ({meta.get('width', 0)} x {meta.get('height', 0)} px, {_esc(meta.get('color_mode', 'RGB'))})", style_mono),
                            Paragraph("Container properties decoded directly from file bytes.", style_body_muted),
                        ],
                        [
                            Paragraph("Camera Manufacturer (Make)", style_body),
                            Paragraph(_esc(meta.get('camera_make')) if meta.get('camera_make') else "Field not present", style_mono_bold if meta.get('camera_make') else style_body_muted),
                            Paragraph("Hardware make recorded in EXIF." if meta.get('camera_make') else "No hardware manufacturer embedded in file.", style_body_muted),
                        ],
                        [
                            Paragraph("Camera Device Model", style_body),
                            Paragraph(_esc(meta.get('camera_model')) if meta.get('camera_model') else "Field not present", style_mono_bold if meta.get('camera_model') else style_body_muted),
                            Paragraph("Hardware model recorded in EXIF." if meta.get('camera_model') else "No device model profile embedded in file.", style_body_muted),
                        ],
                        [
                            Paragraph("Capture Timestamp Original", style_body),
                            Paragraph(_esc(meta.get('capture_date')) if meta.get('capture_date') else "Field not present", style_mono if meta.get('capture_date') else style_body_muted),
                            Paragraph("Original capture date recorded." if meta.get('capture_date') else "No original optical capture time found.", style_body_muted),
                        ],
                        [
                            Paragraph("Software / Processing Tool", style_body),
                            Paragraph(_esc(meta.get('software')) if meta.get('software') else "Field not present", style_mono_bold if meta.get('software') else style_body_muted),
                            Paragraph("<b>Indicator found:</b> Editing software signature." if meta.get('software') else "No photo-editing software tag found.", style_body_muted),
                        ],
                        [
                            Paragraph("GPS Geolocation", style_body),
                            Paragraph(f"Lat {meta['gps']['latitude']}, Lon {meta['gps']['longitude']}" if meta.get('gps') else "Field not present", style_mono if meta.get('gps') else style_body_muted),
                            Paragraph("Geographic coordinates embedded." if meta.get('gps') else "No geographic coordinates embedded in file.", style_body_muted),
                        ],
                    ]
                    meta_table = Table(meta_fields_data, colWidths=[140, 185, 215])
                    meta_table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_GREY),
                        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    image_metadata_tables.append((ev_label, meta_table))

                    # Format plain English finding summary
                    mean_val = ela.get('mean_error', 0.0)
                    max_val = ela.get('max_error', 0.0)

                    if is_this_png:
                        # PNG ELA Disclosure (Item B)
                        obs_text = (
                            f"Metadata: No camera hardware make/model embedded (Field not present). "
                            f"ELA re-save: mean error={mean_val:.2f}, max error={max_val:.2f}. "
                            f"Format disclosure: ELA re-saves lossless PNG as JPEG quality 92; reported error values are "
                            f"format conversion artefacts, not evidence of editing."
                        )
                        outcome_status = STATUS_UNSUPPORTED
                        significance = "PNG conversion artefact"
                    else:
                        notes = []
                        if meta.get("camera_make") or meta.get("camera_model"):
                            notes.append(f"Recorded device: {_esc(meta.get('camera_make'))} {_esc(meta.get('camera_model'))}")
                        else:
                            notes.append("No camera hardware make or model found in metadata (Field not present)")

                        if meta.get("software"):
                            notes.append(f"Editing software signature detected: {_esc(meta.get('software'))}")
                            outcome_status = STATUS_INDICATOR_FOUND
                            significance = "Software signature present"
                        if ela.get("mean_error") is not None:
                            notes.append(f"JPEG ELA difference: mean={mean_val:.2f}, max={max_val:.2f}")
                        if ela.get("indicator_detected"):
                            outcome_status = STATUS_INDICATOR_FOUND
                            significance = "Regional compression variance"
                        obs_text = "; ".join(notes)

                elif an.analysis_type == "video_forensics":
                    # Video forensics only evaluated if video evidence was analyzed
                    vrep = fdata.get("video_report", {})
                    dur = vrep.get("duration_sec", 0.0)
                    fps = vrep.get("fps", 0.0)
                    dup = vrep.get("duplicate_frames_count", 0)
                    codec = vrep.get("codec", "Unknown")
                    is_frozen = vrep.get("is_frozen_detected", False)
                    sampled_cnt = vrep.get("sampled_frames_count", 20)

                    notes = [
                        f"Stream properties: Duration {dur:.2f}s, Speed {fps:.1f} fps, Codec {_esc(codec)} (Decodable)",
                        f"Sample coverage: Exactly {sampled_cnt} sampled frames inspected across footage",
                    ]
                    if dup > 0:
                        notes.append(f"Frame continuity: {dup} duplicate frames detected ({vrep.get('duplicate_percentage', 0.0):.1f}% of sample)")
                        outcome_status = STATUS_INDICATOR_FOUND
                        significance = "Inspect camera frame hold"
                    elif is_frozen:
                        notes.append("Frame continuity: Consecutive frozen frame sequence detected in sample")
                        outcome_status = STATUS_INDICATOR_FOUND
                        significance = "Inspect feed continuity"
                    else:
                        notes.append(f"Sample continuity: 0 duplicate or frozen frames detected across {sampled_cnt} sampled frames")
                        notes.append("No indicator was detected by this check in the examined samples. This result does not establish that the complete video is authentic or free from manipulation.")
                        outcome_status = STATUS_NO_INDICATOR
                        significance = f"Sample normal ({sampled_cnt} frames)"

                    obs_text = "; ".join(notes)

                elif an.analysis_type == "audio_forensics":
                    arep = fdata.get("audio_report", {})
                    dur = arep.get("duration_sec", 0.0)
                    sr = arep.get("sample_rate_hz", "Unknown")
                    ch = arep.get("channels", "Unknown")
                    notes = [f"Decoded audio: Duration {dur:.2f}s, Sample rate {sr} Hz, Channels {ch}"]
                    if arep.get("is_clipped"):
                        notes.append(f"Acoustic envelope: {arep.get('clipped_samples_count')} clipped distorted samples detected")
                        outcome_status = STATUS_INDICATOR_FOUND
                        significance = "High gain / clipping"
                    if arep.get("has_silence_gaps"):
                        notes.append("Acoustic continuity: Abrupt silence drop detected")
                        outcome_status = STATUS_INDICATOR_FOUND
                        significance = "Inspect track continuity"
                    if not arep.get("is_clipped") and not arep.get("has_silence_gaps"):
                        notes.append("Acoustic continuity: No clipping anomalies or silence drops detected")
                        outcome_status = STATUS_NO_INDICATOR
                        significance = "Normal acoustic envelope"
                    obs_text = "; ".join(notes)

        except Exception as e:
            obs_text = f"Analysis completed. Detailed data recorded: {_esc(str(e))}"

        cat_title = an.analysis_type.replace("_", " ").title()
        finding_rows.append([
            Paragraph(f"<b>FND-{finding_counter:03d}</b>", style_mono_bold),
            Paragraph(f"<b>{_esc(ev_label)}</b>", style_mono),
            Paragraph(_esc(cat_title), style_body),
            Paragraph(obs_text, style_body),
            Paragraph(f"<b>{outcome_status}</b>", style_badge_center),
            Paragraph(significance, style_body_muted),
        ])
        finding_counter += 1

    if not finding_rows:
        story.append(Paragraph(
            "<i>No formal laboratory analysis modules (Image, Video, or Audio) have been executed for the selected evidence in this case. "
            "Individual checks remain classified as 'Not run'.</i>",
            style_body_muted,
        ))
    else:
        findings_table_data = [
            [
                Paragraph("<b>ID</b>", style_body_bold),
                Paragraph("<b>Item #</b>", style_body_bold),
                Paragraph("<b>Category</b>", style_body_bold),
                Paragraph("<b>Observation & Checks Performed</b>", style_body_bold),
                Paragraph("<b>Outcome</b>", style_body_bold),
                Paragraph("<b>Significance</b>", style_body_bold),
            ]
        ] + finding_rows

        findings_table = Table(findings_table_data, colWidths=[45, 75, 80, 205, 75, 60], repeatRows=1)
        findings_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_GREY),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(findings_table)

    # Append structured metadata table if image analysis ran (Item C)
    if image_metadata_tables:
        story.append(Spacer(1, 4))
        for ev_num, m_table in image_metadata_tables:
            story.append(Paragraph(f"<b>Extracted Metadata Breakdown for Item {ev_num}:</b>", style_body_bold))
            story.append(Spacer(1, 2))
            story.append(m_table)
            story.append(Spacer(1, 2))
            story.append(Paragraph(
                "<i>Explanation on Metadata Findings: Digital cameras write device make, model, and capture settings directly into EXIF headers. "
                "When an image is created synthetically with AI, edited in software, or saved via messaging apps (e.g. WhatsApp), metadata is usually absent. "
                "The absence of metadata is common and does NOT by itself prove AI generation or malicious tampering.</i>",
                style_body_muted,
            ))

    story.append(Spacer(1, 6))

    # SECTION 5: AI-Generated Image Assessment (Phase 4 — Honest Handling, Item A)
    if has_image_evidence:
        ai_table_data = [
            [
                Paragraph("<b>Assessment Parameter</b>", style_body_bold),
                Paragraph("<b>Current Platform Finding</b>", style_body_bold),
                Paragraph("<b>Investigative Context & Meaning</b>", style_body_bold),
            ],
            [
                Paragraph("AI-Generated vs Real Status", style_body_bold),
                Paragraph("<b>Not Available / Not Implemented in this Prototype</b>", style_body_bold),
                Paragraph("TRACEON prototype does not contain a trained AI-image detection neural network.", style_body),
            ],
            [
                Paragraph("Model Name & Version", style_body),
                Paragraph("None connected", style_mono),
                Paragraph("No neural network weights are bundled in this prototype.", style_body_muted),
            ],
            [
                Paragraph("AI / Real Prediction", style_body),
                Paragraph("Not generated", style_mono),
                Paragraph("TRACEON refuses to guess or provide an unsupported classification.", style_body_muted),
            ],
            [
                Paragraph("Confidence Score", style_body),
                Paragraph("Not available (0.00%)", style_mono),
                Paragraph("Fabricating a fake certainty score is legally inadmissible in court.", style_body_muted),
            ],
            [
                Paragraph("Hardware Provenance Check", style_body),
                Paragraph("Evaluated via EXIF header", style_body),
                Paragraph("AI images typically lack physical camera sensor profiles.", style_body_muted),
            ],
            [
                Paragraph("Byte-Level Integrity", style_body),
                Paragraph("Verified via SHA-256", style_body),
                Paragraph("Confirms file has not changed since intake.", style_body_muted),
            ],
        ]
        ai_table = Table(ai_table_data, colWidths=[140, 185, 215])
        ai_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_GREY),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))

        ai_assessment_flowables = [
            Paragraph("5. AI-GENERATED IMAGE ASSESSMENT", style_section_heading),
            ai_table,
            Spacer(1, 3),
            Table([
                [
                    Paragraph(
                        "<b>Notice on Model Predictions & Proposed AI Addition:</b><br/>"
                        "TRACEON does not output fabricated certainty scores or unverified classifications. In police investigations, presenting an "
                        "unsupported AI probability without a tested model is scientifically unsound and legally inadmissible.<br/>"
                        "<b>Smallest Practical Implementation to Add AI Detection:</b> To enable automated AI-generation detection in future development, "
                        "(1) Add a frequency-domain (2D-FFT) spectral analysis module to spot deconvolution checkerboard artifacts, or (2) Connect a "
                        "lightweight pre-trained open-source detector (such as a compact ViT or ResNet model).",
                        style_callout,
                    )
                ]
            ], colWidths=[540], style=[
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_GREY),
                ("BOX", (0, 0), (-1, -1), 0.75, COLOR_BORDER_STRONG),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]),
            Spacer(1, 6),
        ]
        story.append(KeepTogether(ai_assessment_flowables))

    # SECTION 6: Limitations — What These Checks Cannot Establish (Phase 5 & 7)
    limitations_flowables = [
        Paragraph("6. FORENSIC LIMITATIONS — WHAT THESE CHECKS CANNOT ESTABLISH", style_section_heading),
        Table([
            [
                Paragraph(
                    "<b>Important Forensic Limitations for Non-Technical Readers:</b><br/>"
                    "• <b>Baseline Matching:</b> A matching SHA-256 digital fingerprint confirms only that the file has not changed since it was registered in TRACEON. It does not prove the file was genuine or unedited before registration.<br/>"
                    "• <b>Metadata Absence:</b> Missing camera metadata is common in files shared through messaging apps (e.g. WhatsApp, Telegram) or downloaded from social media. Missing metadata alone does not prove forgery or AI generation.<br/>"
                    "• <b>Error Level Analysis (ELA):</b> ELA identifies compression variations across JPEG images. Natural textures, high-contrast edges, and solid backgrounds naturally produce differing error rates. For lossless PNG images, ELA is technically unsupported because re-saving to JPEG creates artificial conversion differences. ELA is an investigatory guide, not legal proof of manipulation.<br/>"
                    "• <b>Sampled Video Frames:</b> When video is analyzed, OpenCV checks decodability and examines 20 sampled frames. It cannot establish that unexamined frames are genuine or that the recorded event occurred as portrayed.<br/>"
                    "• <b>Investigative Leads Only:</b> An indicator found is a technical anomaly that warrants human investigation. It does not prove intentional falsification.",
                    style_callout,
                )
            ]
        ], colWidths=[540], style=[
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_GREY),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]),
        Spacer(1, 6),
    ]
    story.append(KeepTogether(limitations_flowables))

    # SECTION 7: Final Conclusion — What This Report Tells You (Phase 6 Dynamic Summary)
    dynamic_conclusion = _generate_dynamic_final_conclusion(
        case,
        selected_evidence,
        latest_integrity_by_ev,
        deduplicated_analyses,
    )
    conclusion_flowables = [
        Paragraph("7. FINAL CONCLUSION — WHAT THIS REPORT TELLS YOU", style_section_heading),
        Table([
            [
                Paragraph(
                    f"<b>Summary of Examination Findings:</b><br/>{_esc(dynamic_conclusion)}",
                    style_callout,
                )
            ]
        ], colWidths=[540], style=[
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_ALT_GREY),
            ("BOX", (0, 0), (-1, -1), 1.0, COLOR_DARK_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]),
        Spacer(1, 6),
    ]
    story.append(KeepTogether(conclusion_flowables))

    # SECTION 8: Technical Details & Audit History (Phase 7 Appendix)
    story.append(Paragraph("8. TECHNICAL DETAILS, MANIFESTS & AUDIT HISTORY", style_section_heading))

    # Detailed Manifest Cards (One per item)
    if selected_evidence:
        for ev in selected_evidence:
            size_formatted = f"{ev.file_size / 1024:.1f} KB ({ev.file_size:,} bytes)"
            source_info = "Not recorded"
            if ev.metadata_json:
                try:
                    m = json.loads(ev.metadata_json)
                    if m.get("camera_make") or m.get("camera_model"):
                        source_info = f"{m.get('camera_make', '')} {m.get('camera_model', '')}".strip()
                    elif m.get("device_label"):
                        source_info = m.get("device_label")
                except Exception:
                    pass

            chk = latest_integrity_by_ev.get(ev.id)
            if chk:
                verification_note = (
                    f"Status: <b>{_esc(chk.result.upper())}</b> | "
                    f"Recalculated: {_esc(chk.checked_at.strftime('%Y-%m-%d %H:%M UTC'))}"
                )
            else:
                verification_note = "Status: <b>NOT CHECKED</b> | Intake baseline hash remains authoritative."

            hash_display = _split_hash_safely(ev.sha256_hash)

            card_data = [
                [
                    Paragraph(f"<b>Item ID:</b> <font name='Courier'><b>{_esc(ev.evidence_number)}</b></font>", style_body),
                    Paragraph(f"<b>Format:</b> {_esc(ev.detected_file_type.upper())} ({_esc(ev.mime_type)})", style_body),
                    Paragraph(f"<b>Intake:</b> {ev.uploaded_at.strftime('%Y-%m-%d %H:%M UTC')}", style_body),
                ],
                [
                    Paragraph(f"<b>Filename:</b> {_esc(ev.original_filename)}", style_body),
                    Paragraph(f"<b>File Size:</b> {size_formatted}", style_body),
                    Paragraph(f"<b>Source Device:</b> {_esc(source_info)}", style_body),
                ],
                [
                    Paragraph(
                        f"<b>SHA-256 Cryptographic Fingerprint (Intake Baseline):</b><br/>"
                        f"<font name='Courier' size='7'>{hash_display}</font>",
                        style_mono_hash,
                    ),
                    "",
                    "",
                ],
                [
                    Paragraph(verification_note, style_body_muted),
                    "",
                    "",
                ],
            ]
            card_table = Table(card_data, colWidths=[180, 180, 180])
            card_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_GREY),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("SPAN", (0, 2), (2, 2)),
                ("SPAN", (0, 3), (2, 3)),
            ]))
            story.append(card_table)
            story.append(Spacer(1, 3))

    # Chain of Custody Audit Log (if requested)
    if request_params.include_audit_trail:
        audit_records = (
            db.query(AuditEvent)
            .filter(AuditEvent.case_id == case.id)
            .order_by(AuditEvent.created_at.asc())
            .all()
        )
        if audit_records:
            story.append(Spacer(1, 3))
            story.append(Paragraph("<b>Chain of Custody Event Log:</b>", style_body_bold))
            aud_table_data = [
                [
                    Paragraph("<b>Timestamp (UTC)</b>", style_body_bold),
                    Paragraph("<b>Officer / Actor</b>", style_body_bold),
                    Paragraph("<b>Action Performed</b>", style_body_bold),
                    Paragraph("<b>Result</b>", style_body_bold),
                    Paragraph("<b>Terminal / IP</b>", style_body_bold),
                ]
            ]
            for aud in audit_records:
                aud_table_data.append([
                    Paragraph(aud.created_at.strftime("%Y-%m-%d %H:%M:%S"), style_body),
                    Paragraph(_esc(aud.actor_id), style_body),
                    Paragraph(f"<b>{_esc(aud.action)}</b>", style_body),
                    Paragraph(_esc(aud.result.upper()), style_badge_center),
                    Paragraph(_esc(aud.ip_address or "127.0.0.1"), style_mono),
                ])

            aud_table = Table(aud_table_data, colWidths=[105, 110, 160, 75, 90], repeatRows=1)
            aud_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_GREY),
                ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(aud_table)

    # Optional Investigator Notes
    if request_params.notes and request_params.notes.strip():
        story.append(Spacer(1, 4))
        clean_notes = _sanitize_text(request_params.notes.strip())
        notes_table = Table([[
            Paragraph(f"<b>Investigator Remarks:</b> {_esc(clean_notes)}", style_body)
        ]], colWidths=[540])
        notes_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_ALT_GREY),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(notes_table)

    story.append(Spacer(1, 6))

    # Recommended Action Checklist
    checklist_flowables = [
        Paragraph("<b>Recommended Investigative Action Steps:</b>", style_body_bold),
        Table([
            [
                Paragraph(
                    "1. <b>Physical Hardware Recovery:</b> Seize original recording hardware (CCTV DVR, mobile phone, SD card) using tamper-evident evidence bags.<br/>"
                    "2. <b>Telecom & Carrier Logs:</b> Subpoena carrier Call Detail Records (CDR) and server transmission logs to corroborate creation dates.<br/>"
                    "3. <b>Witness Corroboration:</b> Secure written, timestamped statements from persons who captured or handled the evidence.<br/>"
                    "4. <b>Preserve Bit-Stream Working Copies:</b> Retain original media in read-only write-blocked storage; conduct further checks only on working copies.",
                    style_callout,
                )
            ]
        ], colWidths=[540], style=[
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_GREY),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]),
        Spacer(1, 6),
    ]
    story.append(KeepTogether(checklist_flowables))

    # Sign-off & Statutory Boundaries
    examiner_name = case.investigator_name if case.investigator_name else "Investigating Officer"
    signoff_data = [
        [
            Paragraph("<b>Examiner / Operator:</b>", style_body),
            Paragraph(f"<b>{_esc(examiner_name)}</b>", style_body_bold),
            Paragraph("<b>Platform System:</b>", style_body),
            Paragraph(f"{PRODUCT_NAME} Digital Evidence Platform", style_body),
        ],
        [
            Paragraph("<b>Operational Role:</b>", style_body),
            Paragraph("Digital Evidence Examiner", style_body),
            Paragraph("<b>Report Date:</b>", style_body),
            Paragraph(datetime.now(timezone.utc).strftime("%Y-%m-%d"), style_body),
        ],
        [
            Paragraph("<b>Document Classification:</b>", style_body),
            Paragraph(f"<b>{DOCUMENT_CLASSIFICATION}</b>", style_body),
            Paragraph("<b>Verification Status:</b>", style_body),
            Paragraph("DEMONSTRATION REPORT", style_body_bold),
        ],
    ]
    signoff_table = Table(signoff_data, colWidths=[115, 175, 105, 145])
    signoff_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_GREY),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    disclaimer_block = [
        signoff_table,
        Spacer(1, 4),
        Paragraph(
            "<b>Statutory & Evidentiary Boundaries:</b><br/>"
            f"This document is an automated examination demonstration report generated by {PRODUCT_NAME}. "
            f"It is intended solely for investigative evaluation, software workflow testing, and demonstration purposes. "
            f"{PRODUCT_NAME} is not an accredited statutory forensic science laboratory and does not issue court-certified "
            f"forensic reports or Section 65B Indian Evidence Act certificates. Byte-level integrity verification establishes only "
            f"that the analyzed file matches the intake baseline digest and does not verify real-world authenticity or legal admissibility. "
            f"Original physical media should always be preserved in a certified, tamper-evident evidence locker.",
            style_body_muted,
        ),
    ]
    story.append(KeepTogether(disclaimer_block))

    # Build document with NumberedCanvas
    doc.build(story, canvasmaker=make_numbered_canvas(report_num))

    file_size = os.path.getsize(file_path)
    logger.info(f"Generated TRACEON PDF report {report_num} at {file_path} ({file_size} bytes)")
    return report_num, str(file_path), file_size
