"""A* search (and Dijkstra for comparison) on a weighted, undirected graph.

The evaluation function is f(n) = g(n) + h(n):
    g(n) - actual cost from the start node to n
    h(n) - estimated remaining cost from n to the goal
For geographic graphs the default heuristic is the great-circle (haversine)
distance, which never overestimates the road distance as long as every edge
cost is >= the straight-line distance between its endpoints.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from itertools import count
from typing import Callable, Dict, Hashable, List, Optional, Tuple

EARTH_RADIUS_KM = 6371.0088

Node = Hashable


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


class Graph:
    """Undirected weighted graph whose nodes carry (lat, lon) coordinates."""

    def __init__(self) -> None:
        self.coords: Dict[Node, Tuple[float, float]] = {}
        self.adj: Dict[Node, Dict[Node, float]] = {}

    def add_node(self, node: Node, lat: float, lon: float) -> None:
        self.coords[node] = (lat, lon)
        self.adj.setdefault(node, {})

    def add_edge(self, u: Node, v: Node, cost: float) -> None:
        if u not in self.coords or v not in self.coords:
            raise KeyError("both nodes must be added before connecting them")
        if cost < 0:
            raise ValueError("edge cost must be non-negative")
        # keep the cheaper edge if one already exists
        if v not in self.adj[u] or cost < self.adj[u][v]:
            self.adj[u][v] = cost
            self.adj[v][u] = cost

    def neighbors(self, node: Node) -> Dict[Node, float]:
        return self.adj[node]

    def __contains__(self, node: Node) -> bool:
        return node in self.coords

    def __len__(self) -> int:
        return len(self.coords)


@dataclass
class SearchResult:
    path: Optional[List[Node]]  # None when the goal is unreachable
    cost: float = math.inf
    expanded: int = 0  # number of nodes popped and expanded (search effort)
    expansion_order: List[Node] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.path is not None


Heuristic = Callable[[Node, Node], float]


def _zero_heuristic(_n: Node, _goal: Node) -> float:
    return 0.0


def astar(
    graph: Graph,
    start: Node,
    goal: Node,
    heuristic: Optional[Heuristic] = None,
) -> SearchResult:
    """Least-cost path from ``start`` to ``goal``.

    ``heuristic(n, goal)`` defaults to haversine distance between node
    coordinates. Pass ``lambda n, g: 0`` to obtain Dijkstra's algorithm.
    """
    if start not in graph or goal not in graph:
        raise KeyError("start and goal must both be nodes of the graph")

    if heuristic is None:
        def heuristic(n: Node, g: Node) -> float:  # type: ignore[misc]
            return haversine_km(graph.coords[n], graph.coords[g])

    tie = count()  # stable ordering when f-values are equal
    best_g: Dict[Node, float] = {start: 0.0}
    parent: Dict[Node, Optional[Node]] = {start: None}
    frontier: List[Tuple[float, int, float, Node]] = [(heuristic(start, goal), next(tie), 0.0, start)]
    expanded = 0
    order: List[Node] = []

    while frontier:
        _f, _t, g, node = heapq.heappop(frontier)
        if g > best_g.get(node, math.inf):
            continue  # stale queue entry
        expanded += 1
        order.append(node)
        if node == goal:
            path: List[Node] = []
            cur: Optional[Node] = node
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            path.reverse()
            return SearchResult(path, g, expanded, order)
        for nxt, w in graph.neighbors(node).items():
            ng = g + w
            if ng < best_g.get(nxt, math.inf):
                best_g[nxt] = ng
                parent[nxt] = node
                heapq.heappush(frontier, (ng + heuristic(nxt, goal), next(tie), ng, nxt))

    return SearchResult(None, math.inf, expanded, order)


def dijkstra(graph: Graph, start: Node, goal: Node) -> SearchResult:
    """Dijkstra's algorithm = A* with a zero heuristic."""
    return astar(graph, start, goal, heuristic=_zero_heuristic)
