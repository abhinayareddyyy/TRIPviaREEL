# TripViaReel : AI-Powered Travel Itinerary Generator

**From Instagram Reels to personalized travel itineraries.**

TripViaReel is an AI-powered travel planning application that transforms travel inspiration into practical, budget-friendly travel itineraries. Users provide an Instagram Reel URL and, when needed, upload screenshots or video content. The system identifies potential destinations, verifies their geographic locations, and generates an optimized itinerary based on the user's budget, preferences, and trip duration.

The project combines **Artificial Intelligence, Natural Language Processing, Computer Vision, A* Search, and budget-constrained planning** to automate the travel planning process using free and open-source technologies.

## Problem Statement

Travel reels often showcase multiple destinations without providing a complete travel plan. Users must manually identify locations, research distances, calculate expenses, and determine the best order in which to visit each place.

TripViaReel addresses this problem by extracting destinations from supported travel content and using intelligent search and planning techniques to generate feasible itineraries within a specified budget.

## Objectives

- Extract potential destinations from travel reels using text and visual information.
- Identify and geographically verify the extracted locations.
- Generate personalized itineraries based on budget, interests, and trip duration.
- Implement the A* Search Algorithm for efficient route planning.
- Optimize destination selection under budget and time constraints.
- Display routes, destinations, and estimated expenses through an interactive interface.
- Build a functional prototype without mandatory paid APIs or subscriptions.

## Key Features

### 1. Reel-Based Travel Inspiration
Accept an Instagram Reel URL as the inspiration source, with optional screenshots or user-provided video files for content analysis.

### 2. Location Extraction
Use OCR, text processing, and optional computer vision to identify place names and relevant information from supported media.

### 3. Geographic Verification
Match extracted location candidates against geographic datasets to identify real-world places and their coordinates.

### 4. A* Search Algorithm
Represent destinations as nodes in a weighted graph and calculate efficient routes using the evaluation function:

\[
f(n)=g(n)+h(n)
\]

Where:

- \(g(n)\): Actual cost from the starting node to node \(n\).
- \(h(n)\): Estimated remaining cost from node \(n\) to the goal.
- \(f(n)\): Estimated total path cost through node \(n\).

The edge cost can represent distance or travel time, while the heuristic estimates the remaining distance or time.

### 5. Budget-Constrained Itinerary Planning
Select suitable destinations and experiences based on the user's available budget, preferences, and trip duration.

### 6. Route Optimization
Arrange selected destinations to reduce unnecessary travel and improve itinerary feasibility.

### 7. Expense Estimation
Estimate applicable costs, including transportation, food, entry tickets, and activities using available information or clearly identified estimates.

### 8. Interactive Travel Dashboard
Display the selected destinations, day-wise itinerary, route information, and estimated trip expenses.

## How It Works

```text
       User submits a Reel URL
                  |
                  v
      Upload screenshots/video
          (when necessary)
                  |
                  v
       Content Processing
     OCR + NLP + Visual Analysis
                  |
                  v
       Location Identification
                  |
                  v
      Geographic Verification
                  |
                  v
     Budget and Trip Preferences
                  |
                  v
       Destination Selection
                  |
                  v
        A* Route Search
                  |
                  v
       Budget and Time Checks
                  |
                  v
      Optimized Travel Itinerary
```

## AI Algorithms and Techniques

### A* Search

A* is a heuristic search algorithm that finds a least-cost path through a weighted graph under suitable heuristic conditions.

In TripViaReel:

- **Nodes:** Destinations or points of interest.
- **Edges:** Available travel connections between destinations.
- **Edge weights:** Estimated travel distance or time.
- **Heuristic:** Estimated remaining distance or travel time.
- **Output:** An efficient route between selected locations.

An admissible heuristic does not overestimate the true remaining cost. With suitable graph assumptions, this allows A* to find an optimal path to a goal.

**Note:** A* solves a route-search problem between specified nodes. Choosing the best combination and visiting order of multiple destinations under a budget is a separate optimization problem. TripViaReel combines route search with additional budget and itinerary-planning logic.

### Computer Vision and OCR

The content-processing module can use:

- **OpenCV:** Extract and process video frames.
- **Tesseract OCR:** Recognize text appearing in screenshots or frames.
- **NLP:** Identify candidate place names from extracted text.
- **Optional open-source vision models:** Help interpret visual scenes when text is insufficient.

The initial implementation can prioritize OCR and NLP before introducing more computationally demanding vision models.

### Budget-Constrained Planning

The itinerary planner evaluates destinations according to estimated expenses, user preferences, travel costs, and time requirements.

The objective is to maximize the usefulness of the selected experiences while respecting constraints such as:

- Total estimated cost must not exceed the user's budget.
- The itinerary must fit the available trip duration.
- Travel between selected destinations must be feasible.
- Recommended destinations should match the user's interests.

A* handles route search, while separate selection and validation logic handles the overall itinerary.

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Language | Python | Core application and algorithms |
| Search algorithm | A* implemented in Python | Route planning |
| Video processing | OpenCV | Frame extraction and image processing |
| OCR | Tesseract OCR | Text extraction from frames |
| NLP | spaCy / Python text processing | Candidate location extraction |
| Geographic data | OpenStreetMap | Place and map information |
| Geocoding | Nominatim | Convert place names into coordinates |
| Routing | OSRM | Road-route and travel-distance estimates |
| Frontend | HTML, CSS, JavaScript | User interface |
| Backend | Flask or FastAPI | Application logic and API endpoints |
| Database | SQLite | Local storage of trips and itineraries |
| Map visualization | Leaflet | Interactive maps |
| Version control | Git and GitHub | Source control |

The application is designed to use free and open-source software. Public APIs and datasets remain subject to their respective terms, attribution requirements, rate limits, and availability.

## Free-First Architecture

TripViaReel does not require a paid AI API for its initial prototype.

- **Instagram:** Reel URL serves as the inspiration reference. Media can be provided directly by the user.
- **OCR and video processing:** Run locally using open-source tools.
- **Location data:** Use permitted OpenStreetMap-based services.
- **Route search:** Implement A* locally in Python.
- **Storage:** Use SQLite locally.
- **Maps:** Use Leaflet with appropriate map data and attribution.
- **AI processing:** Start with local OCR and NLP, adding compatible open-source models if needed.

Direct automatic retrieval of Instagram Reel content is not assumed. Official Meta API integration may be considered later if the required access, permissions, and supported functionality are available.

## System Architecture

The project is divided into the following modules:

1. **Input Module:** Accept Reel URLs, supported media uploads, budget, interests, and trip duration.
2. **Content Processing Module:** Extract frames, captions, and available text.
3. **Location Extraction Module:** Detect candidate place names through OCR and NLP.
4. **Location Verification Module:** Resolve place names to geographic coordinates.
5. **Destination Selection Module:** Rank and filter destinations according to user preferences and constraints.
6. **Route Planning Module:** Apply A* search to find efficient paths between destinations.
7. **Budget Planning Module:** Estimate expenses and check budget feasibility.
8. **Itinerary Generation Module:** Arrange destinations into a practical day-wise plan.
9. **Visualization Module:** Display routes, destinations, and estimated costs.

## Project Structure

```text
TripViaReel/
├── app/
│   ├── main.py
│   ├── routes/
│   ├── services/
│   │   ├── video_processor.py
│   │   ├── location_extractor.py
│   │   ├── geocoding.py
│   │   ├── route_planner.py
│   │   ├── budget_optimizer.py
│   │   └── itinerary_generator.py
│   ├── algorithms/
│   │   └── astar.py
│   ├── models/
│   ├── templates/
│   └── static/
├── data/
├── tests/
│   ├── test_astar.py
│   ├── test_location_extraction.py
│   └── test_budget_optimizer.py
├── docs/
│   ├── requirements.md
│   ├── system_design.md
│   ├── database_design.md
│   └── test_plan.md
├── requirements.txt
├── .gitignore
└── README.md
```

This is the proposed structure; files can be added as the project is implemented.

## Installation and Setup

### Prerequisites

- Python 3.10 or later, compatible with the chosen dependencies
- Git
- Tesseract OCR
- A modern web browser

### 1. Clone the Repository

```bash
git clone <your-github-repository-url>
cd TripViaReel
```

Replace the placeholder with your repository URL.

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

On macOS or Linux:

```bash
source venv/bin/activate
```

### 3. Install Dependencies

Once `requirements.txt` is configured:

```bash
pip install -r requirements.txt
```

Install Tesseract OCR separately using the instructions for your operating system. Ensure its executable is accessible to the application.

### 4. Configure Environment Variables

Create a `.env` file if required by the implementation.

```env
DATABASE_PATH=data/tripviareel.db
```

Additional variables may be needed if optional external services are integrated.

### 5. Run the Application

For a Flask implementation:

```bash
python app/main.py
```

For a FastAPI implementation, if `app/main.py` exposes an ASGI application named `app`:

```bash
uvicorn app.main:app --reload
```

Use the command corresponding to the backend actually implemented.

**Setup note:** These instructions describe the proposed configuration. The repository must contain the corresponding modules and dependencies before the application can run successfully.

## Example

### User Input

| Parameter | Value |
|---|---|
| Reel | Travel reel featuring multiple destinations |
| Budget | ₹2,500 |
| Duration | 1 day |
| Interests | Sightseeing, food, photography |

### Expected Output

- Candidate locations extracted from the submitted media.
- Verified place names and geographic coordinates.
- A route calculated using A* search.
- A recommended visiting order.
- Estimated travel and activity expenses.
- A day-wise itinerary that satisfies the budget and duration constraints, where feasible.

Actual recommendations depend on the submitted content and available geographic and pricing data.

## Software Development Life Cycle

The project follows an iterative Software Development Life Cycle (SDLC).

### Phase 1: Requirement Analysis
Identify the target users, input requirements, expected output, functional requirements, and budget constraints.

### Phase 2: System Design
Design the architecture, processing pipeline, database schema, graph representation, and user interface.

### Phase 3: Implementation
Implement content processing, location extraction, A* search, budget optimization, and itinerary generation.

### Phase 4: Testing
Conduct unit, integration, system, and usability testing.

### Phase 5: Deployment
Package the application, configure dependencies, and deploy or run the system in a suitable environment.

### Phase 6: Maintenance
Improve extraction accuracy, fix errors, optimize algorithms, and incorporate user feedback.

## Testing and Evaluation

The system can be evaluated using the following metrics:

- **Location extraction accuracy:** Percentage of correctly identified locations.
- **Route cost:** Total estimated distance or travel time.
- **Budget compliance:** Whether the estimated trip expense stays within the budget.
- **Itinerary feasibility:** Whether the selected places fit the available duration.
- **Execution time:** Time required to process content and generate the itinerary.
- **Algorithm comparison:** Compare A* with Dijkstra's algorithm on suitable route-search tasks.

Tests should include reels with missing location labels, duplicate place names, invalid inputs, unreachable destinations, and budgets that cannot accommodate all requested destinations.

## Limitations

- Direct Reel retrieval is subject to Instagram's access restrictions.
- OCR may fail when text is unclear or absent.
- Visually recognizing a landmark may require a dedicated vision model.
- Multiple places can have identical or similar names.
- Expense estimates may differ from actual prices.
- Public geocoding and routing services impose usage restrictions.
- A* route optimality does not automatically imply global optimality for the entire multi-stop itinerary.

## Future Enhancements

- More accurate landmark recognition using open-source vision models.
- Support for multiple reels in a single trip.
- Multi-day itinerary generation.
- Live traffic and public transportation integration.
- Restaurant and accommodation recommendations.
- Group travel and shared itineraries.
- Better optimization across budget, distance, and available time.
- Export itineraries as PDF or shareable links.
- Optional official Meta API integration, subject to access eligibility and permissions.

## Project Status

**Project Type:** Artificial Intelligence / Software Engineering Academic Project

**Core Focus:** Computer vision, location extraction, A* search, and budget-constrained itinerary planning.

**Development Stage:** In progress.

Features should be marked as completed only after implementation and testing.

## License

No license has been selected yet. Add an appropriate `LICENSE` file before distributing the project for reuse.

---

**TripViaReel**

*Save the reel. Discover the places. Let AI plan the trip.*
