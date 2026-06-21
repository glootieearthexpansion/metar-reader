"""Flask app: look up an airport's METAR and show it in plain English."""
import re

import requests
from flask import Flask, jsonify, render_template, request

from metar_decoder import decode_metar

app = Flask(__name__)

AVIATIONWEATHER_API = "https://aviationweather.gov/api/data/metar"
CODE_RE = re.compile(r"^[A-Za-z0-9]{3,4}$")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/metar")
def api_metar():
    code = request.args.get("code", "").strip().upper()

    if not code:
        return jsonify({"error": "Please enter an airport code."}), 400
    if not CODE_RE.match(code):
        return jsonify({"error": "Enter a valid airport code, e.g. KJFK."}), 400

    try:
        resp = requests.get(
            AVIATIONWEATHER_API,
            params={"ids": code, "format": "raw"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "Could not reach the weather service. Please try again later."}), 502

    raw = resp.text.strip()
    if not raw:
        return jsonify({
            "error": f"No METAR data found for '{code}'. Check the airport code "
                     "(use the 4-letter ICAO code, e.g. KJFK for New York JFK)."
        }), 404

    decoded = decode_metar(raw)
    return jsonify({
        "station": code,
        "raw": raw,
        "summary": decoded["summary"],
        "details": decoded["details"],
        "icon": decoded["icon"],
    })


if __name__ == "__main__":
    app.run(debug=True)
