"""Candidate place detection from caption text / OCR text.

Pipeline: hashtags -> exact phrase matches -> fuzzy matches (for OCR noise)
-> city-based disambiguation of duplicate names. Names are always verified
against the gazetteer, so every returned candidate has real coordinates.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Dict, List

from app.services.geocoding import Gazetteer

FUZZY_CUTOFF = 0.85
FUZZY_MIN_LEN = 6
STOPWORDS = {"for", "the", "and", "in", "at", "to", "of", "a", "an", "is", "on", "with", "from", "by", "or", "my", "our"}
CITY_ALIASES = {"hyderabad": "Hyderabad", "secunderabad": "Hyderabad", "jaipur": "Jaipur", "pink city": "Jaipur",
                "goa": "Goa", "delhi": "Delhi", "new delhi": "Delhi"}

_PIN_RE = re.compile(r"(?:📍|\blocation\s*[:\-]|\bat\s*[:\-])\s*([^\n#|•·@]{3,60})", re.IGNORECASE)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _split_camel(word: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", word)


class LocationExtractor:
    def __init__(self, gazetteer: Gazetteer):
        self.gz = gazetteer
        self.alias_to_places: Dict[str, List[str]] = defaultdict(list)
        for p in gazetteer.all():
            names = {normalize(p.name)} | {normalize(a) for a in p.aliases}
            for n in names:
                if n and p.id not in self.alias_to_places[n]:
                    self.alias_to_places[n].append(p.id)
        self.squashed = defaultdict(list)  # "hawamahal" -> alias keys
        for alias in self.alias_to_places:
            self.squashed[alias.replace(" ", "")].append(alias)
        # longest first so "birla mandir" wins over a shorter alias contained in it
        self._aliases_by_len = sorted(self.alias_to_places, key=len, reverse=True)

    # ------------------------------------------------------------------
    def extract(self, text: str) -> dict:
        hits: Dict[str, Counter] = defaultdict(Counter)       # alias -> {"exact": n, ...}
        fuzzy_conf: Dict[str, float] = {}

        text = text or ""
        working = text

        # 1. hashtags: #HawaMahal (camel case) or #charminar (squashed)
        def hashtag(m: re.Match) -> str:
            word = m.group(1)
            key = word.lower()
            if key in self.squashed:
                # several aliases can squash to the same string; count the tag once
                hits[self.squashed[key][0]]["hashtag"] += 1
                return " "
            return " " + _split_camel(word) + " "
        working = re.sub(r"#(\w+)", hashtag, working)

        norm = normalize(working)

        # 2. exact phrase matches, consuming matched text
        for alias in self._aliases_by_len:
            pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])")
            count = len(pattern.findall(norm))
            if count:
                hits[alias]["exact"] += count
                norm = pattern.sub(" " * 1, norm)

        # 3. fuzzy matches on what is left (OCR noise such as 'Hawa Maha1')
        tokens = norm.split()
        used = [False] * len(tokens)
        fuzzy_pool = [a for a in self._aliases_by_len if len(a) >= FUZZY_MIN_LEN]
        for n in (4, 3, 2, 1):
            for i in range(len(tokens) - n + 1):
                if any(used[i:i + n]):
                    continue
                window = tokens[i:i + n]
                if window[0] in STOPWORDS or window[-1] in STOPWORDS:
                    continue
                phrase = " ".join(window)
                if len(phrase) < FUZZY_MIN_LEN:
                    continue
                match = difflib.get_close_matches(phrase, fuzzy_pool, n=1, cutoff=FUZZY_CUTOFF)
                if match:
                    alias = match[0]
                    hits[alias]["fuzzy"] += 1
                    ratio = difflib.SequenceMatcher(None, phrase, alias).ratio()
                    fuzzy_conf[alias] = max(fuzzy_conf.get(alias, 0), ratio)
                    for k in range(i, i + n):
                        used[k] = True

        # 4. city context
        full_norm = normalize(text)
        city_score: Counter = Counter()
        for phrase, city in CITY_ALIASES.items():
            c = len(re.findall(rf"(?<![a-z0-9]){phrase}(?![a-z0-9])", full_norm))
            if c:
                city_score[city] += c
        for alias, kinds in hits.items():
            ids = self.alias_to_places[alias]
            if len(ids) == 1:
                city_score[self.gz.get(ids[0]).city] += 0.5 * sum(kinds.values())

        # 5. build candidates
        candidates: Dict[str, dict] = {}
        for alias, kinds in hits.items():
            ids = self.alias_to_places[alias]
            ambiguous = False
            if len(ids) > 1:
                scored = sorted(ids, key=lambda i: city_score[self.gz.get(i).city], reverse=True)
                top = city_score[self.gz.get(scored[0]).city]
                second = city_score[self.gz.get(scored[1]).city]
                if top > second:
                    ids = [scored[0]]
                else:
                    ambiguous = True
            for pid in ids:
                p = self.gz.get(pid)
                mentions = sum(kinds.values())
                if "exact" in kinds:
                    conf, how = 1.0, "exact"
                elif "hashtag" in kinds:
                    conf, how = 0.95, "hashtag"
                else:
                    conf, how = round(fuzzy_conf.get(alias, FUZZY_CUTOFF), 2), "fuzzy"
                entry = candidates.setdefault(pid, {
                    "id": pid, "name": p.name, "city": p.city, "lat": p.lat, "lon": p.lon,
                    "tags": p.tags, "mentions": 0, "confidence": 0.0, "match": how,
                    "ambiguous": ambiguous,
                })
                entry["mentions"] += mentions
                if conf > entry["confidence"]:
                    entry["confidence"], entry["match"] = conf, how
                entry["ambiguous"] = entry["ambiguous"] or ambiguous

        # 6. explicit pins / "location:" lines that are not in the dataset
        matched_norm = {normalize(c["name"]) for c in candidates.values()}
        unresolved: List[str] = []
        for m in _PIN_RE.finditer(text):
            raw = m.group(1).strip(" .,:;-")
            n = normalize(raw)
            if not n or n in matched_norm:
                continue
            if any(a in n or n in a for a in self.alias_to_places):
                continue
            if raw not in unresolved:
                unresolved.append(raw)

        ordered = sorted(candidates.values(), key=lambda c: (-c["mentions"], -c["confidence"], c["name"]))
        return {"candidates": ordered, "unresolved": unresolved[:10]}
