import hashlib
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("evidenceguard.video_analysis")


def _fourcc_to_str(fourcc_val: float) -> str:
    """Convert OpenCV integer fourcc code to readable 4-character string."""
    try:
        val = int(fourcc_val)
        chars = [chr((val >> (8 * i)) & 0xFF) for i in range(4)]
        clean = "".join(c for c in chars if c.isprintable())
        return clean.strip() or "H264/AVC"
    except Exception:
        return "UNKNOWN"


def analyze_video_file(
    video_path: str,
    derived_dir: str,
    target_sample_frames: int = 20,
) -> Dict[str, Any]:
    """
    Perform forensic examination on video/CCTV evidence (FR-06).
    Extracts duration, resolution, FPS, codec, extracts frame sequence samples,
    detects exact duplicate or frozen frames, and evaluates continuity anomalies.
    """
    result: Dict[str, Any] = {
        "status": "completed",
        "duration_sec": 0.0,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "total_frames": 0,
        "codec": "UNKNOWN",
        "sampled_frames_count": 0,
        "duplicate_frames_count": 0,
        "duplicate_percentage": 0.0,
        "is_frozen_detected": False,
        "sampled_frames": [],
        "duplicate_groups": [],
        "findings": [],
        "limitations": (
            "Forensic CCTV & Video Limitations (spec.md §FR-06): "
            "Duplicate or repeated frames may occur naturally in CCTV footage due to low-light frame hold, "
            "temporal compression (e.g. H.264 P-frames), or camera motion-detection thresholds. "
            "A duplicate indicator does not automatically prove malicious tampering or footage splicing."
        ),
    }

    path = Path(video_path)
    if not path.exists():
        result["status"] = "failed"
        result["findings"].append({
            "severity": "high",
            "category": "File Access",
            "title": "Evidence File Missing",
            "description": "Video file was not found on secure storage.",
        })
        return result

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        result["status"] = "failed"
        result["findings"].append({
            "severity": "high",
            "category": "Codec & Decoding",
            "title": "Video Stream Cannot Be Decoded",
            "description": "OpenCV decoder could not read video container or streams. File may be malformed or use an unsupported codec.",
        })
        return result

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cap.get(cv2.CAP_PROP_FOURCC)

        # Handle abnormal or zero fps
        if fps <= 0 or math.isnan(fps):
            fps = 25.0  # Fallback standard CCTV default

        duration_sec = round(total_frames / fps, 2) if total_frames > 0 and fps > 0 else 0.0

        result["width"] = width
        result["height"] = height
        result["fps"] = round(fps, 2)
        result["total_frames"] = total_frames
        result["duration_sec"] = duration_sec
        result["codec"] = _fourcc_to_str(fourcc)

        os.makedirs(derived_dir, exist_ok=True)
        stem = path.stem

        # Determine sampling step
        if total_frames <= target_sample_frames or target_sample_frames <= 0:
            step = 1
        else:
            step = max(1, total_frames // target_sample_frames)

        frame_idx = 0
        sampled_list = []
        hash_to_indices: Dict[str, List[int]] = {}
        index_to_hash: Dict[int, str] = {}

        while cap.isOpened() and len(sampled_list) < target_sample_frames:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            if frame_idx % step == 0:
                timestamp = round(frame_idx / fps, 3) if fps > 0 else 0.0
                thumb_filename = f"{stem}_frame_{frame_idx}.jpg"
                thumb_path = Path(derived_dir) / thumb_filename

                # Save 320px thumbnail for fast web preview
                thumb_h, thumb_w = frame.shape[:2]
                if thumb_w > 480:
                    scale = 480 / thumb_w
                    thumb_img = cv2.resize(frame, (480, int(thumb_h * scale)))
                else:
                    thumb_img = frame

                cv2.imwrite(str(thumb_path), thumb_img, [cv2.IMWRITE_JPEG_QUALITY, 85])

                # Calculate hash on downsampled grayscale representation for duplicate matching
                gray_small = cv2.resize(frame, (64, 64))
                if len(gray_small.shape) == 3:
                    gray_small = cv2.cvtColor(gray_small, cv2.COLOR_BGR2GRAY)
                frame_hash = hashlib.md5(gray_small.tobytes()).hexdigest()

                if frame_hash not in hash_to_indices:
                    hash_to_indices[frame_hash] = []
                hash_to_indices[frame_hash].append(frame_idx)
                index_to_hash[frame_idx] = frame_hash

                sampled_list.append({
                    "frame_index": frame_idx,
                    "timestamp_sec": timestamp,
                    "thumbnail_filename": thumb_filename,
                    "thumbnail_url": f"/api/analysis/derived/{thumb_filename}",
                    "is_duplicate": False,
                    "duplicate_of_index": None,
                })

            frame_idx += 1

        cap.release()

        # Identify duplicates
        duplicate_groups = []
        dup_frame_count = 0

        for f_hash, indices in hash_to_indices.items():
            if len(indices) > 1:
                primary = indices[0]
                dups = indices[1:]
                dup_frame_count += len(dups)

                # Check if consecutive
                is_consec = any(indices[i] - indices[i - 1] == step for i in range(1, len(indices)))
                timestamps = [
                    next(f["timestamp_sec"] for f in sampled_list if f["frame_index"] == idx)
                    for idx in indices
                ]

                duplicate_groups.append({
                    "primary_frame_index": primary,
                    "duplicate_frame_indices": dups,
                    "timestamps_sec": timestamps,
                    "is_consecutive": is_consec,
                })

                # Mark in sampled list
                for f in sampled_list:
                    if f["frame_index"] in dups:
                        f["is_duplicate"] = True
                        f["duplicate_of_index"] = primary

        result["sampled_frames_count"] = len(sampled_list)
        result["duplicate_frames_count"] = dup_frame_count
        result["duplicate_percentage"] = (
            round((dup_frame_count / len(sampled_list)) * 100, 1) if sampled_list else 0.0
        )
        result["sampled_frames"] = sampled_list
        result["duplicate_groups"] = duplicate_groups

        # Evaluate Findings
        if dup_frame_count > 0:
            consecutive_groups = [g for g in duplicate_groups if g["is_consecutive"]]
            if consecutive_groups:
                result["is_frozen_detected"] = True
                result["findings"].append({
                    "severity": "medium",
                    "category": "Frame Continuity",
                    "title": "Consecutive Duplicate / Frozen Frames Detected",
                    "description": (
                        f"Found {len(consecutive_groups)} sequences of consecutive identical frames. "
                        f"Example: Frame #{consecutive_groups[0]['primary_frame_index']} "
                        f"({consecutive_groups[0]['timestamps_sec'][0]}s) repeats across subsequent sample points. "
                        "May indicate video freeze, camera sensor pause, or repeated frame encoding."
                    ),
                })
            else:
                result["findings"].append({
                    "severity": "low",
                    "category": "Frame Repetition",
                    "title": "Non-Consecutive Duplicate Frames Detected",
                    "description": (
                        f"Detected {dup_frame_count} non-consecutive duplicate frames. "
                        "Footage contains identical frames at separate intervals, which may occur in static scenes or video looping."
                    ),
                })
        else:
            result["findings"].append({
                "severity": "info",
                "category": "Frame Continuity",
                "title": "Continuous Frame Sequence",
                "description": (
                    f"All {len(sampled_list)} sampled frames across {duration_sec}s "
                    "exhibit distinct visual content with no identical duplicate frames detected."
                ),
            })

        # Frame rate checks
        if fps < 10.0:
            result["findings"].append({
                "severity": "info",
                "category": "Frame Rate",
                "title": "Low Frame Rate CCTV Stream",
                "description": f"Video frame rate is {fps} FPS, typical of bandwidth-constrained CCTV or security DVR recorders.",
            })

    except Exception as e:
        logger.error(f"Error inspecting video {video_path}: {e}")
        result["status"] = "failed"
        result["findings"].append({
            "severity": "high",
            "category": "Video Analysis Error",
            "title": "Video Analysis Exception",
            "description": f"Encountered error during frame extraction and inspection: {str(e)}",
        })

    return result
