import os
import sys

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import create_app  # noqa: E402
from app.services.geocoding import Gazetteer  # noqa: E402
from app.services.location_extractor import LocationExtractor  # noqa: E402


@pytest.fixture(scope="session")
def gazetteer():
    return Gazetteer.load()


@pytest.fixture(scope="session")
def extractor(gazetteer):
    return LocationExtractor(gazetteer)


@pytest.fixture()
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE_PATH": str(tmp_path / "test.db")})
    return app.test_client()


def make_screenshot(path, lines, size=(1080, 1920)):
    """A reel-like screenshot: coloured background with white overlay text."""
    img = Image.new("RGB", size, (70, 110, 150))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=56)
    y = size[1] // 2 - 60 * len(lines)
    for line in lines:
        draw.text((80, y), line, font=font, fill="white")
        y += 110
    img.save(path)
    return path


def make_video(path, lines, size=(540, 960), fps=5, seconds=4):
    """A short mp4 whose second half shows different text than the first."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    assert writer.isOpened(), "OpenCV cannot write mp4 on this machine"
    font = ImageFont.load_default(size=40)
    frames = fps * seconds
    for i in range(frames):
        text = lines[0] if i < frames // 2 else lines[1]
        bg = (70, 110, 150) if i < frames // 2 else (150, 90, 60)
        img = Image.new("RGB", size, bg)
        ImageDraw.Draw(img).text((40, size[1] // 2), text, font=font, fill="white")
        writer.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))
    writer.release()
    return str(path)
