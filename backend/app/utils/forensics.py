import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

# Supported format mappings according to spec.md FR-03
# Images: JPG, JPEG, PNG
# Videos: MP4, MOV, AVI
# Audio: WAV, MP3
ALLOWED_MIME_TYPES: Dict[str, str] = {
    # Images
    "image/jpeg": "image",
    "image/jpg": "image",
    "image/png": "image",
    # Videos
    "video/mp4": "video",
    "video/quicktime": "video",
    "video/x-msvideo": "video",
    "video/avi": "video",
    # Audio
    "audio/wav": "audio",
    "audio/x-wav": "audio",
    "audio/wave": "audio",
    "audio/mpeg": "audio",
    "audio/mp3": "audio",
}

EXTENSION_TO_MIME: Dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
}


def sanitize_filename(filename: str) -> str:
    """
    Sanitize uploaded filename to prevent directory traversal and filesystem injection.
    Strips path components, null bytes, and non-printable characters.
    """
    base = os.path.basename(filename)
    # Remove null bytes and path separators
    clean = re.sub(r"[\x00/\\:*?\"<>|]", "_", base).strip()
    if not clean or clean.startswith("."):
        clean = f"evidence_{clean}" if clean else "unnamed_evidence"
    # Limit length to 200 characters while preserving extension
    if len(clean) > 200:
        stem = Path(clean).stem[:180]
        suffix = Path(clean).suffix[:20]
        clean = f"{stem}{suffix}"
    return clean


def inspect_magic_bytes(header: bytes) -> Optional[Tuple[str, str]]:
    """
    Inspect the file header (magic bytes) to verify actual file signature.
    Returns (detected_file_type, canonical_mime_type) if verified, else None.
    """
    if len(header) < 4:
        return None

    # 1. JPEG: FF D8 FF
    if header.startswith(b"\xFF\xD8\xFF"):
        return ("image", "image/jpeg")

    # 2. PNG: 89 50 4E 47 0D 0A 1A 0A
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ("image", "image/png")

    # 3. MP4 / MOV (ISO Base Media File Format box 'ftyp')
    if len(header) >= 12 and header[4:8] == b"ftyp":
        major_brand = header[8:12]
        # QuickTime MOV brand is typically 'qt  '
        if major_brand == b"qt  ":
            return ("video", "video/quicktime")
        # Standard MP4 brands include isom, iso2, mp41, mp42, mp71, M4V , dash, etc.
        return ("video", "video/mp4")

    # MOV alternative container signatures (moov, mdat, wide)
    if len(header) >= 8 and header[4:8] in {b"moov", b"mdat", b"wide", b"skip"}:
        return ("video", "video/quicktime")

    # 4. AVI: RIFF....AVI 
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"AVI ":
        return ("video", "video/x-msvideo")

    # 5. WAV: RIFF....WAVE
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return ("audio", "audio/wav")

    # 6. MP3: ID3 header or MPEG sync word (0xFFE or 0xFFF)
    if header.startswith(b"ID3"):
        return ("audio", "audio/mpeg")
    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return ("audio", "audio/mpeg")

    return None


def calculate_sha256(file_path: str) -> str:
    """
    Calculate SHA-256 cryptographic digest of a file strictly in binary read mode.
    Reads in 64 KB chunks to guarantee low memory overhead and absolute byte equality.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest().lower()


def generate_storage_filename(original_filename: str) -> str:
    """
    Generate an unpredictable, UUID-based storage filename outside public directories.
    Prevents path collision and traversal attacks.
    """
    ext = Path(original_filename).suffix.lower()
    if not ext:
        ext = ".bin"
    return f"{uuid.uuid4().hex}{ext}"
