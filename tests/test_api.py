import io

import pytest

from app.services import reel_fetcher
from tests.conftest import make_screenshot, make_video


def post_analyze(client, **form):
    return client.post("/api/analyze", data=form, content_type="multipart/form-data")


def upload(client, path, name, **form):
    with open(path, "rb") as fh:
        data = dict(form, files=(io.BytesIO(fh.read()), name))
    return client.post("/api/analyze", data=data, content_type="multipart/form-data")


# ------------------------------------------------------------------ pages
def test_index_page_served(client):
    r = client.get("/")
    assert r.status_code == 200 and b"TripViaReel" in r.data
    assert client.get("/static/vendor/leaflet.js").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_unknown_route_is_json_404(client):
    r = client.get("/nope")
    assert r.status_code == 404 and "error" in r.get_json()


def test_places_catalog(client):
    j = client.get("/api/places").get_json()
    assert len(j["places"]) >= 40 and "food" in j["interests"]


# ------------------------------------------------------------------ analyze
def test_analyze_caption(client):
    j = post_analyze(client, caption="Jaipur trip: Hawa Mahal, Amber Fort & Johari Bazaar").get_json()
    assert {c["name"] for c in j["candidates"]} == {"Hawa Mahal", "Amber Fort", "Johari Bazaar"}
    assert j["sources"]["caption"] and not j["needs_media"]


def test_analyze_requires_some_input(client):
    r = post_analyze(client)
    assert r.status_code == 400 and "error" in r.get_json()


def test_analyze_image_upload(client, tmp_path):
    img = make_screenshot(tmp_path / "s.png", ["Hawa Mahal", "Amber Fort"])
    r = upload(client, img, "reel_screenshot.png")
    j = r.get_json()
    assert r.status_code == 200
    assert {"Hawa Mahal", "Amber Fort"} <= {c["name"] for c in j["candidates"]}
    assert j["sources"]["files"][0]["kind"] == "image" and j["sources"]["files"][0]["ok"]
    assert "extracted_text" in j


def test_analyze_video_upload(client, tmp_path):
    vid = make_video(tmp_path / "v.mp4", ["Charminar", "Chowmahalla Palace"])
    j = upload(client, vid, "reel.mp4").get_json()
    assert {"Charminar", "Chowmahalla Palace"} <= {c["name"] for c in j["candidates"]}
    assert j["sources"]["files"][0]["kind"] == "video"


def test_analyze_combines_caption_and_image(client, tmp_path):
    img = make_screenshot(tmp_path / "s.png", ["Charminar"])
    j = upload(client, img, "s.png", caption="then Baga Beach").get_json()
    assert {"Charminar", "Baga Beach"} <= {c["name"] for c in j["candidates"]}


def test_rejects_unsupported_file_type(client, tmp_path):
    p = tmp_path / "x.exe"
    p.write_bytes(b"MZ")
    r = upload(client, p, "x.exe")
    assert r.status_code == 400 and "not a supported file" in r.get_json()["error"]


def test_corrupt_upload_is_a_warning_not_a_crash(client, tmp_path):
    p = tmp_path / "bad.png"
    p.write_bytes(b"not an image at all")
    r = upload(client, p, "bad.png")
    j = r.get_json()
    assert r.status_code == 200 and j["candidates"] == []
    assert any("Could not read" in w for w in j["warnings"])


def test_path_traversal_filename_is_safe(client, tmp_path):
    img = make_screenshot(tmp_path / "s.png", ["Charminar"])
    r = upload(client, img, "../../etc/passwd.png")
    assert r.status_code == 200 and r.get_json()["candidates"][0]["name"] == "Charminar"


def test_too_many_files(client, tmp_path):
    img = make_screenshot(tmp_path / "s.png", ["Charminar"])
    data = {"files": [(io.BytesIO(open(img, "rb").read()), f"{i}.png") for i in range(6)]}
    r = client.post("/api/analyze", data=data, content_type="multipart/form-data")
    assert r.status_code == 400


def test_upload_size_limit(tmp_path):
    from app.main import create_app
    app = create_app({"TESTING": True, "DATABASE_PATH": str(tmp_path / "t.db"), "MAX_CONTENT_LENGTH": 1000})
    r = app.test_client().post("/api/analyze", data={"files": (io.BytesIO(b"x" * 5000), "big.png")}, content_type="multipart/form-data")
    assert r.status_code == 413 and "too large" in r.get_json()["error"].lower()


def test_caption_length_limit(client):
    assert post_analyze(client, caption="x" * 6000).status_code == 400


def test_no_places_found_warns(client):
    j = post_analyze(client, caption="just vibes and sunsets").get_json()
    assert j["candidates"] == [] and any("No known places" in w for w in j["warnings"])


def test_ambiguous_name_warns(client):
    j = post_analyze(client, caption="Birla Mandir").get_json()
    assert len(j["candidates"]) == 2 and any("more than one city" in w for w in j["warnings"])


# --------------------------------------------------------- instagram links
@pytest.mark.parametrize("url", [
    "https://example.com/reel/abc123/", "https://evil.com/?u=instagram.com/reel/abc/",
    "http://localhost:5000/reel/abc/", "https://www.instagram.com/accounts/login/",
    "file:///etc/passwd", "not a url", "https://instagram.com.evil.com/reel/abc/",
])
def test_rejects_non_instagram_or_non_reel_urls(client, url):
    assert post_analyze(client, reel_url=url).status_code == 400


@pytest.mark.parametrize("url", [
    "https://www.instagram.com/reel/C1abcDEF234/", "instagram.com/reel/C1abc_-d/",
    "https://www.instagram.com/reels/C1abc/", "https://www.instagram.com/p/C1abc/?igsh=xyz",
])
def test_accepts_instagram_reel_urls(url):
    assert reel_fetcher.validate_reel_url(url).startswith("https://www.instagram.com/")


def test_blocked_instagram_link_asks_for_upload(client, monkeypatch):
    monkeypatch.setattr(reel_fetcher, "fetch_caption", lambda url: (None, "blocked"))
    j = post_analyze(client, reel_url="https://www.instagram.com/reel/C1abc/").get_json()
    assert j["needs_media"] is True and j["candidates"] == []
    assert any("Upload a screenshot" in w for w in j["warnings"])


def test_readable_instagram_caption_is_used(client, monkeypatch):
    monkeypatch.setattr(reel_fetcher, "fetch_caption", lambda url: ("Weekend at Charminar and Golconda Fort", "ok"))
    j = post_analyze(client, reel_url="https://www.instagram.com/reel/C1abc/").get_json()
    assert {c["name"] for c in j["candidates"]} == {"Charminar", "Golconda Fort"} and not j["needs_media"]


def test_blocked_link_with_screenshot_still_works(client, monkeypatch, tmp_path):
    monkeypatch.setattr(reel_fetcher, "fetch_caption", lambda url: (None, "blocked"))
    img = make_screenshot(tmp_path / "s.png", ["Hawa Mahal"])
    j = upload(client, img, "s.png", reel_url="https://www.instagram.com/reel/C1abc/").get_json()
    assert not j["needs_media"] and j["candidates"][0]["name"] == "Hawa Mahal"


def test_fetcher_degrades_gracefully_when_network_fails(monkeypatch):
    import urllib.error
    class Boom:
        def open(self, *a, **k): raise urllib.error.URLError("no network")
    monkeypatch.setattr(reel_fetcher.urllib.request, "build_opener", lambda *a: Boom())
    assert reel_fetcher.fetch_caption("https://www.instagram.com/reel/C1abc/") == (None, "blocked")


# ------------------------------------------------------------------ plan
PLAN = {"place_ids": ["hyd-charminar", "hyd-golconda", "hyd-paradise", "hyd-chowmahalla"],
        "budget": 2500, "days": 1, "interests": ["sightseeing", "food", "photography"]}


def test_plan_end_to_end_and_saved(client):
    r = client.post("/api/plan", json=PLAN)
    j = r.get_json()
    assert r.status_code == 200 and j["totals"]["total"] <= 2500 and j["feasible"]
    saved = client.get(f"/api/trips/{j['trip_id']}").get_json()
    assert saved["result"]["totals"] == j["totals"] and saved["request"]["budget"] == 2500


def test_plan_includes_origin_travel_and_saves_origin(client):
    plan = {**PLAN, "origin_place": "hyd-charminar", "place_ids": ["hyd-golconda", "hyd-paradise"]}
    r = client.post("/api/plan", json=plan)
    j = r.get_json()
    assert r.status_code == 200
    assert j["origin"]["id"] == "hyd-charminar"
    assert j["totals"]["km"] > 0
    saved = client.get(f"/api/trips/{j['trip_id']}").get_json()
    assert saved["request"]["origin_place"] == "hyd-charminar"


def test_plan_rejects_unknown_origin(client):
    r = client.post("/api/plan", json={**PLAN, "origin_place": "not-a-place"})
    assert r.status_code == 400 and "origin" in r.get_json()["error"].lower()


def test_full_pipeline_screenshot_to_itinerary(client, tmp_path):
    img = make_screenshot(tmp_path / "s.png", ["Charminar", "Golconda Fort", "Paradise Biryani"])
    cands = upload(client, img, "s.png").get_json()["candidates"]
    ids = [c["id"] for c in cands]
    j = client.post("/api/plan", json={**PLAN, "place_ids": ids, "mentions": {c["id"]: c["mentions"] for c in cands}}).get_json()
    assert j["city"] == "Hyderabad" and len(j["days"][0]["stops"]) >= 2


@pytest.mark.parametrize("patch,fragment", [
    ({"place_ids": []}, "at least one"), ({"place_ids": "hyd-charminar"}, "at least one"),
    ({"place_ids": ["nope"]}, "Unknown place"), ({"place_ids": ["hyd-charminar"] * 21}, "at most 20"),
    ({"budget": -5}, "Budget"), ({"budget": "lots"}, "Budget"), ({"budget": None}, "Budget"),
    ({"budget": float("nan")}, "Budget"), ({"budget": 1e12}, "Budget"),
    ({"days": 0}, "Days"), ({"days": 99}, "Days"), ({"days": "x"}, "Days"),
    ({"interests": "food"}, "Interests"),
])
def test_plan_rejects_invalid_input(client, patch, fragment):
    r = client.post("/api/plan", json={**PLAN, **patch})
    assert r.status_code == 400 and fragment in r.get_json()["error"]


def test_plan_requires_json(client):
    assert client.post("/api/plan", data="x").status_code == 400


def test_plan_budget_too_small_returns_422(client):
    r = client.post("/api/plan", json={**PLAN, "budget": 40})
    assert r.status_code == 422 and "fits" in r.get_json()["error"]


def test_unknown_interests_are_ignored(client):
    r = client.post("/api/plan", json={**PLAN, "interests": ["food", "skydiving"]})
    assert r.status_code == 200


def test_unknown_trip_404(client):
    assert client.get("/api/trips/doesnotexist").status_code == 404
    assert client.get("/api/trips/" + "a" * 80).status_code == 404


def test_xss_text_never_reflected_as_markup(client):
    j = post_analyze(client, caption="<script>alert(1)</script> 📍 <img src=x onerror=alert(1)> Charminar").get_json()
    # the API returns it as plain JSON data; the UI inserts it with textContent
    assert j["candidates"][0]["name"] == "Charminar"
    assert client.get("/").data.count(b"<script>alert") == 0
