"""Geographic verification against the offline place dataset (data/places.json).

The dataset plays the role of the "geographic dataset" in the README: a
candidate name is only accepted as a destination when it can be matched to a
known place with real coordinates.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

DEFAULT_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "places.json")

REQUIRED_FIELDS = ("id", "name", "city", "lat", "lon", "tags", "category", "spend", "visit_hours")


@dataclass
class Place:
    id: str
    name: str
    city: str
    lat: float
    lon: float
    tags: List[str]
    category: str  # "attraction" or "food"
    spend: float  # typical per-person cost in INR (entry fee or meal)
    visit_hours: float
    aliases: List[str] = field(default_factory=list)

    @property
    def is_food(self) -> bool:
        return self.category == "food"

    @property
    def coord(self):
        return (self.lat, self.lon)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "city": self.city,
            "lat": self.lat, "lon": self.lon, "tags": list(self.tags),
            "category": self.category, "spend": self.spend,
            "visit_hours": self.visit_hours,
        }


class Gazetteer:
    def __init__(self, places: List[Place], valid_tags: Optional[List[str]] = None):
        self.places: Dict[str, Place] = {}
        for p in places:
            if p.id in self.places:
                raise ValueError(f"duplicate place id: {p.id}")
            self.places[p.id] = p
        self.valid_tags = valid_tags or []

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Gazetteer":
        path = os.path.abspath(path or os.environ.get("TRIPVIAREEL_PLACES") or DEFAULT_DATA_PATH)
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        places = []
        for item in raw["places"]:
            missing = [f for f in REQUIRED_FIELDS if f not in item]
            if missing:
                raise ValueError(f"place {item.get('id', '?')} is missing fields: {missing}")
            places.append(Place(
                id=item["id"], name=item["name"], city=item["city"],
                lat=float(item["lat"]), lon=float(item["lon"]),
                tags=list(item["tags"]), category=item["category"],
                spend=float(item["spend"]), visit_hours=float(item["visit_hours"]),
                aliases=list(item.get("aliases", [])),
            ))
        return cls(places, raw.get("_meta", {}).get("tags", []))

    def get(self, place_id: str) -> Optional[Place]:
        return self.places.get(place_id)

    def all(self) -> List[Place]:
        return list(self.places.values())

    def cities(self) -> List[str]:
        return sorted({p.city for p in self.places.values()})

    def in_city(self, city: str) -> List[Place]:
        return [p for p in self.places.values() if p.city == city]
