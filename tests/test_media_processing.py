import cv2
import numpy as np
import pytest

from app.services import video_processor as vp
from tests.conftest import make_screenshot, make_video


def test_kind_detection():
    assert vp.kind_of("a.PNG") == "image" and vp.kind_of("clip.mov") == "video"
    assert vp.kind_of("notes.pdf") is None and vp.kind_of("noext") is None


def test_ocr_reads_screenshot_and_extractor_finds_places(tmp_path, extractor):
    path = make_screenshot(tmp_path / "shot.png", ["Hawa Mahal", "Golconda Fort", "Paradise Biryani"])
    text = vp.process_media(str(path), "shot.png")
    found = {c["name"] for c in extractor.extract(text)["candidates"]}
    assert {"Hawa Mahal", "Golconda Fort", "Paradise Biryani"} <= found


def test_ocr_handles_small_screenshot_by_upscaling(tmp_path):
    path = make_screenshot(tmp_path / "small.png", ["Charminar"], size=(480, 480))
    assert "charminar" in vp.process_media(str(path), "small.png").lower().replace(" ", "")


def test_static_video_collapses_to_one_frame(tmp_path):
    path = make_video(tmp_path / "static.mp4", ["Charminar", "Charminar"])
    assert len(vp.extract_frames(path, max_frames=12)) == 1


def test_caption_change_over_same_footage_is_kept(tmp_path):
    # both scenes have almost the same brightness; only the text differs
    path = make_video(tmp_path / "v.mp4", ["Charminar", "Chowmahalla Palace"])
    frames = vp.extract_frames(path, max_frames=12)
    assert 2 <= len(frames) < 12


def test_ocr_reads_text_from_both_scenes_of_a_video(tmp_path, extractor):
    path = make_video(tmp_path / "v.mp4", ["Charminar", "Chowmahalla Palace"])
    found = {c["name"] for c in extractor.extract(vp.process_media(path, "v.mp4"))["candidates"]}
    assert {"Charminar", "Chowmahalla Palace"} <= found


def test_corrupt_image_raises_media_error(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"this is not an image")
    with pytest.raises(vp.MediaError):
        vp.process_media(str(bad), "bad.png")


def test_corrupt_video_raises_media_error(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00\x01 not a video")
    with pytest.raises(vp.MediaError):
        vp.process_media(str(bad), "bad.mp4")


def test_blank_image_gives_no_text(tmp_path):
    p = tmp_path / "blank.png"
    cv2.imwrite(str(p), np.full((800, 600, 3), 90, np.uint8))
    assert vp.process_media(str(p), "blank.png").strip() == ""


def test_unsupported_type_rejected(tmp_path):
    with pytest.raises(vp.MediaError):
        vp.process_media(str(tmp_path / "x.pdf"), "x.pdf")
