"""Generate clearly-labeled synthetic fixture images (no real people/events).

Outputs:
  scene_a.png                 original scene (shapes + gradient)
  scene_a_recompressed.jpg    recompressed copy -> likely same visual source
  scene_a_crop.png            center crop -> partial region match
  scene_b_same_size.jpg       different scene padded to identical byte length (control)
  scene_unrelated.png         unrelated composition
  image_with_gps.jpg          valid EXIF GPS metadata (metadata-reported path)
  cultural_hall.png           generic banner scene that must NOT resolve to a named university
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ExifTags, ImageDraw
from PIL.TiffImagePlugin import IFDRational

OUT = Path(__file__).parent / "images"
OUT.mkdir(parents=True, exist_ok=True)


def gradient(base: tuple[int, int, int], size=(256, 256), accent=(0, 0, 0),
             variant: str = "a") -> Image.Image:
    img = Image.new("RGB", size, base)
    draw = ImageDraw.Draw(img)
    for x in range(size[0]):
        shade = tuple(min(255, int(c * (0.4 + 0.6 * x / size[0]))) for c in base)
        draw.line([(x, 0), (x, size[1])], fill=shade)
    if variant == "a":
        # Layout A: left rectangle, top-right ellipse, low horizontal line.
        draw.rectangle([40, 60, 150, 180], outline=accent, width=6)
        draw.ellipse([160, 40, 230, 110], outline=accent, width=5)
        draw.line([0, 220, 256, 220], fill=accent, width=4)
    else:
        # Layout B: deliberately different geometry — triangle, vertical bars,
        # a filled disk and a diagonal, so grayscale structure hashes diverge.
        draw.polygon([(30, 230), (120, 40), (210, 230)], outline=accent, width=6)
        for x in (180, 205, 230):
            draw.line([(x, 120), (x, 250)], fill=accent, width=4)
        draw.ellipse([20, 20, 70, 70], fill=accent)
        draw.line([(90, 240), (250, 130)], fill=accent, width=5)
    return img


def main() -> None:
    scene_a = gradient((30, 90, 160), accent=(255, 220, 120))
    scene_a.save(OUT / "scene_a.png")
    # Identical bytes under another name — exact-file match, not a new visual source.
    (OUT / "scene_a_renamed.png").write_bytes((OUT / "scene_a.png").read_bytes())
    scene_a.save(OUT / "scene_a_recompressed.jpg", quality=72)
    scene_a.crop((48, 48, 208, 208)).save(OUT / "scene_a_crop.png")

    scene_b = gradient((150, 50, 60), accent=(220, 220, 220), variant="b")
    scene_b.save(OUT / "scene_b_same_size.jpg", quality=72)
    # Equalize byte length by padding AFTER JPEG EOI — decoders ignore trailing bytes.
    a_bytes = (OUT / "scene_a_recompressed.jpg").read_bytes()
    b_path = OUT / "scene_b_same_size.jpg"
    b_bytes = b_path.read_bytes()
    if len(b_bytes) < len(a_bytes):
        b_path.write_bytes(b_bytes + b"\x00" * (len(a_bytes) - len(b_bytes)))
    elif len(a_bytes) < len(b_bytes):
        (OUT / "scene_a_recompressed.jpg").write_bytes(
            a_bytes + b"\x00" * (len(b_bytes) - len(a_bytes)))

    gradient((20, 120, 70), accent=(10, 10, 10)).save(OUT / "scene_unrelated.png")

    gps_img = gradient((90, 60, 140))
    exif = gps_img.getexif()
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    # 24.7959 N, 85.0006 E (synthetic coordinate, written as file metadata only)
    gps[1] = "N"
    gps[2] = (IFDRational(24, 1), IFDRational(47, 1), IFDRational(4524, 100))
    gps[3] = "E"
    gps[4] = (IFDRational(85, 1), IFDRational(0, 1), IFDRational(216, 100))
    gps_img.save(OUT / "image_with_gps.jpg", exif=exif, quality=80)

    hall = Image.new("RGB", (320, 200), (245, 240, 225))
    d = ImageDraw.Draw(hall)
    d.rectangle([20, 90, 300, 190], fill=(225, 220, 205), outline=(120, 120, 120), width=3)
    for x in range(40, 300, 45):  # repeated windows — generic campus-like background
        d.rectangle([x, 110, x + 22, 150], fill=(180, 205, 225), outline=(100, 100, 100))
    d.rectangle([110, 30, 210, 70], fill=(80, 80, 120), outline=(40, 40, 60), width=2)
    d.text((126, 44), "CULTURAL CLUB", fill=(255, 255, 255))
    hall.save(OUT / "cultural_hall.png")

    for path in sorted(OUT.iterdir()):
        print(path.name, os.path.getsize(path))


if __name__ == "__main__":
    main()
