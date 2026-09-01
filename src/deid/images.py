"""Image-level de-identification helpers for scanned pages.

- wipe_page_render: wipes PHI regions in a full-page RENDER and replaces the
  page content with that raster (background-matching fill, not white boxes).
- detect_faces: Haar-cascade frontal-face detection on the rendered page
  (identifier 17 - full-face photographs).
- signature_regions: heuristic regions around "signature"/"signed" labels on
  scans, where handwritten ink (identifier 16-adjacent) typically sits.
"""

from __future__ import annotations

import re

import cv2
import numpy as np
import pymupdf


def wipe_page_render(page, rects, *, dpi: int = 200, pad: int = 3) -> bool:
    """Wipe the given page-coordinate rects in a full-page render, then
    replace the page's ENTIRE content with that raster.

    Rendering first means it does not matter where the PHI ink lives -
    embedded scan image, vector line art, or a font with no usable encoding:
    everything is pixels by the time the fill is applied, and replacing the
    content guarantees no original text/image object survives in the file.
    (The previous approach edited the page's largest embedded image in place;
    on vector lab reports whose only image is a logo, it hit the logo and the
    real text survived underneath the surrogate overlays.)

    Fill is the median color of a ring around each rect (paper background):
    on text documents that looks cleaner than diffusion inpainting, which
    smears ink into visible streaks."""
    if not rects:
        return False
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    bgr = (cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2BGR) if pix.n >= 3
           else cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR))
    h, w = bgr.shape[:2]
    if page.rect.width <= 0 or page.rect.height <= 0:
        return False
    sx, sy = w / page.rect.width, h / page.rect.height
    out = bgr.copy()
    filled = False
    for r in rects:
        x0 = max(int((r.x0 - page.rect.x0) * sx) - pad, 0)
        y0 = max(int((r.y0 - page.rect.y0) * sy) - pad, 0)
        x1 = min(int((r.x1 - page.rect.x0) * sx) + pad, w - 1)
        y1 = min(int((r.y1 - page.rect.y0) * sy) + pad, h - 1)
        if x1 <= x0 or y1 <= y0:
            continue
        ring = 14
        rx0, ry0 = max(x0 - ring, 0), max(y0 - ring, 0)
        rx1, ry1 = min(x1 + ring, w - 1), min(y1 + ring, h - 1)
        region = bgr[ry0:ry1, rx0:rx1].reshape(-1, 3)
        # paper background = the bright majority of the surrounding pixels
        bright = region[region.mean(axis=1) > max(region.mean() * 0.9, 120)]
        color = (np.median(bright if len(bright) else region, axis=0)
                 .astype(int).tolist())
        cv2.rectangle(out, (x0, y0), (x1, y1), color, -1)
        filled = True
    if not filled:
        return False
    ok, enc = cv2.imencode(".png", out)
    if not ok:
        return False
    page.add_redact_annot(page.rect, fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_REMOVE)
    page.insert_image(page.rect, stream=enc.tobytes())
    return True


def unrecognized_ink_components(page, textpage, *, dpi: int = 120) -> list[pymupdf.Rect]:
    """Regions of ink that OCR could NOT read: handwriting, signatures, logos,
    or degraded print. These are exactly the places where text-based passes
    are blind, so each one goes to the vision classifier."""
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    gray = (cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
            if pix.n >= 3 else img[:, :, 0])
    ink = (gray < 160).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(9, dpi // 8), max(5, dpi // 24)))
    joined = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel)
    n, _labels, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
    scale = page.rect.width / pix.width
    words = ([pymupdf.Rect(w[:4]) for w in page.get_text("words", textpage=textpage)]
             if textpage is not None else [])
    out = []
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if area < (dpi / 8) ** 2 or hh < dpi / 24:      # specks and rules
            continue
        rect = pymupdf.Rect(x * scale, y * scale,
                            (x + ww) * scale, (y + hh) * scale)
        if rect.width > page.rect.width * 0.95 and rect.height < 8:
            continue                                     # page-wide rule lines
        covered = 0.0
        for wr in words:
            ix = min(rect.x1, wr.x1) - max(rect.x0, wr.x0)
            iy = min(rect.y1, wr.y1) - max(rect.y0, wr.y0)
            if ix > 0 and iy > 0:
                covered += ix * iy
        if covered < 0.45 * abs(rect):                   # OCR can't read it
            out.append(rect)
    return out


def flatten_page(page, *, dpi: int = 200) -> None:
    """Render the finished page and replace all its content with that single
    raster: wipes and typed overlays end up sharing one uniform texture, and
    no earlier image object survives in the file."""
    pix = page.get_pixmap(dpi=dpi)
    page.add_redact_annot(page.rect, fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_REMOVE)
    page.insert_image(page.rect, pixmap=pix)


def detect_faces(page) -> list[pymupdf.Rect]:
    """Frontal faces on the rendered page, as page-coordinate rects."""
    pix = page.get_pixmap(dpi=150)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    gray = (cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
            if pix.n >= 3 else img[:, :, 0])
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=8,
                                     minSize=(48, 48))
    scale = page.rect.width / pix.width
    return [pymupdf.Rect(x * scale, y * scale, (x + w) * scale, (y + h) * scale)
            for (x, y, w, h) in faces]


# identifier field labels on forms; a handwritten value after one of these is
# invisible to OCR, so the whole value band gets blanked unless a readable
# value was already located there
LABEL_SEQUENCES = [
    ("patient", "name"), ("name",), ("dob",), ("date", "of", "birth"),
    ("birth", "date"), ("date",), ("address",), ("phone",), ("fax",),
    ("ssn",), ("mrn",), ("member", "id"), ("policy",), ("insured",),
]

# labels whose value bands are ALWAYS wiped on scans and refilled with the
# canonical fake (handwritten name/DOB misreads leave tails and garbage)
CRITICAL_LABELS = {"patient name", "name", "dob", "date of birth", "birth date"}


def labeled_value_regions(page, textpage) -> list[tuple[str, pymupdf.Rect]]:
    """Bands to the right of identifier labels, where form values are written."""
    words = page.get_text("words", textpage=textpage)
    toks = [w[4].strip(":,.").lower() for w in words]
    out = []
    i = 0
    while i < len(toks):
        matched = None
        for seq in sorted(LABEL_SEQUENCES, key=len, reverse=True):
            if tuple(toks[i:i + len(seq)]) == seq:
                matched = seq
                break
        if matched:
            last = words[i + len(matched) - 1]
            x1, y0, y1 = last[2], min(w[1] for w in words[i:i + len(matched)]), last[3]
            band = pymupdf.Rect(x1 + 2, max(page.rect.y0, y0 - 6),
                                min(page.rect.x1, x1 + 240), y1 + 10)
            out.append((" ".join(matched), band))
            i += len(matched)
        else:
            i += 1
    return out


SIGNATURE_WORD_RX = re.compile(r"(?i)^sign(?:ature|ed|:)?[.:]?$")


def signature_regions(page, textpage) -> list[pymupdf.Rect]:
    """Bands adjacent to signature labels on a scanned page, where handwriting
    usually sits: above the label and to its right."""
    regions = []
    for x0, y0, x1, y1, word, *_ in page.get_text("words", textpage=textpage):
        if SIGNATURE_WORD_RX.match(word.strip()):
            regions.append(pymupdf.Rect(
                x0, max(page.rect.y0, y0 - 30),
                min(page.rect.x1, x1 + 240), y1 + 4))
    return regions
