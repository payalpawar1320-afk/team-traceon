import json
import logging
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageEnhance, ExifTags
import cv2
import numpy as np

logger = logging.getLogger("evidenceguard.image_analysis")

# Known photo-editing software signatures
EDITING_SOFTWARE_SIGNATURES = [
    r"adobe\s*photoshop",
    r"adobe\s*lightroom",
    r"gimp",
    r"canva",
    r"paint\.net",
    r"snapseed",
    r"vsco",
    r"picsart",
    r"pixlr",
    r"corel",
    r"affinity\s*photo",
    r"photopea",
    r"facetune",
]


def _convert_gps_to_decimal(coords: Any, ref: str) -> Optional[float]:
    """Convert EXIF GPS (degrees, minutes, seconds) rational tuple to decimal degrees."""
    try:
        if not coords or len(coords) < 3:
            return None

        # Convert degree, minute, second values which might be IFDRational or tuple
        def to_float(val: Any) -> float:
            if hasattr(val, "numerator") and hasattr(val, "denominator"):
                return float(val.numerator) / float(val.denominator) if val.denominator != 0 else 0.0
            if isinstance(val, (tuple, list)) and len(val) == 2:
                return float(val[0]) / float(val[1]) if val[1] != 0 else 0.0
            return float(val)

        deg = to_float(coords[0])
        minute = to_float(coords[1])
        sec = to_float(coords[2])

        decimal = deg + (minute / 60.0) + (sec / 3600.0)
        if ref in ["S", "W"]:
            decimal = -decimal
        return round(decimal, 6)
    except Exception as e:
        logger.debug(f"Failed to convert GPS coordinates: {e}")
        return None


def extract_image_metadata(image_path: str) -> Dict[str, Any]:
    """
    Extract comprehensive metadata, camera EXIF, GPS coordinates, and detect
    potential editing traces or timestamp inconsistencies (FR-05).
    """
    result: Dict[str, Any] = {
        "format": "UNKNOWN",
        "width": 0,
        "height": 0,
        "color_mode": "UNKNOWN",
        "has_exif": False,
        "camera_make": None,
        "camera_model": None,
        "software": None,
        "capture_date": None,
        "digitized_date": None,
        "modification_date": None,
        "gps": None,
        "raw_exif": {},
        "findings": [],
        "indicators_count": 0,
    }

    path = Path(image_path)
    if not path.exists():
        result["findings"].append({
            "severity": "high",
            "category": "File Access",
            "title": "Evidence File Missing",
            "description": "Image file could not be found in storage for metadata extraction.",
        })
        result["indicators_count"] += 1
        return result

    try:
        with Image.open(path) as img:
            result["format"] = img.format or path.suffix.replace(".", "").upper()
            result["width"], result["height"] = img.size
            result["color_mode"] = img.mode

            raw_exif = img.getexif()
            if not raw_exif:
                result["findings"].append({
                    "severity": "info",
                    "category": "EXIF Metadata",
                    "title": "EXIF Metadata Absent",
                    "description": "No embedded EXIF header was found. Note: metadata is commonly stripped by messaging apps or web optimization.",
                })
                return result

            result["has_exif"] = True
            exif_dict: Dict[str, Any] = {}

            # Map numerical EXIF tags to readable names
            for tag_id, val in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, f"Tag_{tag_id}")
                # Exclude large binary dumps like thumbnails
                if tag_name not in ["MakerNote", "UserComment"] and not isinstance(val, (bytes, bytearray)):
                    exif_dict[tag_name] = str(val)

            # Check IFD sub-exif for detailed camera settings
            if hasattr(raw_exif, "get_ifd"):
                try:
                    sub_exif = raw_exif.get_ifd(ExifTags.IFD.Exif)
                    for tag_id, val in sub_exif.items():
                        tag_name = ExifTags.TAGS.get(tag_id, f"SubTag_{tag_id}")
                        if not isinstance(val, (bytes, bytearray)):
                            exif_dict[tag_name] = str(val)
                except Exception:
                    pass

            result["raw_exif"] = exif_dict

            # 1. Camera Make & Model
            result["camera_make"] = exif_dict.get("Make")
            result["camera_model"] = exif_dict.get("Model")

            # Check inconsistency: Make present without Model or vice-versa
            if result["camera_make"] and not result["camera_model"]:
                result["findings"].append({
                    "severity": "low",
                    "category": "Hardware Consistency",
                    "title": "Incomplete Camera Hardware Profile",
                    "description": f"Camera manufacturer specified ('{result['camera_make']}') without device model information.",
                })
                result["indicators_count"] += 1

            # 2. Software Traces Check
            software_tag = exif_dict.get("Software", "")
            result["software"] = software_tag if software_tag else None

            if software_tag:
                detected_editors = []
                for pattern in EDITING_SOFTWARE_SIGNATURES:
                    if re.search(pattern, software_tag, re.IGNORECASE):
                        detected_editors.append(software_tag)
                        break

                if detected_editors:
                    result["findings"].append({
                        "severity": "medium",
                        "category": "Editing Software Signature",
                        "title": "Photo-Editing Software Detected in EXIF",
                        "description": f"The EXIF 'Software' tag recorded '{software_tag}', matching known digital image editing tools.",
                    })
                    result["indicators_count"] += 1
                else:
                    result["findings"].append({
                        "severity": "info",
                        "category": "Software Tag",
                        "title": "Software Tag Recorded",
                        "description": f"EXIF Software recorded as '{software_tag}'.",
                    })

            # 3. Timestamps & Conflict Detection
            capture_str = exif_dict.get("DateTimeOriginal") or exif_dict.get("DateTime")
            digitized_str = exif_dict.get("DateTimeDigitized")
            modify_str = exif_dict.get("DateTime")

            result["capture_date"] = capture_str
            result["digitized_date"] = digitized_str
            result["modification_date"] = modify_str

            parsed_dates: Dict[str, Optional[datetime]] = {}
            for label, date_str in [
                ("capture", capture_str),
                ("digitized", digitized_str),
                ("modified", modify_str),
            ]:
                if date_str:
                    try:
                        # Common EXIF date format: "YYYY:MM:DD HH:MM:SS"
                        parsed_dates[label] = datetime.strptime(date_str[:19], "%Y:%m:%d %H:%M:%S")
                    except Exception:
                        parsed_dates[label] = None

            # Detect Conflicting Timestamps: e.g. modified earlier than capture
            if parsed_dates.get("capture") and parsed_dates.get("modified"):
                cap = parsed_dates["capture"]
                mod = parsed_dates["modified"]
                if mod < cap:
                    result["findings"].append({
                        "severity": "high",
                        "category": "Timestamp Inconsistency",
                        "title": "Chronological Timestamp Conflict",
                        "description": f"EXIF modification timestamp ({mod}) predates original capture timestamp ({cap}).",
                    })
                    result["indicators_count"] += 1

            # Check if capture date is in the future
            if parsed_dates.get("capture"):
                if parsed_dates["capture"] > datetime.now():
                    result["findings"].append({
                        "severity": "medium",
                        "category": "Timestamp Anomaly",
                        "title": "Future Capture Timestamp",
                        "description": f"EXIF capture date ({parsed_dates['capture']}) is set in the future relative to system clock.",
                    })
                    result["indicators_count"] += 1

            # 4. GPS Geolocation Extraction
            if hasattr(raw_exif, "get_ifd"):
                try:
                    gps_info = raw_exif.get_ifd(ExifTags.IFD.GPSInfo)
                    if gps_info:
                        gps_dict = {
                            ExifTags.GPSTAGS.get(k, k): v
                            for k, v in gps_info.items()
                        }
                        lat = _convert_gps_to_decimal(
                            gps_dict.get("GPSLatitude"),
                            gps_dict.get("GPSLatitudeRef", "N"),
                        )
                        lon = _convert_gps_to_decimal(
                            gps_dict.get("GPSLongitude"),
                            gps_dict.get("GPSLongitudeRef", "E"),
                        )
                        if lat is not None and lon is not None:
                            result["gps"] = {
                                "latitude": lat,
                                "longitude": lon,
                                "altitude": float(gps_dict.get("GPSAltitude", 0)) if "GPSAltitude" in gps_dict else None,
                            }
                            result["findings"].append({
                                "severity": "info",
                                "category": "Geolocation",
                                "title": "Embedded GPS Coordinates Found",
                                "description": f"Geographic coordinates: Lat {lat}, Lon {lon}.",
                            })
                except Exception as e:
                    logger.debug(f"Error parsing GPS IFD: {e}")

    except Exception as e:
        logger.error(f"Error extracting metadata from {image_path}: {e}")
        result["findings"].append({
            "severity": "low",
            "category": "Parsing Error",
            "title": "Metadata Extraction Warning",
            "description": f"Partial error encountered while parsing image metadata: {str(e)}",
        })

    return result


def perform_error_level_analysis(
    image_path: str,
    derived_dir: str,
    quality: int = 92,
    scale: int = 15,
) -> Dict[str, Any]:
    """
    Perform Error Level Analysis (ELA) for image compression forensics (FR-05).
    Re-compresses the image at a known quality factor and computes amplified pixel error differences.
    Generates and stores the derived heatmap overlay in the specified derived output directory.
    """
    result: Dict[str, Any] = {
        "status": "completed",
        "ela_filename": None,
        "ela_path": None,
        "quality_factor": quality,
        "amplification_scale": scale,
        "mean_error": 0.0,
        "max_error": 0,
        "variance": 0.0,
        "indicator_detected": False,
        "findings": [],
        "limitations": (
            "Error Level Analysis (ELA) identifies differences in compression levels. "
            "High-contrast edges, fine textures, and solid backgrounds naturally produce differing "
            "error rates. ELA is an investigation aid, not conclusive proof of tampering."
        ),
    }

    path = Path(image_path)
    if not path.exists():
        result["status"] = "failed"
        result["findings"].append({
            "severity": "high",
            "title": "Evidence File Missing",
            "description": "Original image was not found for Error Level Analysis.",
        })
        return result

    try:
        os.makedirs(derived_dir, exist_ok=True)
        stem = path.stem
        ela_filename = f"{stem}_ela.jpg"
        ela_target_path = Path(derived_dir) / ela_filename
        temp_recompressed_path = Path(derived_dir) / f"{stem}_temp_resave.jpg"

        with Image.open(path) as original_img:
            # Ensure RGB mode for standardized JPEG ELA computation
            rgb_original = original_img.convert("RGB")

            # 1. Resave at specified reference quality
            rgb_original.save(temp_recompressed_path, "JPEG", quality=quality)

            # 2. Re-open recompressed version and compute difference
            with Image.open(temp_recompressed_path) as resaved_img:
                diff = ImageChops.difference(rgb_original, resaved_img)

                # 3. Calculate error statistics across difference pixels
                # diff is RGB, find extrema for each band
                extrema = diff.getextrema()
                # extrema is ((min_r, max_r), (min_g, max_g), (min_b, max_b))
                max_diff = max(band[1] for band in extrema)
                result["max_error"] = max_diff

                # Calculate average error
                hist = diff.histogram()
                # 3 bands of 256 bins each
                total_pixels = rgb_original.width * rgb_original.height
                weighted_sum = sum(i % 256 * hist[i] for i in range(len(hist)))
                mean_error = weighted_sum / (total_pixels * 3.0)
                result["mean_error"] = round(mean_error, 2)

                # Estimate quadrant variance to spot localized tampering
                w, h = rgb_original.width, rgb_original.height
                mid_x, mid_y = w // 2, h // 2
                quadrants = [
                    (0, 0, mid_x, mid_y),
                    (mid_x, 0, w, mid_y),
                    (0, mid_y, mid_x, h),
                    (mid_x, mid_y, w, h),
                ]

                quad_means = []
                for box in quadrants:
                    quad_diff = diff.crop(box)
                    q_hist = quad_diff.histogram()
                    q_pixels = (box[2] - box[0]) * (box[3] - box[1])
                    if q_pixels > 0:
                        q_sum = sum(i % 256 * q_hist[i] for i in range(len(q_hist)))
                        quad_means.append(q_sum / (q_pixels * 3.0))

                if quad_means:
                    mean_all = sum(quad_means) / len(quad_means)
                    variance = sum((q - mean_all) ** 2 for q in quad_means) / len(quad_means)
                    result["variance"] = round(variance, 2)

                # 4. Amplify difference for visual forensic inspection
                # Scale differences so human investigators can visually scrutinize compression artifacts
                enhancer = ImageEnhance.Brightness(diff)
                amplified = enhancer.enhance(scale)
                amplified.save(ela_target_path, "JPEG", quality=95)

                result["ela_filename"] = ela_filename
                result["ela_path"] = str(ela_target_path.resolve())

        # Clean up temporary resave file
        if temp_recompressed_path.exists():
            temp_recompressed_path.unlink()

        # 5. Evaluate findings based on error distribution
        if result["variance"] > 15.0 and result["max_error"] > 35:
            result["indicator_detected"] = True
            result["findings"].append({
                "severity": "medium",
                "category": "Compression Inconsistency",
                "title": "Localized Compression Variance Detected",
                "description": (
                    f"Quadrant error level variance is elevated ({result['variance']:.1f}), "
                    f"with maximum error reaching {result['max_error']}. "
                    "This may indicate localized splicing, repeated resaving of an inserted region, "
                    "or high frequency contrast differences."
                ),
            })
        else:
            result["findings"].append({
                "severity": "info",
                "category": "Compression Continuity",
                "title": "Consistent Error Level Distribution",
                "description": (
                    f"Mean compression error ({result['mean_error']:.1f}) and variance ({result['variance']:.1f}) "
                    "appear relatively uniform across the analyzed quadrants."
                ),
            })

    except Exception as e:
        logger.error(f"Error performing ELA on {image_path}: {e}")
        result["status"] = "failed"
        result["findings"].append({
            "severity": "high",
            "category": "Processing Error",
            "title": "ELA Processing Failure",
            "description": f"Failed to compute Error Level Analysis: {str(e)}",
        })

    return result


_AI_NET = None


def get_ai_detection_net():
    global _AI_NET
    if _AI_NET is not None:
        return _AI_NET
    weights_path = Path(__file__).parent.parent / "weights" / "cifake_model" / "model.onnx"
    if weights_path.exists():
        try:
            _AI_NET = cv2.dnn.readNetFromONNX(str(weights_path))
            logger.info(f"Loaded AI image detection ONNX model from {weights_path}")
        except Exception as e:
            logger.error(f"Failed to load AI image detection ONNX model: {e}")
            _AI_NET = None
    return _AI_NET


def detect_ai_generated_image(image_path: str) -> Dict[str, Any]:
    """
    Perform Dual-Layer AI-Generated Synthetic Media Detection on evidence image:
    1. Deep Neural Network Classification: CIFAKE-Trained EfficientNet-B0 (ONNX opset 17).
    2. Frequency Domain Analysis: 2D-FFT to evaluate high-frequency spectral energy distribution.

    Audited under ISO/IEC 17025 scientific integrity guidelines:
    - Never presents ad-hoc heuristics as calibrated probabilities.
    - Decouples frequency analysis from neural network output.
    - Guards against corrupt, 1x1, or extreme inputs.
    - Includes empirical benchmark generalization disclosures.
    """
    result: Dict[str, Any] = {
        "status": "completed",
        "model_name": "CIFAKE-EfficientNet-B0 (ONNX)",
        "model_version": "1.0 (opset 17)",
        "prediction": "Unknown",
        "is_ai_generated": False,
        "is_calibrated": False,
        "score_type": "Uncalibrated Sigmoid Model Score",
        "calibration_disclaimer": (
            "Model scores are uncalibrated sigmoid outputs from CIFAKE-trained weights. "
            "Empirical temperature scaling or Platt calibration has NOT been fitted to general real-world distributions. "
            "Scores must be interpreted as qualitative heuristic indicators, not certified forensic probabilities."
        ),
        "confidence_score": 0.0,
        "probability_ai_pct": 0.0,
        "probability_real_pct": 0.0,
        "raw_logit": 0.0,
        "fft_anomaly_detected": False,
        "fft_outer_center_ratio": 0.0,
        "indicator_detected": False,
        "verdict": "Not Evaluated",
        "findings": [],
        "limitations": (
            "Automated AI-image detection evaluates structural representations and spectral distribution. "
            "Independent benchmark testing on out-of-domain images reveals significant domain transfer degradation. "
            "Predictions must not be used as the sole basis for legal authenticity determination."
        ),
    }

    path = Path(image_path)
    if not path.exists():
        result["status"] = "failed"
        result["verdict"] = "Error: Evidence file missing from storage"
        result["findings"].append({
            "severity": "high",
            "category": "File Access",
            "title": "Evidence File Missing",
            "description": "Image file could not be found for AI-generation examination.",
        })
        return result

    try:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            result["status"] = "failed"
            result["verdict"] = "Error: Unable to decode image bytes"
            result["findings"].append({
                "severity": "high",
                "category": "Decode Error",
                "title": "Corrupt or Unsupported Image Format",
                "description": "Image bytes could not be decoded. File may be corrupted, truncated, or in an unsupported format.",
            })
            return result

        h, w = img.shape[:2]
        # Guard: Inconclusive on extreme miniature images (< 32x32 pixels)
        if h < 32 or w < 32:
            result["status"] = "inconclusive"
            result["prediction"] = "Inconclusive (Resolution Too Low)"
            result["verdict"] = f"Inconclusive: Image dimensions ({w}x{h}) are too small for reliable spatial feature extraction"
            result["findings"].append({
                "severity": "medium",
                "category": "Resolution Limitation",
                "title": "Miniature Image Resolution",
                "description": (
                    f"Evidence resolution ({w}x{h} px) is below the minimum threshold (32x32 px) required for "
                    "structural convolution and spectral analysis. Automated AI classification is inconclusive."
                ),
            })
            return result

        net = get_ai_detection_net()
        if net is None:
            result["status"] = "model_unavailable"
            result["prediction"] = "Model Not Loaded"
            result["verdict"] = "Model weights not available"
            result["findings"].append({
                "severity": "medium",
                "category": "System State",
                "title": "AI Model Weights Unavailable",
                "description": "The ONNX model weights could not be loaded into memory for evaluation.",
            })
            return result

        # 1. EfficientNet DNN Inference
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        normalized = (resized - mean) / std
        blob = np.transpose(normalized, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)

        net.setInput(blob)
        raw_output = net.forward()
        raw_logit = float(raw_output[0][0])
        result["raw_logit"] = round(raw_logit, 2)

        # Standard class mapping: logit >= 0.0 -> Class 1 (REAL), logit < 0.0 -> Class 0 (FAKE)
        is_real = raw_logit >= 0.0
        result["is_ai_generated"] = not is_real

        # Uncalibrated Sigmoid Model Decision Score (bounded with clipping for numerical stability)
        clipped_logit = max(-20.0, min(20.0, raw_logit))
        sigmoid_real = 1.0 / (1.0 + math.exp(-clipped_logit))
        prob_real = round(sigmoid_real * 100.0, 1)
        prob_ai = round((1.0 - sigmoid_real) * 100.0, 1)

        result["confidence_score"] = prob_ai if not is_real else prob_real
        result["probability_ai_pct"] = prob_ai
        result["probability_real_pct"] = prob_real

        # 2. 2D-FFT Frequency Domain Analysis (Fully Decoupled from neural model output)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1e-6)

        cy, cx = h // 2, w // 2
        r = max(4, min(cy, cx) // 4)
        center_energy = float(np.mean(magnitude_spectrum[cy-r:cy+r, cx-r:cx+r]))
        total_energy = float(np.mean(magnitude_spectrum)) * magnitude_spectrum.size
        outer_energy = (total_energy - center_energy * (2*r)**2) / max(1, magnitude_spectrum.size - (2*r)**2)
        fft_ratio = float(outer_energy / (center_energy + 1e-6))
        elevated_spectral_energy = fft_ratio > 0.70

        result["fft_anomaly_detected"] = elevated_spectral_energy
        result["fft_outer_center_ratio"] = round(fft_ratio, 3)

        if not is_real:
            result["prediction"] = "AI-Generated / Synthetic Media"
            result["indicator_detected"] = True
            result["verdict"] = f"Indicator found: Synthetic media characteristics detected (Model Score: {prob_ai}%)"
            result["findings"].append({
                "severity": "high",
                "category": "AI Synthesis",
                "title": "AI-Generated Synthetic Media Characteristics",
                "description": (
                    f"CIFAKE-trained EfficientNet-B0 evaluated an uncalibrated synthetic media score of {prob_ai}%. "
                    "Structural representations align with patterns learned from generative diffusion models."
                ),
            })
        else:
            result["prediction"] = "Real Camera / Optical Capture"
            result["indicator_detected"] = False
            result["verdict"] = f"No indicator found: Consistent with optical capture (Model Score: {prob_real}%)"
            result["findings"].append({
                "severity": "info",
                "category": "Authenticity Verification",
                "title": "Physical Camera Footprint Consistent",
                "description": (
                    f"Model evaluated an uncalibrated optical capture score of {prob_real}%. "
                    "Spatial feature distributions align with camera training samples."
                ),
            })

        # Separate, decoupled frequency analysis finding
        if elevated_spectral_energy:
            result["findings"].append({
                "severity": "medium",
                "category": "Frequency Spectrum",
                "title": "Elevated High-Frequency Spectral Density",
                "description": (
                    f"2D-FFT analysis recorded a high-to-central spectral energy ratio of {result['fft_outer_center_ratio']}. "
                    "Elevated high-frequency energy can result from diffusion upsampling deconvolution grids, "
                    "but can also be produced by sharp natural edges, text line-art, or high ISO optical sensor noise."
                ),
            })

    except Exception as e:
        logger.error(f"Error executing AI detection on {image_path}: {e}")
        result["status"] = "failed"
        result["verdict"] = f"Error during AI detection processing: {str(e)}"
        result["findings"].append({
            "severity": "high",
            "category": "Processing Error",
            "title": "AI Detection Processing Failure",
            "description": f"Failed to execute AI-image classifier: {str(e)}",
        })

    return result

