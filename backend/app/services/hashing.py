"""Deterministic image fingerprints.

* SHA-256 — cryptographic byte fingerprint for exact-file identity only.
* pHash  — 64-bit DCT perceptual hash (pure numpy, no native deps) for
  candidate retrieval after resize/recompression. It is a similarity
  representation, never a probability that two photos depict the same event.

Thresholds are configurable (PS03_PHASH_DISTANCE_THRESHOLD) and must be
validated on representative fixtures rather than treated as universal truth.
"""
from __future__ import annotations

import numpy as np
from PIL import Image


def sha256_file(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _dct_2d(matrix: np.ndarray) -> np.ndarray:
    """Orthonormal DCT-II via explicit basis matrices (32x32 — cheap)."""
    n = matrix.shape[0]
    k = np.arange(n)
    basis = np.cos(np.pi * (2 * k[:, None] + 1) * k[None, :] / (2 * n))
    basis *= np.sqrt(2 / n)
    basis[0, :] = 1 / np.sqrt(n)
    return basis @ matrix @ basis.T


def phash(image: Image.Image, hash_size: int = 8, highfreq: int = 4) -> str:
    """Return a 64-bit perceptual hash as a 16-char hex string."""
    img = image.convert("L").resize((hash_size * highfreq, hash_size * highfreq),
                                    Image.Resampling.LANCZOS)
    arr = np.asarray(img, dtype=np.float64)
    dct = _dct_2d(arr)
    low = dct[:hash_size, :hash_size]
    # Median excludes the DC term, matching the standard pHash convention.
    median = np.median(low[1:])
    bits = (low > median).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:0{hash_size * hash_size // 4}x}"


def hamming_distance(hash_a: str, hash_b: str) -> int:
    return (int(hash_a, 16) ^ int(hash_b, 16)).bit_count()


def bit_agreement(hash_a: str, hash_b: str) -> float:
    """Bit agreement in this representation — explicitly NOT a probability."""
    return 1 - hamming_distance(hash_a, hash_b) / (len(hash_a) * 4)


def normalized_pixel_correlation(image_a: Image.Image, image_b: Image.Image, size: int = 32) -> float:
    """Local verification step: grayscale correlation on a common small grid."""
    a = np.asarray(image_a.convert("L").resize((size, size)), dtype=np.float64).flatten()
    b = np.asarray(image_b.convert("L").resize((size, size)), dtype=np.float64).flatten()
    a_c = a - a.mean()
    b_c = b - b.mean()
    denom = np.linalg.norm(a_c) * np.linalg.norm(b_c)
    if denom == 0:
        return 0.0
    return float(np.dot(a_c, b_c) / denom)


def best_region_correlation(image_a: Image.Image, image_b: Image.Image,
                            patch: int = 24, strides: int = 5) -> tuple[float, dict]:
    """Sliding-window local verification for crops/screenshots.

    The smaller image is matched against windows of the larger one at several
    scales. Returns (best correlation, window metadata). A high value means a
    *region* of one image matches the other — region match, not whole-file
    identity. Bounded grid keeps this cheap for the authorized corpus.
    """
    big = image_a if image_a.width * image_a.height >= image_b.width * image_b.height else image_b
    small = image_b if big is image_a else image_a
    big_g = np.asarray(big.convert("L"), dtype=np.float64)
    best, best_meta = 0.0, {}
    # Compare at scales where the small image occupies 45%..100% of the large one.
    for scale in (0.45, 0.6, 0.75, 0.9, 1.0):
        win_w = max(8, int(big.width * scale))
        win_h = max(8, int(big.height * scale))
        if win_w > big.width or win_h > big.height:
            continue
        xs = np.linspace(0, big.width - win_w, strides).astype(int)
        ys = np.linspace(0, big.height - win_h, strides).astype(int)
        small_grid = np.asarray(small.convert("L").resize((patch, patch)), dtype=np.float64)
        small_c = (small_grid - small_grid.mean()).flatten()
        small_norm = np.linalg.norm(small_c)
        if small_norm == 0:
            continue
        for x in xs:
            for y in ys:
                window = big_g[y:y + win_h, x:x + win_w]
                if window.size == 0:
                    continue
                window_img = Image.fromarray(window).resize((patch, patch))
                w_arr = np.asarray(window_img, dtype=np.float64)
                w_c = (w_arr - w_arr.mean()).flatten()
                w_norm = np.linalg.norm(w_c)
                if w_norm == 0:
                    continue
                corr = float(np.dot(small_c, w_c) / (small_norm * w_norm))
                if corr > best:
                    best, best_meta = corr, {"scale": scale, "offset": [int(x), int(y)],
                                             "window": [win_w, win_h]}
    return best, best_meta
