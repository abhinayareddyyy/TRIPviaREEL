import pytest


def names(result):
    return [c["name"] for c in result["candidates"]]


def test_exact_names_in_caption(extractor):
    r = extractor.extract("Hyderabad in a day! Charminar, Golconda Fort and Paradise Biryani")
    assert set(names(r)) == {"Charminar", "Golconda Fort", "Paradise Biryani"}
    assert all(c["match"] == "exact" and c["confidence"] == 1.0 for c in r["candidates"])


def test_alias_matches_canonical_place(extractor):
    r = extractor.extract("We loved the Palace of Winds")
    assert names(r) == ["Hawa Mahal"]


def test_hashtags_camel_and_lowercase(extractor):
    r = extractor.extract("#HawaMahal #charminar #goldenhour")
    assert set(names(r)) == {"Hawa Mahal", "Charminar"}
    assert {c["match"] for c in r["candidates"]} == {"hashtag"}


def test_hashtag_counted_once(extractor):
    r = extractor.extract("#charminar")
    assert r["candidates"][0]["mentions"] == 1


def test_fuzzy_match_for_ocr_errors(extractor):
    r = extractor.extract("hawa maha1\nQutub Minor")
    assert set(names(r)) == {"Hawa Mahal", "Qutub Minar"}
    assert all(c["match"] == "fuzzy" and 0.85 <= c["confidence"] < 1 for c in r["candidates"])


def test_mentions_are_counted(extractor):
    r = extractor.extract("Charminar at dawn. Charminar at night. Charminar again!")
    assert r["candidates"][0]["mentions"] == 3


def test_duplicate_name_without_city_is_ambiguous(extractor):
    r = extractor.extract("Birla Mandir is stunning")
    assert sorted(c["city"] for c in r["candidates"]) == ["Hyderabad", "Jaipur"]
    assert all(c["ambiguous"] for c in r["candidates"])


@pytest.mark.parametrize("city", ["Hyderabad", "Jaipur"])
def test_duplicate_name_resolved_by_city(extractor, city):
    r = extractor.extract(f"Birla Mandir in {city} is stunning")
    assert [c["city"] for c in r["candidates"]] == [city]
    assert not r["candidates"][0]["ambiguous"]


def test_duplicate_name_resolved_by_other_places(extractor):
    r = extractor.extract("Amber Fort, Hawa Mahal and Birla Mandir")
    birla = [c for c in r["candidates"] if c["name"] == "Birla Mandir"]
    assert len(birla) == 1 and birla[0]["city"] == "Jaipur"


@pytest.mark.parametrize("text", [
    "", "   ", "nothing to see here", "red for sale, the fort was fun",
    "the golden fort was kind of old", "my hotel was paradise", "12345 !!! ###",
])
def test_no_false_positives(extractor, text):
    assert extractor.extract(text)["candidates"] == []


def test_unknown_pin_is_reported_unresolved(extractor):
    r = extractor.extract("📍 Secret Cafe Banjara Hills\nAlso Charminar")
    assert names(r) == ["Charminar"]
    assert r["unresolved"] == ["Secret Cafe Banjara Hills"]


def test_known_pin_not_reported_unresolved(extractor):
    r = extractor.extract("📍 Charminar")
    assert names(r) == ["Charminar"] and r["unresolved"] == []


def test_candidates_have_real_coordinates(extractor):
    for c in extractor.extract("Charminar Hawa Mahal Baga Beach India Gate")["candidates"]:
        assert -90 < c["lat"] < 90 and -180 < c["lon"] < 180


def test_dataset_integrity(gazetteer):
    ids = [p.id for p in gazetteer.all()]
    assert len(ids) == len(set(ids)) >= 40
    for p in gazetteer.all():
        assert 6 < p.lat < 36 and 68 < p.lon < 98, p.id  # inside India
        assert p.spend >= 0 and 0 < p.visit_hours <= 8
        assert p.category in {"attraction", "food"}
        assert p.tags and set(p.tags) <= set(gazetteer.valid_tags), p.id
        if p.category == "food":
            assert "food" in p.tags, p.id
