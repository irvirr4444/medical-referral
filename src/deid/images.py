"""Image-level de-identification helpers for scanned pages.

- inpaint_page_rects: removes PHI pixels by inpainting the page's scan image
  (background-matching fill instead of white boxes), via OpenCV TELEA.
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


def _page_scan(page):
    """The page's largest image -> (xref, BGR array, placement rect) or None."""
    best = None
    for im in page.get_images(full=True):
        xref, w, h = im[0], im[2], im[3]
        if best is None or w * h > best[1] * best[2]:
            best = (xref, w, h)
    if best is None:
        return None
    xref = best[0]
    rects = page.get_image_rects(xref)
    if not rects:
        return None
    raw = page.parent.extract_image(xref)
    arr = np.frombuffer(raw["image"], np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    return xref, img, rects[0]


def inpaint_page_rects(page, rects, *, pad: int = 3) -> bool:
    """Inpaint the given page-coordinate rects out of the page's scan image."""
    scan = _page_scan(page)
    if scan is None or not rects:
        return False
    xref, img, bbox = scan
    h, w = img.shape[:2]
    if bbox.width <= 0 or bbox.height <= 0:
        return False
    sx, sy = w / bbox.width, h / bbox.height
    mask = np.zeros((h, w), np.uint8)
    for r in rects:
        x0 = max(int((r.x0 - bbox.x0) * sx) - pad, 0)
        y0 = max(int((r.y0 - bbox.y0) * sy) - pad, 0)
        x1 = min(int((r.x1 - bbox.x0) * sx) + pad, w - 1)
        y1 = min(int((r.y1 - bbox.y0) * sy) + pad, h - 1)
        if x1 > x0 and y1 > y0:
            cv2.rectangle(mask, (x0, y0), (x1, y1), 255, -1)
    if not mask.any():
        return False
    out = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
    ok, enc = cv2.imencode(".png", out)
    if not ok:
        return False
    page.replace_image(xref, stream=enc.tobytes())
    return True


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
