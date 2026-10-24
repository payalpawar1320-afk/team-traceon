import io
import math
import struct
import uuid
import wave
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db
from app.config import settings
from app.utils.audio_analysis import analyze_audio_file

client = TestClient(app)


def setup_module():
    """Ensure database and storage directories are initialized."""
    init_db()
    settings.ensure_storage_directories()


def create_test_case() -> int:
    """Helper to register a case."""
    res = client.post(
        "/api/cases",
        json={
            "title": f"Audio Forensic Case {uuid.uuid4().hex[:6]}",
            "investigator_name": "Cyber Cell Audio Unit",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def generate_synthetic_wav(
    duration_sec: float = 1.0,
    sample_rate: int = 44100,
    channels: int = 1,
    frequency: float = 440.0,
    with_clipping: bool = False,
    with_silence_drop: bool = False,
) -> bytes:
    """
    Generate an in-memory 16-bit PCM WAV audio file using Python's standard wave library.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_out:
        wav_out.setnchannels(channels)
        wav_out.setsampwidth(2)  # 16-bit
        wav_out.setframerate(sample_rate)

        total_frames = int(sample_rate * duration_sec)
        samples = []

        for i in range(total_frames):
            t = float(i) / sample_rate

            if with_silence_drop and int(0.4 * sample_rate) <= i <= int(0.6 * sample_rate):
                # 200ms of digital zero silence drop in the middle of active signal
                val = 0
            elif with_clipping and int(0.2 * sample_rate) <= i <= int(0.35 * sample_rate):
                # Hard 0 dBFS clipping: clamp to max positive / negative 16-bit bounds
                val = 32767 if math.sin(2.0 * math.pi * frequency * t) >= 0 else -32768
            else:
                # Normal clean sine wave at ~70% peak amplitude
                val = int(0.7 * 32767 * math.sin(2.0 * math.pi * frequency * t))

            # Clamp to 16-bit integer range
            val = max(-32768, min(32767, val))

            for _ in range(channels):
                samples.append(val)

        raw_bytes = struct.pack(f"<{len(samples)}h", *samples)
        wav_out.writeframes(raw_bytes)

    return buffer.getvalue()


def test_analyze_clean_wav_audio():
    """Verify clean WAV properties, RMS dbfs calculation, and absence of clipping."""
    case_id = create_test_case()
    wav_bytes = generate_synthetic_wav(duration_sec=1.5, sample_rate=44100, channels=1, frequency=440.0)

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("interview_recording.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/audio?target_waveform_points=50")
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    assert data["evidence_id"] == ev_id
    assert data["analysis_type"] == "audio_forensics"
    assert "No indicator detected" in data["status"]

    report = data["audio_report"]
    assert "WAV" in report["format"]
    assert report["sample_rate_hz"] == 44100
    assert report["channels"] == 1
    assert report["channel_mode"] == "Mono"
    assert report["bit_depth"] == 16
    assert report["is_clipped"] is False
    assert report["clipped_samples_count"] == 0
    assert report["silence_drop_count"] == 0
    assert report["duration_sec"] >= 1.4
    assert len(report["waveform_peaks"]) > 0
    assert data["limitations"] != ""


def test_analyze_clipped_wav_audio():
    """Verify detection of 0 dBFS signal clipping in audio."""
    case_id = create_test_case()
    clipped_wav = generate_synthetic_wav(duration_sec=1.0, with_clipping=True)

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("clipped_call.wav", io.BytesIO(clipped_wav), "audio/wav")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/audio")
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    report = data["audio_report"]
    assert report["is_clipped"] is True
    assert report["clipped_samples_count"] > 0
    assert any("Clipping" in f["title"] for f in report["findings"])
    assert data["total_indicators"] >= 1


def test_analyze_silence_drop_wav_audio():
    """Verify detection of digital zero silence drop discontinuities in audio."""
    case_id = create_test_case()
    silence_wav = generate_synthetic_wav(duration_sec=1.2, with_silence_drop=True)

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("drop_call.wav", io.BytesIO(silence_wav), "audio/wav")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/audio")
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    report = data["audio_report"]
    assert report["silence_drop_count"] >= 1
    assert any("Silence" in f["title"] for f in report["findings"])


def test_non_audio_rejected_for_audio_analysis():
    """Verify attempting audio analysis on image/document evidence returns 400 Bad Request."""
    case_id = create_test_case()
    # 1x1 valid PNG
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa76M\xda\x00\x00\x00\x00IEND\xaeB`\x82"

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("photo.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    analyze_res = client.post(f"/api/evidence/{ev_id}/analyze/audio")
    assert analyze_res.status_code == 400
    assert "audio" in analyze_res.json()["detail"].lower()


def test_retrieve_audio_analysis_history():
    """Verify GET /api/evidence/{id}/analysis returns deserialized audio forensics."""
    case_id = create_test_case()
    wav_bytes = generate_synthetic_wav(duration_sec=0.5)

    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("evidence_audio.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert upload_res.status_code == 201
    ev_id = upload_res.json()["id"]

    # Analyze
    client.post(f"/api/evidence/{ev_id}/analyze/audio")

    # Fetch history
    history_res = client.get(f"/api/evidence/{ev_id}/analysis")
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) >= 1
    assert history[0]["analysis_type"] == "audio_forensics"
    assert "audio_report" in history[0]
    assert "WAV" in history[0]["audio_report"]["format"]
