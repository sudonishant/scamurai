"""Staged image pipeline (master prompt section 9-11).

Stage 1 SHA-256 exact file identity -> Stage 2 pHash candidate retrieval ->
Stage 3 local pixel/region verification -> Stage 4 semantic (only when an
embedding provider exists) -> Stage 5 external reverse search (adapter, off
by default). Same file size is never a match signal on its own.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import ExifTags, Image
from PIL.ExifTags import GPSTAGS

from ..config import get_settings
from . import hashing

settings = get_settings()

MATCH_TYPES = (
    "exact_file", "likely_same_visual_source", "partial_region_match",
    "related_scene", "no_match", "uncertain",
)


@dataclass
class ImageInfo:
    width: int
    height: int
    mime: str
    phash: str
    exif_gps: dict | None


def _gps_to_decimal(values, ref: str) -> float:
    d, m, s = values
    decimal = float(d) + float(m) / 60 + float(s) / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def extract_exif_gps(image: Image.Image) -> dict | None:
    """Return raw GPS fields. Metadata-reported only — editable, not proof."""
    try:
        exif = image.getexif()
    except Exception:
        return None
    gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo) if hasattr(ExifTags, "IFD") else {}
    if not gps_ifd:
        return None
    gps = {GPSTAGS.get(k, str(k)): v for k, v in gps_ifd.items()}
    result: dict = {"raw_fields": {k: str(v) for k, v in gps.items()}}
    try:
        lat = _gps_to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
        lon = _gps_to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])
        result["latitude"] = lat
        result["longitude"] = lon
        result["role"] = "camera_position_reported_by_file"
    except (KeyError, TypeError, ValueError):
        pass
    return result or None


def inspect_image(data: bytes, mime: str) -> ImageInfo:
    image = Image.open(io.BytesIO(data))
    image.load()
    if image.width * image.height > settings.max_image_pixels:
        raise ValueError("Image exceeds pixel safety limit")
    return ImageInfo(
        width=image.width,
        height=image.height,
        mime=mime,
        phash=hashing.phash(image),
        exif_gps=extract_exif_gps(image),
    )


def compare_pair(image_a: Image.Image, image_b: Image.Image,
                 phash_a: str, phash_b: str, exact: bool) -> dict:
    """Return an honest match category with method details and limitations."""
    if exact:
        return {
            "match_type": "exact_file",
            "method": "sha256+byte_length",
            "limitation": "Byte identity only; does not establish first uploader or caption truth.",
        }
    distance = hashing.hamming_distance(phash_a, phash_b)
    agreement = hashing.bit_agreement(phash_a, phash_b)
    correlation = hashing.normalized_pixel_correlation(image_a, image_b)
    threshold = settings.phash_distance_threshold
    # Stage 3: sliding-window local verification for crops/screenshots.
    region_corr, region_meta = hashing.best_region_correlation(image_a, image_b)
    result = {
        "phash_distance": distance,
        "phash_threshold": threshold,
        "bit_agreement": round(agreement, 4),
        "pixel_correlation": round(correlation, 4),
        "best_region_correlation": round(region_corr, 4),
        "region_window": region_meta,
        "method": "phash-v1(dct64)+grayscale-correlation+sliding-window",
    }
    if distance <= threshold and correlation >= settings.pixel_correlation_threshold:
        result["match_type"] = "likely_same_visual_source"
        result["limitation"] = "Shared visual content, not shared account ownership."
    elif region_corr >= settings.pixel_correlation_threshold:
        result["match_type"] = "partial_region_match"
        result["limitation"] = "A region appears shared; verify with the overlay view."
    elif distance <= threshold * 3:
        result["match_type"] = "related_scene"
        result["limitation"] = "Related-looking scene; semantic closeness is not copying."
    else:
        result["match_type"] = "no_match"
        result["limitation"] = "No signal above validated thresholds."
    return result


def ocr_available() -> bool:
    if not settings.ocr_provider:
        return False
    import importlib.util
    import shutil
    return importlib.util.find_spec("pytesseract") is not None and shutil.which("tesseract") is not None


def visual_clue_observations(data: bytes) -> list[str]:
    """Deterministic, conservative observations used when no vision LLM exists.

    Interpretations (e.g. 'campus cultural event') are produced only by a
    configured model or a human; this function never invents place names.
    """
    image = Image.open(io.BytesIO(data))
    observations = [f"image dimensions {image.width}x{image.height}", f"mode {image.mode}"]
    exif_gps = extract_exif_gps(image)
    if exif_gps:
        observations.append("file contains GPS metadata (metadata-reported, editable)")
    else:
        observations.append("no usable GPS metadata in file (not 'hidden', simply absent)")
    return observations
