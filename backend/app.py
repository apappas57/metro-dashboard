import os
import time
import hmac
import hashlib
from urllib.parse import urlencode
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

PTV_BASE = "https://timetableapi.ptv.vic.gov.au"
DEV_ID = os.getenv("PTV_DEV_ID", "")
API_KEY = os.getenv("PTV_API_KEY", "")
USE_MOCK = not DEV_ID or not API_KEY


# --- PTV request signing ---

def ptv_request(path, params=None):
    if params is None:
        params = {}
    params["devid"] = DEV_ID
    query = path + "?" + urlencode(params)
    raw = query.encode("utf-8")
    key = API_KEY.encode("utf-8")
    signature = hmac.new(key, raw, hashlib.sha1).hexdigest().upper()
    url = PTV_BASE + query + "&signature=" + signature
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


# --- Mock data (used until PTV API key arrives) ---

MOCK_DEPARTURES = [
    {"line": "Frankston", "destination": "Frankston", "departs": "2 min", "platform": "1", "status": "On time"},
    {"line": "Sandringham", "destination": "Sandringham", "departs": "5 min", "platform": "2", "status": "On time"},
    {"line": "Glen Waverley", "destination": "Glen Waverley", "departs": "8 min", "platform": "3", "status": "Delayed"},
    {"line": "Pakenham", "destination": "Pakenham", "departs": "11 min", "platform": "1", "status": "On time"},
    {"line": "Cranbourne", "destination": "Cranbourne", "departs": "14 min", "platform": "4", "status": "On time"},
]

MOCK_LINES = [
    {"name": "Alamein",        "status": "good"},
    {"name": "Belgrave",       "status": "good"},
    {"name": "Cranbourne",     "status": "good"},
    {"name": "Frankston",      "status": "good"},
    {"name": "Glen Waverley",  "status": "disrupted"},
    {"name": "Hurstbridge",    "status": "good"},
    {"name": "Lilydale",       "status": "good"},
    {"name": "Mernda",         "status": "good"},
    {"name": "Pakenham",       "status": "good"},
    {"name": "Sandringham",    "status": "good"},
    {"name": "Stony Point",    "status": "works"},
    {"name": "Sunbury",        "status": "good"},
    {"name": "Upfield",        "status": "good"},
    {"name": "Werribee",       "status": "good"},
    {"name": "Williamstown",   "status": "good"},
]

MOCK_DISRUPTIONS = [
    {
        "title": "Glen Waverley line delays",
        "description": "Trains running 10-15 minutes late due to a track fault near Syndal.",
        "severity": "high",
        "updated": "10 mins ago"
    },
    {
        "title": "Stony Point line — buses replace trains",
        "description": "Buses replacing trains between Frankston and Stony Point all weekend.",
        "severity": "medium",
        "updated": "2 hrs ago"
    },
    {
        "title": "Platform works at Flinders Street",
        "description": "Platform 9 and 10 closed for maintenance. Allow extra time.",
        "severity": "low",
        "updated": "1 day ago"
    },
]


# --- Routes ---
@app.route("/api/weather")
def weather():
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=-37.8136&longitude=144.9631"
            "&current=temperature_2m,precipitation,windspeed_10m,weathercode"
            "&timezone=Australia/Melbourne"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()["current"]

        code = data["weathercode"]
        if code == 0:
            condition = "Clear"
        elif code in [1, 2, 3]:
            condition = "Cloudy"
        elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            condition = "Rainy"
        elif code in [71, 73, 75]:
            condition = "Snowy"
        elif code in [95, 96, 99]:
            condition = "Stormy"
        else:
            condition = "Overcast"

        rain = data["precipitation"]
        wind = data["windspeed_10m"]

        if condition in ["Rainy", "Stormy"] or wind > 50:
            impact = "high"
            impact_msg = "Weather may cause delays on exposed lines"
        elif condition in ["Cloudy", "Overcast"] or wind > 30:
            impact = "medium"
            impact_msg = "Minor weather impact possible"
        else:
            impact = "low"
            impact_msg = "Good conditions for travel"

        return jsonify({
            "temp": round(data["temperature_2m"]),
            "condition": condition,
            "rain": rain,
            "wind": round(wind),
            "impact": impact,
            "impact_msg": impact_msg,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/patronage")
def patronage():
    # Average patronage index by hour at Flinders Street (0=quiet, 100=peak)
    # Derived from Transport Victoria annual patronage data
    weekday = [
        {"hour": "5am",  "label": "5am",  "index": 8,  "rating": "quiet"},
        {"hour": "6am",  "label": "6am",  "index": 35, "rating": "moderate"},
        {"hour": "7am",  "label": "7am",  "index": 78, "rating": "busy"},
        {"hour": "8am",  "label": "8am",  "index": 100,"rating": "peak"},
        {"hour": "9am",  "label": "9am",  "index": 65, "rating": "busy"},
        {"hour": "10am", "label": "10am", "index": 38, "rating": "moderate"},
        {"hour": "11am", "label": "11am", "index": 32, "rating": "moderate"},
        {"hour": "12pm", "label": "12pm", "index": 35, "rating": "moderate"},
        {"hour": "1pm",  "label": "1pm",  "index": 33, "rating": "moderate"},
        {"hour": "2pm",  "label": "2pm",  "index": 36, "rating": "moderate"},
        {"hour": "3pm",  "label": "3pm",  "index": 52, "rating": "moderate"},
        {"hour": "4pm",  "label": "4pm",  "index": 72, "rating": "busy"},
        {"hour": "5pm",  "label": "5pm",  "index": 95, "rating": "peak"},
        {"hour": "6pm",  "label": "6pm",  "index": 88, "rating": "peak"},
        {"hour": "7pm",  "label": "7pm",  "index": 55, "rating": "busy"},
        {"hour": "8pm",  "label": "8pm",  "index": 35, "rating": "moderate"},
        {"hour": "9pm",  "label": "9pm",  "index": 22, "rating": "quiet"},
        {"hour": "10pm", "label": "10pm", "index": 15, "rating": "quiet"},
    ]
    now = datetime.now()
    current_hour = now.strftime("%-I%p").lower()
    return jsonify({
        "hours": weekday,
        "current_hour": current_hour,
        "is_weekend": now.weekday() >= 5
    })

@app.route("/api/departures")
def departures():
    if USE_MOCK:
        return jsonify({"source": "mock", "departures": MOCK_DEPARTURES})
    try:
        # Flinders Street Station = stop 1071, Metro = route_type 0
        data = ptv_request("/v3/departures/route_type/0/stop/1071", {"max_results": 10})
        return jsonify({"source": "live", "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lines")
def lines():
    if USE_MOCK:
        return jsonify({"source": "mock", "lines": MOCK_LINES})
    try:
        data = ptv_request("/v3/routes", {"route_types": 0})
        return jsonify({"source": "live", "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/disruptions")
def disruptions():
    if USE_MOCK:
        return jsonify({"source": "mock", "disruptions": MOCK_DISRUPTIONS})
    try:
        data = ptv_request("/v3/disruptions", {"route_types": 0})
        return jsonify({"source": "live", "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "mode": "mock" if USE_MOCK else "live"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)