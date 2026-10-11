"""HTTP API: /api/analyze (find places), /api/plan (build itinerary), /api/trips/<id>."""
from __future__ import annotations

import os
import tempfile
from typing import List

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from app.models import db
from app.services import reel_fetcher, video_processor
from app.services.itinerary_generator import InfeasibleTrip, generate_itinerary

bp = Blueprint("api", __name__, url_prefix="/api")

MAX_FILES = 5
MAX_CAPTION_CHARS = 5000


def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


@bp.get("/places")
def places():
    gz = current_app.config["GAZETTEER"]
    return jsonify({
        "interests": gz.valid_tags,
        "places": sorted((p.to_dict() for p in gz.all()), key=lambda p: (p["city"], p["name"])),
    })


@bp.post("/analyze")
def analyze():
    reel_url = (request.form.get("reel_url") or "").strip()
    caption = (request.form.get("caption") or "").strip()
    files = [f for f in request.files.getlist("files") if f and f.filename]

    if not (reel_url or caption or files):
        return _err("Add a reel link, paste its caption, or upload a screenshot / video.")
    if len(caption) > MAX_CAPTION_CHARS:
        return _err(f"Caption is too long (max {MAX_CAPTION_CHARS} characters).")
    if len(files) > MAX_FILES:
        return _err(f"Please upload at most {MAX_FILES} files at once.")

    warnings: List[str] = []
    sources = {"caption": bool(caption), "reel_url": None, "files": []}
    texts: List[str] = [caption] if caption else []

    # 1. reel link (best effort only)
    needs_media = False
    if reel_url:
        try:
            fetched, status = reel_fetcher.fetch_caption(reel_url)
        except reel_fetcher.InvalidReelURL as exc:
            return _err(str(exc))
        sources["reel_url"] = status
        if fetched:
            texts.append(fetched)
        else:
            needs_media = not (caption or files)
            warnings.append(
                "Instagram does not allow automatic access to this reel. "
                "Upload a screenshot or screen-recording of it, or paste its caption."
            )

    # 2. uploads -> OCR
    with tempfile.TemporaryDirectory(prefix="tripviareel_") as tmp:
        for i, f in enumerate(files):
            name = secure_filename(f.filename) or f"upload_{i}"
            kind = video_processor.kind_of(name)
            if kind is None:
                return _err(f"'{f.filename}' is not a supported file. Use PNG/JPG/WEBP images or MP4/MOV/WEBM videos.")
            path = os.path.join(tmp, f"{i}_{name}")
            f.save(path)
            try:
                text = video_processor.process_media(path, name)
            except video_processor.MediaError as exc:
                warnings.append(f"Could not read '{f.filename}': {exc}.")
                sources["files"].append({"name": f.filename, "kind": kind, "chars": 0, "ok": False})
                continue
            sources["files"].append({"name": f.filename, "kind": kind, "chars": len(text.strip()), "ok": True})
            if text.strip():
                texts.append(text)
            else:
                warnings.append(f"No readable text found in '{f.filename}'. Place names must be visible on screen or in the caption.")

    combined = "\n".join(texts)
    result = current_app.config["EXTRACTOR"].extract(combined)
    if not result["candidates"] and not needs_media:
        warnings.append(
            "No known places were detected. Try a clearer screenshot, paste the caption, or add places manually from the list."
        )
    if any(c["ambiguous"] for c in result["candidates"]):
        warnings.append("Some names exist in more than one city (for example Birla Mandir). Tick the one you mean.")

    return jsonify({
        "candidates": result["candidates"],
        "unresolved": result["unresolved"],
        "warnings": warnings,
        "needs_media": needs_media,
        "sources": sources,
        "extracted_text": combined[:2000],
    })


def _num(value, name, lo, hi, integer=False):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number")
    if v != v or v < lo or v > hi:  # NaN or out of range
        raise ValueError(f"{name} must be between {lo:g} and {hi:g}")
    return int(v) if integer else v


@bp.post("/plan")
def plan():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _err("Send a JSON body.")
    gz = current_app.config["GAZETTEER"]

    ids = body.get("place_ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        return _err("Select at least one place.")
    if len(ids) > 20:
        return _err("Please select at most 20 places.")
    unknown = [i for i in ids if gz.get(i) is None]
    if unknown:
        return _err(f"Unknown place id: {unknown[0]}")
    try:
        budget = _num(body.get("budget"), "Budget", 0, 10_000_000)
        days = _num(body.get("days", 1), "Days", 1, 7, integer=True)
    except ValueError as exc:
        return _err(str(exc))
    interests = body.get("interests") or []
    if not isinstance(interests, list) or not all(isinstance(i, str) for i in interests):
        return _err("Interests must be a list of words.")
    interests = [i.lower() for i in interests if i.lower() in gz.valid_tags]
    mentions_raw = body.get("mentions") or {}
    mentions = {k: int(v) for k, v in mentions_raw.items() if isinstance(v, (int, float)) and k in gz.places} if isinstance(mentions_raw, dict) else {}
    start = body.get("origin_place") if isinstance(body.get("origin_place"), str) else None
    if start and gz.get(start) is None:
        return _err(f"Unknown origin place id: {start}")

    try:
        itinerary = generate_itinerary(gz, ids, budget, days, interests, mentions, origin_place=start)
    except InfeasibleTrip as exc:
        return _err(str(exc), 422)

    req = {"place_ids": ids, "origin_place": start, "budget": budget, "days": days, "interests": interests}
    itinerary["trip_id"] = db.save_trip(current_app.config["DATABASE_PATH"], req, itinerary)
    return jsonify(itinerary)


@bp.get("/trips/<trip_id>")
def get_trip(trip_id: str):
    if len(trip_id) > 32:
        return _err("Trip not found.", 404)
    trip = db.load_trip(current_app.config["DATABASE_PATH"], trip_id)
    if not trip:
        return _err("Trip not found.", 404)
    return jsonify(trip)
