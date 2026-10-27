"""Conservative media forensics and optional configured synthetic-image model.

Metadata, compression residuals and C2PA byte markers are observations, not a
deepfake verdict. A model score is returned only when an operator explicitly
configures a real Hugging Face image-classification model; its raw labels and
scores are preserved and described as uncalibrated for operational deployment.
"""
from __future__ import annotations

import io
import json
from typing import Any

import numpy as np
from PIL import ExifTags, Image, ImageFilter
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AnalysisRun, MediaAsset, MediaForensics
from . import storage

settings = get_settings()
AI_METADATA_TERMS = (
    "stable diffusion", "midjourney", "dall-e", "dall·e", "comfyui", "automatic1111",
    "novelai", "adobe firefly", "leonardo.ai", "invokeai", "flux.1", "gemini image",
)
SELECTED_EXIF = {"Make", "Model", "Software", "DateTime", "DateTimeOriginal", "DateTimeDigitized", "ImageDescription", "UserComment", "CreatorTool", "History"}
_MODEL_CACHE: dict[tuple[str, str | None], Any] = {}


def _short(value: Any, limit: int = 500) -> str:
    return str(value)[:limit]


def metadata_observations(image: Image.Image, raw: bytes) -> tuple[dict, list[dict]]:
    metadata: dict[str, str] = {}
    try:
        exif = image.getexif()
        for key, value in exif.items():
            name = ExifTags.TAGS.get(key, str(key))
            if name in SELECTED_EXIF:
                metadata[name] = _short(value)
    except Exception:
        metadata["exif_read_status"] = "unavailable_or_malformed"
    for key in ("Software", "Description", "Comment", "Author", "Creation Time", "XML:com.adobe.xmp"):
        value = image.info.get(key)
        if value is not None and key not in metadata:
            metadata[key] = _short(value, 1500 if key.startswith("XML") else 500)
    haystack = "\n".join(f"{key}: {value}" for key, value in metadata.items()).casefold()
    declarations = [{"indicator": "ai_tool_name_in_metadata", "matched_term": term,
                     "meaning": "Metadata mentions a tool; it may be edited, copied or removed and is not independent proof of generation."}
                    for term in AI_METADATA_TERMS if term in haystack]
    c2pa_marker = b"c2pa" in raw.lower() and (b"jumbf" in raw.lower() or b"jumb" in raw.lower())
    if c2pa_marker:
        declarations.append({"indicator": "possible_c2pa_manifest_bytes", "matched_term": "c2pa+jumbf",
                             "meaning": "A possible manifest marker only; cryptographic validation requires a C2PA validator and is not claimed here."})
    return metadata, declarations


def pixel_indicators(image: Image.Image, mime: str) -> dict:
    working = image.convert("RGB")
    original_size = [working.width, working.height]
    working.thumbnail((2048, 2048))
    gray = working.convert("L")
    pixels = np.asarray(gray, dtype=np.float32)
    blurred = np.asarray(gray.filter(ImageFilter.GaussianBlur(radius=1.0)), dtype=np.float32)
    residual = pixels - blurred
    result: dict[str, Any] = {
        "original_dimensions": original_size,
        "analyzed_dimensions": [working.width, working.height],
        "downsampled_for_analysis": original_size != [working.width, working.height],
        "residual_statistics": {
            "mean_absolute": round(float(np.mean(np.abs(residual))), 5),
            "standard_deviation": round(float(np.std(residual)), 5),
            "p95_absolute": round(float(np.percentile(np.abs(residual), 95)), 5),
            "method": "grayscale pixel minus GaussianBlur(radius=1), after bounded RGB downsampling",
        },
    }
    if mime == "image/jpeg":
        buffer = io.BytesIO()
        working.save(buffer, format="JPEG", quality=90, optimize=False)
        buffer.seek(0)
        recompressed = Image.open(buffer).convert("RGB")
        a = np.asarray(working, dtype=np.int16)
        b = np.asarray(recompressed, dtype=np.int16)
        difference = np.abs(a - b)
        result["jpeg_recompression"] = {
            "reference_quality": 90,
            "mean_absolute_channel_difference": round(float(np.mean(difference)), 5),
            "p95_absolute_channel_difference": round(float(np.percentile(difference, 95)), 5),
            "fraction_channel_differences_above_20": round(float(np.mean(difference > 20)), 6),
            "method": "bounded image re-saved as JPEG q90 and compared pixel-wise",
            "warning": "ELA-style residuals vary with original quality, resizing, texture and editing; no manipulation threshold is asserted.",
        }
    else:
        result["jpeg_recompression"] = {"status": "not_applicable", "reason": "Source is not JPEG; no equivalent manipulation score is inferred."}

    # InVID / WeVerify Style: Multi-channel Error Level Analysis (ELA) at q95
    try:
        ela_buffer = io.BytesIO()
        working.save(ela_buffer, format="JPEG", quality=95, optimize=False)
        ela_buffer.seek(0)
        ela_recompressed = Image.open(ela_buffer).convert("RGB")
        ela_orig = np.asarray(working, dtype=np.float32)
        ela_recomp = np.asarray(ela_recompressed, dtype=np.float32)
        ela_diff = np.abs(ela_orig - ela_recomp)
        result["ela_analysis"] = {
            "reference_quality": 95,
            "mean_error": round(float(np.mean(ela_diff)), 5),
            "max_error": round(float(np.max(ela_diff)), 5),
            "standard_deviation": round(float(np.std(ela_diff)), 5),
            "high_error_pixel_ratio": round(float(np.mean(ela_diff > 15.0)), 6),
            "method": "InVID-style Error Level Analysis (ELA) comparing source against in-memory q95 JPEG recompression",
            "forensic_cues": "Uniform error surfaces correspond to untouched captures; spliced, composited or selectively modified regions present anomalous error variance.",
        }
    except Exception as exc:
        result["ela_analysis"] = {"status": "error", "reason": str(exc)}

    # Sentinel / DeepMedia Style: 2D FFT Radial Frequency Energy Spectrum Analysis
    try:
        f = np.fft.fft2(pixels)
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)
        h, w = magnitude.shape
        cy, cx = h // 2, w // 2
        y, x = np.ogrid[:h, :w]
        r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        max_r = min(cx, cy)
        low_freq_mask = r <= (max_r * 0.3)
        high_freq_mask = (r > (max_r * 0.7)) & (r <= max_r)

        low_energy = float(np.sum(magnitude[low_freq_mask]))
        high_energy = float(np.sum(magnitude[high_freq_mask]))
        total_energy = float(np.sum(magnitude)) + 1e-9

        high_freq_ratio = round(high_energy / total_energy, 6)
        low_freq_ratio = round(low_energy / total_energy, 6)
        result["fft_spectral_analysis"] = {
            "high_frequency_energy_ratio": high_freq_ratio,
            "low_frequency_energy_ratio": low_freq_ratio,
            "spectral_energy_balance": round(high_freq_ratio / (low_freq_ratio + 1e-9), 6),
            "method": "2D Fast Fourier Transform (FFT) radial power distribution for high-frequency synthetic periodicity cues",
            "interpretation_note": "Diffusion and GAN upsampling layers typically exhibit high-frequency spectral spikes or checkerboard anomalies.",
        }
    except Exception as exc:
        result["fft_spectral_analysis"] = {"status": "error", "reason": str(exc)}

    return result


def configured_model(image: Image.Image) -> dict:
    model_id = settings.deepfake_model_id
    if not model_id:
        return {
            "status": "not_configured", "model_id": None, "synthetic_score": None,
            "detail": "No synthetic-media model is configured; deterministic observations above are not converted into a fake confidence score.",
        }
    revision = settings.deepfake_model_revision
    try:
        from transformers import pipeline
        key = (model_id, revision)
        if key not in _MODEL_CACHE:
            kwargs = {"model": model_id, "device": -1}
            if revision:
                kwargs["revision"] = revision
            _MODEL_CACHE[key] = pipeline("image-classification", **kwargs)
        classifier = _MODEL_CACHE[key]
        output = classifier(image.convert("RGB"), top_k=None)
        rows = output if isinstance(output, list) else [output]
        if rows and isinstance(rows[0], list):
            rows = rows[0]
        labels = [{"label": str(row.get("label")), "score": float(row.get("score", 0.0))}
                  for row in rows if isinstance(row, dict) and row.get("label") is not None]
        positive, negative = 0.0, 0.0
        for row in labels:
            label = row["label"].casefold().replace("_", " ").replace("-", " ")
            is_negative = any(term in label for term in ("real", "human", "authentic", "genuine", "not fake", "not ai"))
            is_positive = any(term in label for term in ("fake", "synthetic", "generated", "deepfake", "artificial"))
            if is_negative:
                negative += row["score"]
            elif is_positive:
                positive += row["score"]
        score = positive / (positive + negative) if positive + negative > 0 else None
        return {
            "status": "successful", "model_id": model_id, "model_revision": revision,
            "model_card_url": f"https://huggingface.co/{model_id}",
            "labels": labels,
            "synthetic_score": round(score, 6) if score is not None else None,
            "score_semantics": "Raw model-label aggregation, not a calibrated deepfake probability or operational confidence interval.",
            "limitations": [
                "Validate this exact model and threshold on representative local data, unseen generators and social-media compression before operational use.",
                "A low score does not prove authenticity; a high score does not prove manipulation.",
            ],
        }
    except Exception as exc:
        return {
            "status": "unavailable", "model_id": model_id, "synthetic_score": None,
            "detail": f"Configured model could not run: {type(exc).__name__}. Raw error details remain server-side; no fallback score was invented.",
        }


def analyze_asset(db: Session, case_id: str, media: MediaAsset, analysis_run: AnalysisRun) -> MediaForensics:
    raw = storage.get_object(media.object_key)
    image = Image.open(io.BytesIO(raw))
    image.load()
    metadata, declarations = metadata_observations(image, raw)
    indicators = {
        "integrity": {"sha256": media.sha256, "bytes": media.byte_length, "phash": media.phash},
        "metadata": metadata,
        "metadata_declarations": declarations,
        "pixels": pixel_indicators(image, media.mime_type),
    }
    model_result = configured_model(image)
    limitations = [
        "These are screening indicators, not a forensic certificate or standalone deepfake determination.",
        "Metadata can be absent, edited or copied; no AI-tool metadata does not imply human origin.",
        "C2PA/provenance and content-based detection answer different questions; a byte marker here is not signature validation.",
        "Compression, resizing, cropping, texture and camera pipelines can alter residual measurements.",
    ]
    record = MediaForensics(
        case_id=case_id, media_asset_id=media.id, analysis_run_id=analysis_run.id,
        status="screened" if model_result["status"] == "successful" else f"screened_model_{model_result['status']}",
        indicators=json.dumps(indicators, ensure_ascii=False),
        model_result=json.dumps(model_result, ensure_ascii=False),
        limitations=json.dumps(limitations + model_result.get("limitations", []), ensure_ascii=False),
    )
    db.add(record)
    db.flush()
    return record


def analyze_video_keyframes(video_bytes: bytes, max_frames: int = 15, sample_fps: float = 1.0) -> dict:
    """InVID / WeVerify style Video Keyframe Extraction and Temporal Forensic Analysis."""
    import os
    import shutil
    import subprocess
    import tempfile

    from ..config import get_settings

    settings = get_settings()
    ffmpeg_bin = settings.ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"

    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "input_video.mp4")
        with open(input_file, "wb") as f:
            f.write(video_bytes)

        frame_pattern = os.path.join(tmpdir, "frame_%04d.jpg")
        cmd = [
            ffmpeg_bin, "-y", "-i", input_file,
            "-vf", f"fps={sample_fps}",
            "-vframes", str(max_frames),
            "-q:v", "2",
            frame_pattern,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=20)
        except Exception as exc:
            return {"status": "ffmpeg_execution_failed", "error": str(exc), "timeline": []}

        frame_files = sorted([os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.startswith("frame_") and f.endswith(".jpg")])
        if not frame_files:
            return {"status": "no_frames_extracted", "timeline": []}

        timeline = []
        ela_errors = []
        fft_ratios = []

        for idx, fpath in enumerate(frame_files):
            try:
                frame_img = Image.open(fpath)
                frame_img.load()
                pix = pixel_indicators(frame_img, mime="image/jpeg")
                ela_mean = pix.get("ela_analysis", {}).get("mean_error", 0.0)
                fft_ratio = pix.get("fft_spectral_analysis", {}).get("high_frequency_energy_ratio", 0.0)
                ela_errors.append(ela_mean)
                fft_ratios.append(fft_ratio)
                timestamp_sec = round(idx / sample_fps, 2)
                timeline.append({
                    "frame_index": idx + 1,
                    "timestamp_sec": timestamp_sec,
                    "ela_mean_error": ela_mean,
                    "fft_high_freq_ratio": fft_ratio,
                    "dimensions": [frame_img.width, frame_img.height],
                })
            except Exception:
                continue

        mean_ela = float(np.mean(ela_errors)) if ela_errors else 0.0
        std_ela = float(np.std(ela_errors)) if ela_errors else 0.0

        anomalous_frames = []
        for item in timeline:
            if std_ela > 0.01 and item["ela_mean_error"] > (mean_ela + 1.8 * std_ela):
                item["tampering_flag"] = "elevated_recompression_divergence"
                anomalous_frames.append(item["timestamp_sec"])
            else:
                item["tampering_flag"] = "normal"

        return {
            "status": "completed",
            "total_frames_extracted": len(timeline),
            "sample_fps": sample_fps,
            "mean_video_ela_error": round(mean_ela, 4),
            "std_video_ela_error": round(std_ela, 4),
            "flagged_timestamps_sec": anomalous_frames,
            "timeline": timeline,
            "methodology": "InVID-style keyframe decomposition with temporal ELA and 2D FFT spectral variance tracking",
            "interpretation": "Spikes in ELA error or FFT energy at specific timestamps highlight composite edits, deepfake face-swaps, or spliced scene transitions."
        }

