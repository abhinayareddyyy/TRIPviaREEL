"""Budget- and time-constrained destination selection.

Choosing *which* places to visit is a 0/1 knapsack with two constraints
(money and time). It is solved exactly with dynamic programming. Travel cost
depends on the final route, so the itinerary generator re-solves with larger
"reserves" until the real route fits (see itinerary_generator.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from app.services.geocoding import Place

# ---- planning assumptions (all approximate, shown to the user) ----
COST_PER_KM = 12.0      # INR per km, blend of auto-rickshaw / cab fares
SPEED_KMPH = 25.0       # average urban travel speed
DAILY_ALLOWANCE = 200.0 # INR per day for water, snacks and small expenses
DAY_START_HOUR = 9.0
DAY_HOURS = 10.0        # sightseeing hours available per day

COST_UNIT = 10          # knapsack granularity: INR 10
TIME_UNIT = 0.5         # knapsack granularity: 30 minutes


def place_value(place: Place, interests: Iterable[str], mentions: int = 1) -> float:
    """Usefulness of a place: base + interest matches + how often the reel showed it."""
    wanted = {i.lower() for i in interests}
    overlap = len(wanted & set(place.tags))
    return 1.0 + 2.0 * overlap + 0.5 * min(max(mentions, 1), 4)


@dataclass
class Selection:
    chosen: List[Place]
    total_value: float
    total_cost: float
    total_hours: float


def select_places(
    places: Sequence[Place],
    cost_budget: float,
    time_budget_hours: float,
    values: Dict[str, float],
) -> Selection:
    """Maximise total value subject to spend <= cost_budget and visit hours <= time budget."""
    n = len(places)
    if n == 0 or cost_budget < 0 or time_budget_hours < 0:
        return Selection([], 0.0, 0.0, 0.0)

    costs = [math.ceil(round(p.spend, 6) / COST_UNIT) for p in places]
    times = [math.ceil(round(p.visit_hours, 6) / TIME_UNIT) for p in places]
    vals = [int(round(values[p.id] * 10)) for p in places]

    cap_c = min(int(cost_budget // COST_UNIT), sum(costs))
    cap_t = min(int(time_budget_hours // TIME_UNIT), sum(times))

    # dp[i][c][t] = best value using the first i places
    dp = [[[0] * (cap_t + 1) for _ in range(cap_c + 1)] for _ in range(n + 1)]
    for i in range(1, n + 1):
        ci, ti, vi = costs[i - 1], times[i - 1], vals[i - 1]
        prev, cur = dp[i - 1], dp[i]
        for c in range(cap_c + 1):
            for t in range(cap_t + 1):
                best = prev[c][t]
                if c >= ci and t >= ti:
                    cand = prev[c - ci][t - ti] + vi
                    if cand > best:
                        best = cand
                cur[c][t] = best

    chosen: List[Place] = []
    c, t = cap_c, cap_t
    for i in range(n, 0, -1):
        if dp[i][c][t] != dp[i - 1][c][t]:
            chosen.append(places[i - 1])
            c -= costs[i - 1]
            t -= times[i - 1]
    chosen.reverse()
    return Selection(
        chosen=chosen,
        total_value=sum(values[p.id] for p in chosen),
        total_cost=sum(p.spend for p in chosen),
        total_hours=sum(p.visit_hours for p in chosen),
    )


def travel_cost(km: float) -> float:
    return km * COST_PER_KM


def travel_minutes(km: float) -> float:
    return km / SPEED_KMPH * 60.0
