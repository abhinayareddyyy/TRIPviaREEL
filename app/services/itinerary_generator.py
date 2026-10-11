"""Builds a day-wise itinerary that respects the budget and trip duration."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from app.services import budget_optimizer as bo
from app.services.geocoding import Gazetteer, Place
from app.services.route_planner import build_graph, plan_route

MAX_REPAIR_ROUNDS = 60


def _fmt_clock(hours: float) -> str:
    total_min = int(round(hours * 60))
    return f"{total_min // 60 % 24:02d}:{total_min % 60:02d}"


def split_into_days(order: Sequence[Place], leg_km: Dict[str, float], day_hours: float) -> List[List[Place]]:
    """Greedily fill each day with consecutive stops until its time window is used.

    ``leg_km[place_id]`` is the road distance from the previous stop. The first
    stop of a day has no inbound leg (the traveller starts the day nearby).
    """
    days: List[List[Place]] = []
    used, cur = 0.0, []
    for p in order:
        inbound = 0.0 if not cur else bo.travel_minutes(leg_km.get(p.id, 0.0)) / 60.0
        need = inbound + p.visit_hours
        if cur and used + need > day_hours + 1e-9:
            days.append(cur)
            cur, used = [], 0.0
            need = p.visit_hours
        cur.append(p)
        used += need
    if cur:
        days.append(cur)
    return days


def _evaluate(order: List[Place], route: dict, days_requested: int) -> dict:
    leg_km = {l["to"]: l["km"] for l in route["legs"]}
    day_lists = split_into_days(order, leg_km, bo.DAY_HOURS)
    entry = sum(p.spend for p in order if not p.is_food)
    food = sum(p.spend for p in order if p.is_food)
    km = 0.0
    for d in day_lists:
        for p in d[1:]:
            km += leg_km.get(p.id, 0.0)
    transport = bo.travel_cost(km)
    allowance = bo.DAILY_ALLOWANCE * len(day_lists)
    return {
        "day_lists": day_lists, "leg_km": leg_km, "entry": entry, "food": food,
        "km": km, "transport": transport, "allowance": allowance,
        "total": entry + food + transport + allowance,
        "days_used": len(day_lists),
    }


def generate_itinerary(
    gazetteer: Gazetteer,
    place_ids: Sequence[str],
    budget: float,
    days: int,
    interests: Sequence[str] = (),
    mentions: Optional[Dict[str, int]] = None,
    start_place: Optional[str] = None,
) -> dict:
    """Select, order and schedule destinations.

    Steps: (1) keep the dominant city, (2) knapsack-select places that fit the
    budget/time after reserving for travel, (3) order them with A*-based
    distances, (4) check the real route cost and, if over budget, enlarge the
    reserves and re-select (repair loop).
    """
    mentions = mentions or {}
    warnings: List[str] = []
    places = [gazetteer.get(pid) for pid in dict.fromkeys(place_ids)]
    places = [p for p in places if p is not None]
    if not places:
        raise ValueError("no valid places supplied")

    # --- 1. a trip happens in one city; keep the city with most requested stops
    by_city: Dict[str, List[Place]] = {}
    for p in places:
        by_city.setdefault(p.city, []).append(p)
    city = max(by_city, key=lambda c: (len(by_city[c]), sum(mentions.get(p.id, 1) for p in by_city[c])))
    dropped: List[dict] = []
    if len(by_city) > 1:
        others = sorted(c for c in by_city if c != city)
        warnings.append(
            f"Places are spread across several cities; planned {city} only. "
            f"Left out: {', '.join(others)}. Plan those as a separate trip."
        )
        for c in others:
            for p in by_city[c]:
                dropped.append({"id": p.id, "name": p.name, "reason": f"different city ({c})"})
    candidates = by_city[city]

    # road graph over *all* known places in the city so A* can route via other landmarks
    graph = build_graph(gazetteer.in_city(city))
    values = {p.id: bo.place_value(p, interests, mentions.get(p.id, 1)) for p in candidates}

    # --- 2-4. selection with repair loop
    # The knapsack cannot see travel cost (it depends on the final route), so we
    # check the real route and, when over budget/time, either reserve more money
    # and time or - if the selection stopped changing, e.g. free places whose
    # only cost is travel - drop the least valuable place and try again.
    pool = list(candidates)
    reserve_cost = bo.DAILY_ALLOWANCE * days
    reserve_hours = 0.0
    best = None
    prev_ids = None
    for _ in range(MAX_REPAIR_ROUNDS):
        sel = bo.select_places(pool, budget - reserve_cost, days * bo.DAY_HOURS - reserve_hours, values)
        if not sel.chosen:
            break
        start = start_place if start_place in {p.id for p in sel.chosen} else None
        route = plan_route(graph, [p.id for p in sel.chosen], start)
        order = [gazetteer.get(i) for i in route["order"]]
        ev = _evaluate(order, route, days)
        ok = ev["total"] <= budget + 1e-6 and ev["days_used"] <= days
        if ok:
            best = (sel, route, order, ev)
            break
        chosen_ids = frozenset(p.id for p in sel.chosen)
        if chosen_ids == prev_ids and len(pool) > 1:
            # more reserve did not change anything: drop the weakest, most travel-heavy place
            leg_km = {l["to"]: l["km"] for l in route["legs"]}
            weakest = min(sel.chosen, key=lambda p: (values[p.id], -leg_km.get(p.id, 0.0)))
            pool = [p for p in pool if p.id != weakest.id]
        prev_ids = chosen_ids
        over_cost = max(0.0, ev["total"] - budget)
        over_days = max(0, ev["days_used"] - days)
        reserve_cost += max(over_cost, 10.0)
        reserve_hours += max(0.5, over_days * bo.DAY_HOURS * 0.25)

    if best is None:
        raise InfeasibleTrip(
            "Nothing from this reel fits the budget and duration. "
            f"Minimum for one day is about ₹{int(bo.DAILY_ALLOWANCE)} for daily expenses plus entry fees and travel; "
            "try a higher budget or more days."
        )
    sel, route, order, ev = best

    chosen_ids = {p.id for p in order}
    for p in candidates:
        if p.id not in chosen_ids:
            dropped.append({"id": p.id, "name": p.name, "reason": "did not fit the budget/time alongside better-matching places"})

    # --- schedule
    leg_by_to = {l["to"]: l for l in route["legs"]}
    day_out = []
    day_stops_total = 0
    for d_idx, stops in enumerate(ev["day_lists"], start=1):
        clock = bo.DAY_START_HOUR
        out_stops, path_coords, day_km, day_cost = [], [], 0.0, 0.0
        for s_idx, p in enumerate(stops):
            leg = leg_by_to.get(p.id)
            km = leg["km"] if (s_idx > 0 and leg) else 0.0
            tmin = bo.travel_minutes(km)
            clock += tmin / 60.0
            arrive = clock
            clock += p.visit_hours
            tcost = bo.travel_cost(km)
            day_km += km
            day_cost += p.spend + tcost
            if s_idx > 0 and leg:
                for node in leg["path"]:
                    gp = gazetteer.get(node)
                    path_coords.append([gp.lat, gp.lon])
            elif s_idx == 0:
                path_coords.append([p.lat, p.lon])
            day_stops_total += 1
            out_stops.append({
                "order": day_stops_total, "id": p.id, "name": p.name,
                "lat": p.lat, "lon": p.lon, "category": p.category, "tags": p.tags,
                "arrive": _fmt_clock(arrive), "depart": _fmt_clock(clock),
                "visit_hours": p.visit_hours, "cost": round(p.spend),
                "travel_km": round(km, 1), "travel_min": int(round(tmin)),
                "travel_cost": round(tcost),
                "via": [gazetteer.get(n).name for n in leg["path"][1:-1]] if (s_idx > 0 and leg) else [],
            })
        day_out.append({
            "day": d_idx, "stops": out_stops, "km": round(day_km, 1),
            "cost": round(day_cost + bo.DAILY_ALLOWANCE), "path": path_coords,
            "ends_at": _fmt_clock(clock),
        })

    total = round(ev["total"])
    if ev["days_used"] < days:
        warnings.append(
            f"The reel's places fit in {ev['days_used']} day(s); the remaining days are free for places not shown in the reel."
        )
    if dropped and any(d["reason"].startswith("did not fit") for d in dropped):
        warnings.append("Some detected places were left out to stay within budget and time. See 'Left out' below.")

    return {
        "city": city,
        "budget": round(budget),
        "days_requested": days,
        "days_used": ev["days_used"],
        "feasible": True,
        "totals": {
            "entry_and_activities": round(ev["entry"]),
            "food": round(ev["food"]),
            "transport": round(ev["transport"]),
            "daily_allowance": round(ev["allowance"]),
            "total": total,
            "remaining": round(budget) - total,
            "km": round(ev["km"], 1),
        },
        "days": day_out,
        "dropped": dropped,
        "warnings": warnings,
        "assumptions": {
            "transport_inr_per_km": bo.COST_PER_KM,
            "average_speed_kmph": bo.SPEED_KMPH,
            "daily_allowance_inr": bo.DAILY_ALLOWANCE,
            "day_window": f"{_fmt_clock(bo.DAY_START_HOUR)}-{_fmt_clock(bo.DAY_START_HOUR + bo.DAY_HOURS)}",
            "road_factor": 1.3,
            "note": "Costs, fees and durations are approximate estimates for one traveller. Opening hours are not modelled.",
        },
    }


class InfeasibleTrip(ValueError):
    """Raised when no selection of places fits the budget and duration."""
