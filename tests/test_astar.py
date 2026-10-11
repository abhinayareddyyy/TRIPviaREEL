import math
import random

import pytest

from app.algorithms.astar import Graph, astar, dijkstra, haversine_km
from app.services.route_planner import ROAD_FACTOR, build_graph


def line_graph():
    g = Graph()
    for n, (la, lo) in {"A": (0, 0), "B": (0, 1), "C": (0, 2), "D": (1, 1)}.items():
        g.add_node(n, la, lo)
    g.add_edge("A", "B", 100)
    g.add_edge("B", "C", 100)
    g.add_edge("A", "D", 500)
    g.add_edge("D", "C", 500)
    return g


def test_finds_known_shortest_path():
    r = astar(line_graph(), "A", "C")
    assert r.path == ["A", "B", "C"] and r.cost == 200


def test_start_equals_goal():
    r = astar(line_graph(), "A", "A")
    assert r.path == ["A"] and r.cost == 0


def test_unreachable_goal_returns_none():
    g = line_graph()
    g.add_node("Z", 10, 10)
    r = astar(g, "A", "Z")
    assert r.path is None and not r.found and r.cost == math.inf


def test_unknown_node_raises():
    with pytest.raises(KeyError):
        astar(line_graph(), "A", "nope")


def test_negative_edge_rejected():
    g = line_graph()
    with pytest.raises(ValueError):
        g.add_edge("A", "C", -1)


def test_haversine_known_distance():
    # Hyderabad (Charminar) to Golconda is roughly 7-8 km in a straight line
    d = haversine_km((17.3616, 78.4747), (17.3833, 78.4011))
    assert 7.0 < d < 8.5


def random_geo_graph(seed, n=40):
    rnd = random.Random(seed)
    g = Graph()
    for i in range(n):
        g.add_node(i, 17 + rnd.random() * 0.3, 78 + rnd.random() * 0.3)
    for i in range(n):
        for j in rnd.sample(range(n), 4):
            if i != j:
                # cost >= straight-line distance keeps the haversine heuristic admissible
                g.add_edge(i, j, haversine_km(g.coords[i], g.coords[j]) * rnd.uniform(1.0, 1.8))
    return g


@pytest.mark.parametrize("seed", range(15))
def test_astar_matches_dijkstra_cost(seed):
    g = random_geo_graph(seed)
    rnd = random.Random(seed + 100)
    for _ in range(10):
        a, b = rnd.sample(range(len(g)), 2)
        ra, rd = astar(g, a, b), dijkstra(g, a, b)
        assert ra.found == rd.found
        if ra.found:
            assert ra.cost == pytest.approx(rd.cost)


def test_astar_expands_fewer_nodes_than_dijkstra_overall():
    total_a = total_d = 0
    for seed in range(15):
        g = random_geo_graph(seed)
        rnd = random.Random(seed)
        for _ in range(10):
            a, b = rnd.sample(range(len(g)), 2)
            ra, rd = astar(g, a, b), dijkstra(g, a, b)
            if ra.found:
                total_a += ra.expanded
                total_d += rd.expanded
    assert total_a < total_d


def test_heuristic_admissible_on_place_graph(gazetteer):
    """h(n) <= true remaining cost for every pair of places in every city."""
    for city in gazetteer.cities():
        places = gazetteer.in_city(city)
        g = build_graph(places)
        for a in places:
            for b in places:
                res = dijkstra(g, a.id, b.id)
                assert res.found
                assert haversine_km(a.coord, b.coord) <= res.cost + 1e-9


def test_place_graph_is_connected_and_road_factor_applied(gazetteer):
    for city in gazetteer.cities():
        places = gazetteer.in_city(city)
        g = build_graph(places)
        first = places[0].id
        assert all(astar(g, first, p.id).found for p in places)
    p, q = gazetteer.in_city("Hyderabad")[:2]
    g = build_graph(gazetteer.in_city("Hyderabad"))
    assert astar(g, p.id, q.id).cost >= ROAD_FACTOR * haversine_km(p.coord, q.coord) - 1e-9
