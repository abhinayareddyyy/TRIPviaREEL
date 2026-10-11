# TripViaReel : AI-Powered Travel Itinerary Generator

**From travel reels to budget-friendly itineraries.**

TripViaReel turns travel inspiration into a practical plan. You give it a travel reel (an Instagram link, a screenshot, a screen recording, or just the caption); it finds the places shown, verifies them against a geographic dataset, and builds a day-wise itinerary that fits your **budget** and **trip duration**, with the route drawn on a map.

It combines **OCR / computer vision, text processing, A\* search, and budget-constrained optimisation**, and uses only free and open-source software. No paid API, account or key is needed.

> **Status: working prototype.** Everything marked ✅ below is implemented and covered by the automated tests (`pytest`, 155 tests). Things that are *not* done are listed honestly under [Limitations](#limitations).

## Problem Statement

Travel reels show several destinations but give no plan. Viewers must work out the places, the distances, the costs and a sensible visiting order by hand. TripViaReel automates that.

## Features

| | Feature | How it works |
|---|---|---|
| ✅ | Reel input | Paste a reel link, paste the caption, and/or upload up to 5 screenshots / videos |
| ✅ | Upload fallback | Instagram usually blocks automatic access, so screenshots (PNG/JPG/WEBP) and videos (MP4/MOV/WEBM) are fully supported |
| ✅ | Location extraction | Tesseract OCR on images and sampled video frames, then dictionary + fuzzy matching of place names, hashtags (`#HawaMahal`) and aliases |
| ✅ | Geographic verification | Every candidate is matched to a known place with real coordinates (offline dataset, `data/places.json`) |
| ✅ | Duplicate-name handling | "Birla Mandir" exists in Hyderabad *and* Jaipur; city mentions and neighbouring places decide, otherwise you are asked to choose |
| ✅ | A\* route search | Places form a road graph; A\* with a haversine heuristic finds shortest road paths between stops |
| ✅ | Visiting order | Exact (all permutations) for up to 8 stops, nearest-neighbour + 2-opt beyond that |
| ✅ | Budget optimisation | Exact 0/1 knapsack over **cost and time**, plus a repair loop that checks the real route cost |
| ✅ | Multi-day plans | Days are filled in order (09:00-19:00 window by default) |
| ✅ | Expense estimate | Entry/activities, food, local transport, daily allowance, all shown as estimates |
| ✅ | Interactive dashboard | Leaflet map with numbered stops and per-day route lines, timeline, cost breakdown |
| ✅ | Saved trips | Plans are stored in SQLite and can be reopened with `/?trip=<id>` |

## How It Works

```text
  Reel link / caption / screenshots / video
                    |
        (link blocked? -> upload or paste)
                    v
   OCR (Tesseract) on images + sampled video frames
                    |
                    v
   Place-name matching (exact, hashtag, fuzzy) ──> verified against data/places.json
                    |
                    v
   You confirm the detected places, set budget, days, interests
                    |
                    v
   Knapsack selects places that fit budget + time (reserving travel)
                    |
                    v
   A* distances -> best visiting order -> day split
                    |
                    v
   Real cost / time check ──(over budget? reserve more or drop a place, repeat)
                    |
                    v
   Day-wise itinerary + map + cost breakdown
```

## The AI Techniques

### A\* search

A\* finds a least-cost path with `f(n) = g(n) + h(n)` where `g(n)` is the cost so far and `h(n)` the estimated remaining cost.

In TripViaReel:

- **Nodes:** places in a city. **Edges:** each place is linked to its 3 nearest neighbours (components are joined so the graph is connected).
- **Edge cost:** road kilometres = 1.3 × straight-line (haversine) distance.
- **Heuristic:** straight-line (haversine) distance to the goal. Because every edge costs at least the straight-line distance, the heuristic never overestimates, so it is **admissible** and A\* returns optimal paths. The tests check this for every pair of places in every city.
- **Output:** the node path (used to draw the route and to say "via ...") and its distance.

A\* answers "shortest path between two places". Deciding *which* places to visit and in *what order* is a separate problem, solved by the budget optimiser and the ordering step, as described next.

### Budget-constrained planning

1. **Selection:** exact dynamic-programming knapsack. Value = base + 2 per matching interest + up to 1.5 for how often the reel showed the place. Constraints: money (₹10 steps) and time (30-minute steps).
2. **Ordering:** A\* distances between all chosen places, then the cheapest open path (exact for ≤ 8 stops).
3. **Repair loop:** travel cost depends on the final route, so the knapsack cannot know it. The real route is checked; if it is over budget or over the day window, more money/time is reserved and selection is repeated, and if the selection stops changing the weakest place is dropped.

### Computer vision and OCR

- **OpenCV** samples up to 12 frames per video. A frame is skipped only if almost no pixels changed since the last kept frame (so a caption that changes over similar footage is still read).
- **Tesseract** runs two passes per frame: plain grayscale, and a "bright text" pass that isolates white overlay text, which is how most reels show place names.
- **Matching** uses exact phrases, hashtags (camel-case or lowercase), and fuzzy matching (difflib) to tolerate OCR errors such as `Hawa Maha1`.

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Language | Python 3.10+ | Everything on the back end |
| Search | A\* written from scratch (`app/algorithms/astar.py`) | Road-distance routing; Dijkstra included for comparison |
| Video / images | OpenCV, Pillow | Frame extraction and preprocessing |
| OCR | Tesseract via `pytesseract` | Text from screenshots and frames |
| Text processing | Python `re`, `difflib` | Place-name matching (no spaCy needed) |
| Geographic data | Offline gazetteer, `data/places.json` | Coordinates, fees, visit times (50 places, 4 cities) |
| Back end | Flask | API and page serving |
| Database | SQLite | Saved trips |
| Front end | HTML, CSS, JavaScript (no build step) | UI |
| Maps | Leaflet (bundled) + OpenStreetMap tiles | Route visualisation |
| Tests | pytest | 155 tests |

## Installation and Setup

### Prerequisites

- Python 3.10 or later
- **Tesseract OCR** (installed separately):
  - Windows: install from the [UB-Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki) and add it to `PATH`
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt install tesseract-ocr`
- A modern web browser (an internet connection is needed only for the map background tiles)

### Steps

```bash
git clone <your-github-repository-url>
cd TripViaReel

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
python -m app.main
```

Open **http://127.0.0.1:5000**.

Optional environment variables: `DATABASE_PATH` (default `data/tripviareel.db`), `PORT` (default `5000`), `TRIPVIAREEL_PLACES` (path to another places file).

### Run the tests

```bash
python -m pytest -q
```

## Using the App

1. **Your reel:** paste the reel link (optional), paste the caption, and/or drop screenshots or a screen recording of the reel.
2. **Places found:** tick the places you want. Low-confidence fuzzy matches (below 90%) and ambiguous matches start unticked. You can add any known place manually.
3. **Trip preferences:** set budget (₹), days, and interests, then **Plan my trip**.

### Example

| Parameter | Value |
|---|---|
| Reel | Hyderabad reel showing Charminar, Golconda Fort, Chowmahalla Palace, Hussain Sagar, Salar Jung Museum, Ramoji Film City, Paradise Biryani |
| Budget | ₹2,500 |
| Duration | 1 day |
| Interests | Sightseeing, food, photography |

The planner keeps Golconda Fort, Chowmahalla Palace, Charminar, Hussain Sagar and Paradise Biryani (about ₹1,180 including travel, ~25 km). It leaves out Ramoji Film City (7 hours and ₹1,500 cannot fit a busy day) and Salar Jung Museum (no time left in the day window), and says so in the "Left out" box.

## Project Structure

```text
TripViaReel/
├── app/
│   ├── main.py                    # Flask app factory and entry point
│   ├── routes/api.py              # /api/analyze, /api/plan, /api/places, /api/trips/<id>
│   ├── algorithms/astar.py        # A* and Dijkstra
│   ├── services/
│   │   ├── video_processor.py     # OpenCV frame sampling + Tesseract OCR
│   │   ├── reel_fetcher.py        # best-effort Instagram caption fetch (instagram.com only)
│   │   ├── location_extractor.py  # place-name detection and disambiguation
│   │   ├── geocoding.py           # offline gazetteer / geographic verification
│   │   ├── route_planner.py       # road graph, A* legs, visiting order
│   │   ├── budget_optimizer.py    # knapsack selection, cost/time model
│   │   └── itinerary_generator.py # repair loop, day split, schedule, totals
│   ├── models/db.py               # SQLite storage
│   ├── templates/index.html
│   └── static/                    # app.js, style.css, vendor/leaflet
├── data/places.json               # 50 places in Hyderabad, Jaipur, Goa, Delhi
├── tests/                         # 155 pytest tests
├── requirements.txt
├── .gitignore
└── README.md
```

## Adding More Places

Edit `data/places.json` and add an entry:

```json
{"id": "blr-lalbagh", "name": "Lalbagh Botanical Garden", "aliases": ["lalbagh"],
 "city": "Bengaluru", "lat": 12.9507, "lon": 77.5848,
 "tags": ["nature", "photography"], "category": "attraction",
 "spend": 30, "visit_hours": 2.0}
```

`tags` must come from the list in the file's `_meta`; `category` is `attraction` or `food`; `spend` is the typical per-person cost in ₹. Restart the app. The tests validate the dataset format.

## Testing and Evaluation

`python -m pytest -q` runs 155 tests covering:

- **A\*:** known shortest paths, same cost as Dijkstra on 150 random queries over 15 random graphs, fewer node expansions overall, unreachable goals, invalid input, and admissibility of the heuristic on the real place graphs.
- **Location extraction:** exact, alias, hashtag, fuzzy/OCR-noise matches, mention counting, duplicate names across cities, unknown pins, and false-positive checks on ordinary text.
- **Media:** OCR on generated screenshots and videos (including small images, corrupt files and blank images), frame sampling and duplicate skipping.
- **Budget optimiser:** equals brute force on 25 random instances, never exceeds budget or time, zero/negative budgets, empty input.
- **Itinerary:** the README example, totals adding up, day windows, multi-city reels, multi-day splits, infeasible budgets, route order no worse than input order, large selections.
- **API:** uploads (image, video, combined, wrong type, corrupt, oversize, too many, path-traversal names), URL validation (non-Instagram hosts rejected), blocked-link fallback, input validation, saved trips.

Suggested metrics for your report: location-extraction accuracy on your own set of reels, route cost versus input order, budget compliance, and A\* versus Dijkstra node expansions (the tests already compare cost; `SearchResult.expanded` gives the effort count).

## Limitations

- **Instagram links:** automatic retrieval of a reel is best-effort and normally blocked by Instagram. The app then asks for a screenshot, recording or caption. Link retrieval was only tested with the failure path and with a mocked success response, not against a live reel.
- **Fixed place list:** only the 50 places in `data/places.json` can be detected and planned. A place name not in the dataset is reported as "not in the offline place list" instead of being guessed. Online geocoding (Nominatim) is not included.
- **OCR:** works on text visible on screen or in the caption. It cannot recognise a landmark from its appearance.
- **Estimates:** fees, typical spend, visit durations and coordinates are approximate values written by hand for planning, not live prices. Verify before travelling. Opening hours and closed days are not modelled.
- **Distances:** road distances are estimated from a graph (1.3 × straight-line), not from real road data, so route lines are drawn between place coordinates.
- **One city per trip:** if a reel shows several cities, the city with most places is planned and the others are reported.
- **A\* scope:** A\* is optimal for each leg; the overall order is found by exhaustive search (≤ 8 stops) or a heuristic (more), and the selection by knapsack plus a repair loop, so the whole plan is a good solution rather than a proven global optimum when travel costs interact.
- Single traveller, no hotels, no public-transport timetables.

## Future Enhancements

- Online geocoding (Nominatim) and real road routing (OSRM) for places beyond the dataset
- Landmark recognition with an open-source vision model
- Several reels in one trip; PDF / shareable export
- Opening hours, restaurant and stay recommendations
- Official Meta API integration if access is granted

## Software Development Life Cycle

Built iteratively: requirements → design (modules above) → implementation → unit, integration, API and UI testing (headless-browser run of the full upload-to-itinerary flow) → deployment on a local Flask server → maintenance (extend the dataset, tune matching).

## License

No license has been selected yet. Add a `LICENSE` file before distributing the project for reuse. Leaflet is bundled under its BSD-2-Clause license; map tiles © OpenStreetMap contributors.

---

**TripViaReel**

*Save the reel. Discover the places. Let AI plan the trip.*
