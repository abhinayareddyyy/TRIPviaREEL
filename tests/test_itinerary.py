import pytest

from app.services import budget_optimizer as bo
from app.services.itinerary_generator import InfeasibleTrip, generate_itinerary, split_into_days

HYD = ["hyd-charminar", "hyd-golconda", "hyd-chowmahalla", "hyd-paradise", "hyd-hussain-sagar", "hyd-salar-jung", "hyd-ramoji"]


def all_stops(it):
    return [s for d in it["days"] for s in d["stops"]]


def test_readme_example_one_day_2500(gazetteer):
    it = generate_itinerary(gazetteer, HYD, 2500, 1, ["sightseeing", "food", "photography"])
    assert it["feasible"] and it["days_used"] == 1
    assert it["totals"]["total"] <= 2500
    assert it["totals"]["remaining"] == 2500 - it["totals"]["total"]
    assert len(all_stops(it)) >= 3
    assert "Ramoji Film City" in [d["name"] for d in it["dropped"]]  # 7h + ₹1500 cannot fit a busy day


def test_totals_add_up(gazetteer):
    it = generate_itinerary(gazetteer, HYD, 5000, 2, ["history"])
    t = it["totals"]
    assert t["total"] == pytest.approx(t["entry_and_activities"] + t["food"] + t["transport"] + t["daily_allowance"], abs=2)
    assert t["entry_and_activities"] == sum(s["cost"] for s in all_stops(it) if s["category"] != "food")


def test_day_time_window_respected(gazetteer):
    it = generate_itinerary(gazetteer, HYD, 8000, 3, [])
    for day in it["days"]:
        first, last = day["stops"][0], day["stops"][-1]
        h = lambda t: int(t[:2]) + int(t[3:]) / 60
        assert h(first["arrive"]) == pytest.approx(bo.DAY_START_HOUR)
        assert h(last["depart"]) <= bo.DAY_START_HOUR + bo.DAY_HOURS + 0.02


def test_stops_are_numbered_and_unique(gazetteer):
    it = generate_itinerary(gazetteer, HYD, 8000, 3, [])
    stops = all_stops(it)
    assert [s["order"] for s in stops] == list(range(1, len(stops) + 1))
    assert len({s["id"] for s in stops}) == len(stops)


def test_interests_change_what_is_kept(gazetteer):
    ids = ["hyd-paradise", "hyd-nimrah", "hyd-pista-house", "hyd-golconda", "hyd-chowmahalla", "hyd-zoo"]
    foodie = generate_itinerary(gazetteer, ids, 1500, 1, ["food"])
    kept = {s["id"] for s in all_stops(foodie)}
    assert {"hyd-paradise", "hyd-nimrah"} <= kept


def test_tiny_budget_is_reported_as_infeasible(gazetteer):
    with pytest.raises(InfeasibleTrip):
        generate_itinerary(gazetteer, HYD, 50, 1, [])


def test_zero_budget_infeasible(gazetteer):
    with pytest.raises(InfeasibleTrip):
        generate_itinerary(gazetteer, HYD, 0, 1, [])


def test_budget_just_enough_for_free_places_only(gazetteer):
    it = generate_itinerary(gazetteer, ["hyd-mecca-masjid", "hyd-birla-mandir"], 260, 1, [])
    assert it["totals"]["total"] <= 260


def test_not_all_places_fit_budget(gazetteer):
    it = generate_itinerary(gazetteer, HYD, 900, 1, ["sightseeing"])
    assert it["totals"]["total"] <= 900
    assert it["dropped"], "with ₹900 not everything can be visited"


def test_multi_city_reel_plans_dominant_city_only(gazetteer):
    ids = ["hyd-charminar", "hyd-golconda", "jai-hawa-mahal"]
    it = generate_itinerary(gazetteer, ids, 3000, 1, [])
    assert it["city"] == "Hyderabad"
    assert all(s["id"].startswith("hyd-") for s in all_stops(it))
    assert any("Jaipur" in w for w in it["warnings"])
    assert any(d["id"] == "jai-hawa-mahal" and "different city" in d["reason"] for d in it["dropped"])


def test_single_place_trip(gazetteer):
    it = generate_itinerary(gazetteer, ["goa-baga-beach"], 1000, 1, [])
    assert [s["name"] for s in all_stops(it)] == ["Baga Beach"]
    assert it["totals"]["km"] == 0


def test_more_days_than_needed_adds_note(gazetteer):
    it = generate_itinerary(gazetteer, ["hyd-charminar", "hyd-mecca-masjid"], 3000, 3, [])
    assert it["days_used"] == 1 and any("remaining days" in w for w in it["warnings"])


def test_route_order_is_not_worse_than_input_order(gazetteer):
    from app.services.route_planner import build_graph, distance_matrix
    ids = ["jai-amber-fort", "jai-albert-hall", "jai-nahargarh", "jai-hawa-mahal", "jai-jal-mahal"]
    it = generate_itinerary(gazetteer, ids, 10000, 1, [])
    stops = [s["id"] for s in all_stops(it)]
    g = build_graph(gazetteer.in_city("Jaipur"))
    dist = distance_matrix(g, stops)
    planned = sum(dist[(a, b)][0] for a, b in zip(stops, stops[1:]))
    given = sum(dist[(a, b)][0] for a, b in zip(ids, ids[1:]))
    assert planned <= given + 1e-9


def test_start_place_is_first(gazetteer):
    ids = ["hyd-charminar", "hyd-golconda", "hyd-chowmahalla"]
    it = generate_itinerary(gazetteer, ids, 3000, 1, [], start_place="hyd-golconda")
    assert all_stops(it)[0]["id"] == "hyd-golconda"


def test_route_path_available_for_map(gazetteer):
    it = generate_itinerary(gazetteer, HYD[:3], 3000, 1, [])
    assert len(it["days"][0]["path"]) >= 3


def test_split_into_days_never_overflows(gazetteer):
    order = [gazetteer.get(i) for i in HYD]
    days = split_into_days(order, {p.id: 5.0 for p in order}, 10)
    assert sum(len(d) for d in days) == len(order)
    assert len(days) >= 2


def test_large_selection_uses_heuristic_ordering(gazetteer):
    ids = [p.id for p in gazetteer.in_city("Delhi")]  # 12 places > exact limit
    it = generate_itinerary(gazetteer, ids, 20000, 3, [])
    assert it["totals"]["total"] <= 20000
