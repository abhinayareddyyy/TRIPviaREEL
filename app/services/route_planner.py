"""Route planning: road graph construction, A* legs, and visiting order."""
from __future__ import annotations

import itertools
from typing import Dict, List, Optional, Sequence, Tuple

from app.algorithms.astar import Graph, astar, haversine_km
from app.services.geocoding import Place

ROAD_FACTOR = 1.3      # road distance is typically ~30% longer than a straight line
NEIGHBOURS_K = 3       # each place is linked to its k nearest places
EXACT_ORDER_LIMIT = 8  # brute-force the visiting order up to this many stops


def build_graph(places: Sequence[Place], k: int = NEIGHBOURS_K) -> Graph:
    """Connect every place to its k nearest neighbours (edge cost = road km).

    Components are then joined by their closest pair so the graph is always
    connected. Because each edge costs ROAD_FACTOR * straight-line distance,
    the haversine heuristic used by A* is admissible.
    """
    g = Graph()
    for p in places:
        g.add_node(p.id, p.lat, p.lon)
    ids = [p.id for p in places]

    def road_km(a: str, b: str) -> float:
        return ROAD_FACTOR * haversine_km(g.coords[a], g.coords[b])

    for a in ids:
        nearest = sorted((b for b in ids if b != a), key=lambda b: road_km(a, b))[:k]
        for b in nearest:
            g.add_edge(a, b, road_km(a, b))

    # join disconnected components through their closest pair of nodes
    while True:
        comps = _components(g)
        if len(comps) <= 1:
            break
        base = comps[0]
        best: Optional[Tuple[float, str, str]] = None
        for other in comps[1:]:
            for a in base:
                for b in other:
                    d = road_km(a, b)
                    if best is None or d < best[0]:
                        best = (d, a, b)
        assert best is not None
        g.add_edge(best[1], best[2], best[0])
    return g


def _components(g: Graph) -> List[List[str]]:
    seen, comps = set(), []
    for n in g.coords:
        if n in seen:
            continue
        stack, comp = [n], []
        seen.add(n)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nb in g.neighbors(cur):
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        comps.append(comp)
    return comps


def distance_matrix(g: Graph, ids: Sequence[str]) -> Dict[Tuple[str, str], Tuple[float, List[str]]]:
    """Pairwise A* shortest road distances: (a, b) -> (km, node path)."""
    out: Dict[Tuple[str, str], Tuple[float, List[str]]] = {}
    for a, b in itertools.combinations(ids, 2):
        res = astar(g, a, b)
        if not res.found:
            raise ValueError(f"no route between {a} and {b}")
        out[(a, b)] = (res.cost, res.path)
        out[(b, a)] = (res.cost, list(reversed(res.path)))
    for a in ids:
        out[(a, a)] = (0.0, [a])
    return out


def _path_cost(order: Sequence[str], dist) -> float:
    return sum(dist[(order[i], order[i + 1])][0] for i in range(len(order) - 1))


def best_order(ids: Sequence[str], dist, start: Optional[str] = None) -> List[str]:
    """Visiting order that minimises total travel (open path, no return trip).

    A* only answers "shortest path between two nodes"; deciding the order of
    several stops is a separate problem. For up to EXACT_ORDER_LIMIT stops every
    permutation is checked; beyond that nearest-neighbour + 2-opt is used.
    """
    ids = list(ids)
    if start and start not in ids:
        if len(ids) <= EXACT_ORDER_LIMIT:
            best = min(ids, key=lambda i: dist[(start, i)][0])
            rest = [i for i in ids if i != best]
            return [start, best] + rest if rest else [start, best]
        ids = [start] + ids
    if len(ids) <= 2:
        if start and start in ids and ids[0] != start:
            ids.reverse()
        return ids
    if len(ids) <= EXACT_ORDER_LIMIT:
        rest = [i for i in ids if i != start]
        best, best_cost = None, float("inf")
        for perm in itertools.permutations(rest):
            order = ([start] if start else []) + list(perm)
            c = _path_cost(order, dist)
            if c < best_cost - 1e-9:
                best, best_cost = order, c
        return list(best)  # type: ignore[arg-type]

    starts = [start] if start else ids
    best, best_cost = None, float("inf")
    for s in starts:
        order = [s]
        left = set(ids) - {s}
        while left:
            nxt = min(left, key=lambda x: dist[(order[-1], x)][0])
            order.append(nxt)
            left.remove(nxt)
        order = _two_opt(order, dist, fixed_first=bool(start))
        c = _path_cost(order, dist)
        if c < best_cost:
            best, best_cost = order, c
    return list(best)  # type: ignore[arg-type]


def _two_opt(order: List[str], dist, fixed_first: bool) -> List[str]:
    improved = True
    lo = 1 if fixed_first else 0
    while improved:
        improved = False
        for i in range(lo, len(order) - 1):
            for j in range(i + 1, len(order)):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                if _path_cost(cand, dist) < _path_cost(order, dist) - 1e-9:
                    order, improved = cand, True
    return order


def plan_route(g: Graph, ids: Sequence[str], start: Optional[str] = None) -> dict:
    """Order the stops and return A* legs between consecutive stops."""
    if not ids:
        return {"order": [], "legs": [], "total_km": 0.0}
    route_ids = list(dict.fromkeys(([start] if start else []) + list(ids)))
    dist = distance_matrix(g, route_ids)
    order = best_order(ids, dist, start)
    legs = []
    for a, b in zip(order, order[1:]):
        km, path = dist[(a, b)]
        legs.append({"from": a, "to": b, "km": km, "path": path})
    return {"order": order, "legs": legs, "total_km": sum(l["km"] for l in legs)}
