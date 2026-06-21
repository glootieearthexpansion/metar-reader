# METAR Reader

A small Flask app that turns a cryptic METAR weather report into a plain-English summary. Type in an airport's ICAO code (e.g. `KJFK`) and get back something like:

> Broken clouds at 25,000 ft, 73°F, wind from the WNW (300°) at 13 mph, visibility 10 statute miles.

Weather data comes live from the [aviationweather.gov](https://aviationweather.gov/data/api/) METAR API.

## Setup

1. **Clone the repo**

   ```bash
   git clone https://github.com/glootieearthexpansion/metar-reader.git
   cd metar-reader
   ```

2. **Create a virtual environment (recommended)**

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the app**

   ```bash
   python app.py
   ```

5. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser, enter a 4-letter ICAO airport code (e.g. `KJFK`, `KLAX`, `EGLL`), and click **Get Weather**.

## How it works

- `app.py` — Flask routes. `/` serves the page; `/api/metar?code=XXXX` fetches the raw METAR text from aviationweather.gov and returns the decoded result as JSON.
- `metar_decoder.py` — parses the raw METAR token by token (wind, visibility, sky cover, weather phenomena, temperature/dew point, altimeter) and builds a plain-English summary, a detail table, and a weather icon.
- `templates/` / `static/` — the single-page UI (HTML, JS, CSS) that calls the API and renders the result without a page reload.

## Notes

- Use the 4-letter ICAO code, not the 3-letter IATA code (e.g. `KJFK`, not `JFK`).
- If a station has no current report, or the code doesn't exist, the app shows a friendly error instead of failing.
