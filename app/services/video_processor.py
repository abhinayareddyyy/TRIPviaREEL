"""Text extraction from screenshots and screen-recordings (OpenCV + Tesseract)."""
from __future__ import annotations

import os
from typing import List, Optional

import cv2
import numpy as np
import pytesseract

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
MAX_FRAMES = 12          # frames sampled per video
MAX_SIDE = 1600          # downscale huge frames before OCR
TESS_CONFIG = "--psm 11"  # sparse text: suits overlay captions on reels
DIFF_PIXEL = 25          # a pixel counts as changed if its gray value moves by more than this
DIFF_FRACTION = 0.001    # skip a frame if fewer than 0.1% of pixels changed since the last kept frame


class MediaError(Exception):
    """The file could not be read as an image or video."""


def kind_of(filename: str) -> Optional[str]:
    ext = os.path.splitext(filename.lower())[1]
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def _prepare(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    scale = 1.0
    if max(h, w) > MAX_SIDE:
        scale = MAX_SIDE / max(h, w)
    elif w < 900:
        scale = 900 / w  # tiny text OCRs poorly; upscale small screenshots
    if scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
    return img


def ocr_array(img: np.ndarray) -> str:
    """OCR one BGR image using two passes: plain gray, and bright-text isolation.

    The second pass helps with white overlay text on busy photos, which is how
    most reels show place names.
    """
    img = _prepare(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    _, white_text = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    texts: List[str] = []
    for variant in (gray, white_text):
        try:
            texts.append(pytesseract.image_to_string(variant, config=TESS_CONFIG))
        except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover
            raise MediaError("Tesseract OCR is not installed or not on PATH") from exc
    return "\n".join(t for t in texts if t.strip())


def ocr_image(path: str) -> str:
    img = cv2.imread(path)
    if img is None:
        raise MediaError("could not read this image file")
    return ocr_array(img)


def extract_frames(path: str, max_frames: int = MAX_FRAMES) -> List[np.ndarray]:
    """Sample frames evenly across the video, skipping near-duplicates."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise MediaError("could not open this video file")
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames: List[np.ndarray] = []
        if total <= 0:  # unknown length: read sequentially, keep every Nth
            raw = []
            while True:
                ok, f = cap.read()
                if not ok:
                    break
                raw.append(f)
            idxs = np.linspace(0, len(raw) - 1, num=min(max_frames, len(raw)), dtype=int) if raw else []
            candidates = [raw[i] for i in idxs]
        else:
            idxs = np.linspace(0, total - 1, num=min(max_frames, total), dtype=int)
            candidates = []
            for i in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
                ok, f = cap.read()
                if ok:
                    candidates.append(f)
        last_small = None
        for f in candidates:
            gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (256, max(1, int(256 * gray.shape[0] / gray.shape[1]))), interpolation=cv2.INTER_AREA)
            # compare the *fraction of changed pixels* (not the mean), so a caption
            # that changes over otherwise similar footage still counts as a new frame
            if last_small is not None and float(np.mean(cv2.absdiff(small, last_small) > DIFF_PIXEL)) < DIFF_FRACTION:
                continue
            frames.append(f)
            last_small = small
        if not frames:
            raise MediaError("no readable frames in this video")
        return frames
    finally:
        cap.release()


def ocr_video(path: str, max_frames: int = MAX_FRAMES) -> str:
    seen, lines = set(), []
    for frame in extract_frames(path, max_frames):
        for line in ocr_array(frame).splitlines():
            key = line.strip().lower()
            if key and key not in seen:
                seen.add(key)
                lines.append(line.strip())
    return "\n".join(lines)


def process_media(path: str, filename: Optional[str] = None) -> str:
    kind = kind_of(filename or path)
    if kind == "image":
        return ocr_image(path)
    if kind == "video":
        return ocr_video(path)
    raise MediaError("unsupported file type")
