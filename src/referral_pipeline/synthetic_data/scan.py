"""Deterministic raster and transmission artifacts for synthetic PDFs.

The profiles model document transport rather than document content.  Every
input is already synthetic before it reaches this module.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
import random

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


@dataclass(frozen=True)
class ScanProfile:
    name: str
    dpi: int
    contrast: float = 1.0
    brightness: float = 1.0
    blur: float = 0.0
    rotation: float = 0.0
    noise_density: float = 0.0
    streaks: int = 0
    jpeg_quality: int = 82
    threshold: int | None = None
    edge_shadow: bool = False


SCAN_PROFILES: dict[str, ScanProfile] = {
    "office_scan": ScanProfile(
        "office_scan", dpi=200, contrast=1.08, blur=0.15, rotation=0.18,
        noise_density=0.00008, jpeg_quality=88,
    ),
    "fax_clean": ScanProfile(
        "fax_clean", dpi=172, contrast=1.23, brightness=1.02, blur=0.28,
        rotation=0.28, noise_density=0.00025, streaks=2, jpeg_quality=68,
    ),
    "fax_noisy": ScanProfile(
        "fax_noisy", dpi=138, contrast=1.42, brightness=1.02, blur=0.48,
        rotation=0.65, noise_density=0.0011, streaks=7, jpeg_quality=46,
        threshold=205, edge_shadow=True,
    ),
    "photocopy": ScanProfile(
        "photocopy", dpi=190, contrast=1.34, brightness=0.98, blur=0.32,
        rotation=0.38, noise_density=0.00055, streaks=4, jpeg_quality=60,
        edge_shadow=True,
    ),
    "low_toner": ScanProfile(
        "low_toner", dpi=155, contrast=0.82, brightness=1.12, blur=0.38,
        rotation=0.48, noise_density=0.00045, streaks=5, jpeg_quality=52,
    ),
}


def scan_profile_names() -> tuple[str, ...]:
    return ("native", *SCAN_PROFILES)


def render_scan_variant(
    source_pdf: str | Path,
    output_pdf: str | Path,
    *,
    profile: str,
    seed: str | int,
) -> Path:
    """Create one deterministic native or image-only PDF variant."""

    source_path = Path(source_pdf)
    output_path = Path(output_pdf)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if profile == "native":
        output_path.write_bytes(source_path.read_bytes())
        return output_path
    if profile == "mixed_fax":
        return _render_raster(source_path, output_path, profile=None, seed=seed)
    try:
        selected = SCAN_PROFILES[profile]
    except KeyError as exc:
        choices = ", ".join((*scan_profile_names(), "mixed_fax"))
        raise ValueError(f"unknown scan profile {profile!r}; choose from {choices}") from exc
    return _render_raster(source_path, output_path, profile=selected, seed=seed)


def _render_raster(
    source_path: Path,
    output_path: Path,
    *,
    profile: ScanProfile | None,
    seed: str | int,
) -> Path:
    rng = random.Random(str(seed))
    source = pdfium.PdfDocument(str(source_path))
    canvas = Canvas(str(output_path), pagesize=letter, pageCompression=1)
    try:
        for page_index, page in enumerate(source):
            base_profile = profile or SCAN_PROFILES[rng.choice(tuple(SCAN_PROFILES))]
            selected = _vary_profile(base_profile, rng)
            image = page.render(scale=selected.dpi / 72).to_pil().convert("L")
            image = _degrade(image, selected, rng, page_index=page_index)
            encoded = BytesIO()
            image.save(
                encoded,
                format="JPEG",
                quality=selected.jpeg_quality,
                optimize=True,
                progressive=False,
            )
            encoded.seek(0)
            canvas.drawImage(ImageReader(encoded), 0, 0, width=letter[0], height=letter[1])
            canvas.showPage()
    finally:
        source.close()
    canvas.save()
    return output_path


def _vary_profile(profile: ScanProfile, rng: random.Random) -> ScanProfile:
    """Continuously perturb a profile so documents do not share one artifact recipe."""

    return replace(
        profile,
        dpi=max(110, int(profile.dpi * rng.uniform(0.88, 1.12))),
        contrast=max(0.65, profile.contrast * rng.uniform(0.90, 1.12)),
        brightness=max(0.72, profile.brightness * rng.uniform(0.94, 1.07)),
        blur=max(0.0, profile.blur + rng.uniform(-0.12, 0.22)),
        rotation=max(0.0, profile.rotation * rng.uniform(0.55, 1.55)),
        noise_density=max(0.0, profile.noise_density * rng.uniform(0.45, 1.9)),
        streaks=max(0, profile.streaks + rng.randint(-2, 3)),
        jpeg_quality=max(30, min(94, profile.jpeg_quality + rng.randint(-10, 8))),
        threshold=(
            None if profile.threshold is None
            else max(170, min(230, profile.threshold + rng.randint(-12, 12)))
        ),
    )


def _degrade(
    image: Image.Image,
    profile: ScanProfile,
    rng: random.Random,
    *,
    page_index: int,
) -> Image.Image:
    image = ImageOps.autocontrast(image, cutoff=(0.2, 0.5))
    image = ImageEnhance.Contrast(image).enhance(profile.contrast)
    image = ImageEnhance.Brightness(image).enhance(profile.brightness)
    if profile.blur:
        image = image.filter(ImageFilter.GaussianBlur(profile.blur))
    if profile.threshold is not None:
        threshold = profile.threshold + rng.randint(-9, 9)
        image = image.point(lambda value: 255 if value > threshold else min(225, value))

    angle = rng.uniform(-profile.rotation, profile.rotation)
    if abs(angle) > 0.02:
        image = image.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=255)

    draw = ImageDraw.Draw(image)
    width, height = image.size
    specks = int(width * height * profile.noise_density)
    for _ in range(specks):
        x = rng.randrange(width)
        y = rng.randrange(height)
        shade = rng.choice((0, 18, 45, 190, 220, 245))
        radius = 0 if rng.random() < 0.84 else rng.choice((1, 1, 2))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=shade)

    for _ in range(profile.streaks):
        y = rng.randrange(8, max(9, height - 8))
        shade = rng.choice((175, 195, 215, 232))
        draw.line((0, y, width, y + rng.choice((-1, 0, 1))), fill=shade, width=rng.choice((1, 1, 2)))

    if profile.edge_shadow:
        side = "left" if (page_index + rng.randrange(2)) % 2 == 0 else "right"
        shadow_width = max(5, int(width * rng.uniform(0.008, 0.022)))
        for offset in range(shadow_width):
            shade = int(140 + 110 * (offset / shadow_width))
            x = offset if side == "left" else width - 1 - offset
            draw.line((x, 0, x, height), fill=shade)

    return image
