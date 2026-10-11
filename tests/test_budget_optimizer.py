import itertools
import random

import pytest

from app.services import budget_optimizer as bo
from app.services.geocoding import Place


def mk(i, spend, hours, tags=("sightseeing",), category="attraction"):
    return Place(id=f"p{i}", name=f"P{i}", city="X", lat=0, lon=0, tags=list(tags),
                 category=category, spend=spend, visit_hours=hours)


def brute_force(places, budget, hours, values):
    best = 0.0
    for r in range(len(places) + 1):
        for combo in itertools.combinations(places, r):
            cost = sum(bo.COST_UNIT * -(-p.spend // bo.COST_UNIT) for p in combo)
            time = sum(bo.TIME_UNIT * -(-p.visit_hours // bo.TIME_UNIT) for p in combo)
            if cost <= budget and time <= hours:
                best = max(best, sum(round(values[p.id] * 10) for p in combo))
    return best / 10


@pytest.mark.parametrize("seed", range(25))
def test_knapsack_is_optimal_vs_brute_force(seed):
    rnd = random.Random(seed)
    places = [mk(i, rnd.choice([0, 20, 50, 100, 250, 400, 600]), rnd.choice([0.5, 1, 1.5, 2, 3])) for i in range(9)]
    values = {p.id: rnd.choice([1.5, 2, 3.5, 5, 7]) for p in places}
    budget, hours = rnd.choice([300, 600, 1000]), rnd.choice([4, 6, 10])
    sel = bo.select_places(places, budget, hours, values)
    assert sel.total_cost <= budget and sel.total_hours <= hours
    assert sel.total_value == pytest.approx(brute_force(places, budget, hours, values))


def test_budget_never_exceeded_and_time_respected():
    places = [mk(i, 300, 2) for i in range(10)]
    values = {p.id: 3 for p in places}
    sel = bo.select_places(places, 1000, 7, values)
    assert len(sel.chosen) == 3  # 3*300 <= 1000 and 3*2h <= 7h; a 4th breaks both


def test_everything_selected_when_it_all_fits():
    places = [mk(i, 50, 1) for i in range(4)]
    sel = bo.select_places(places, 10_000, 100, {p.id: 1 for p in places})
    assert len(sel.chosen) == 4


def test_zero_budget_selects_only_free_places():
    places = [mk(1, 0, 1), mk(2, 100, 1)]
    sel = bo.select_places(places, 0, 5, {"p1": 1, "p2": 5})
    assert [p.id for p in sel.chosen] == ["p1"]


def test_empty_inputs():
    assert bo.select_places([], 100, 5, {}).chosen == []
    assert bo.select_places([mk(1, 10, 1)], -5, 5, {"p1": 1}).chosen == []


def test_interest_match_raises_value():
    food = mk(1, 100, 1, tags=("food",), category="food")
    temple = mk(2, 100, 1, tags=("spiritual",))
    assert bo.place_value(food, ["food"]) > bo.place_value(temple, ["food"])
    assert bo.place_value(food, []) == bo.place_value(temple, [])


def test_more_mentions_raise_value_but_are_capped():
    p = mk(1, 0, 1)
    assert bo.place_value(p, [], 3) > bo.place_value(p, [], 1)
    assert bo.place_value(p, [], 50) == bo.place_value(p, [], 4)


def test_travel_helpers():
    assert bo.travel_cost(10) == 10 * bo.COST_PER_KM
    assert bo.travel_minutes(bo.SPEED_KMPH) == pytest.approx(60)
