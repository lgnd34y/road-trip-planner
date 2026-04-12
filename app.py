import anthropic
import json
import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# API key is set via environment variable on the hosting platform
DEFAULT_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# In-memory store for route data (avoids cookie size limits)
route_store = {}


def build_maps_url(addresses):
    from urllib.parse import quote
    encoded = [quote(a) for a in addresses]
    return "https://www.google.com/maps/dir/" + "/".join(encoded)


@app.route("/")
def index():
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] 👀 Someone visited the site — IP: {request.remote_addr}", flush=True)
    return render_template("index.html")


@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.json
    api_key     = data.get("api_key", "").strip()
    location    = data.get("location", "").strip()
    destination = data.get("destination", "").strip()
    duration    = data.get("duration", "").strip()
    preferences = data.get("preferences", "").strip()
    extra_info  = data.get("extra_info", "").strip()

    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or DEFAULT_API_KEY
    if not api_key or api_key == "your-api-key-here":
        return jsonify({"error": "Please add your Anthropic API key to app.py"}), 400
    if not location:
        return jsonify({"error": "Location is required"}), 400

    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] 🚗 Trip requested — From: {location} | Destination: {destination or 'any'} | Duration: {duration or 'any'} | IP: {request.remote_addr}", flush=True)

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = """You are an expert road trip planner. When given a starting location, provide 3 distinct road trip routes.

Return ONLY a valid JSON array with this exact structure (no markdown, no extra text):
[
  {
    "name": "Route name",
    "theme": "Theme description",
    "distance": "Total distance",
    "drive_time": "Total drive time",
    "best_time": "Best time of year",
    "highlight": "One don't-miss tip",
    "stops": [
      {
        "name": "Place Name",
        "address": "Full street address or City, State, Country",
        "description": "2-3 sentence description of what this place is and why it's worth visiting"
      }
    ]
  }
]

Rules:
- Each route's stops must start AND end at the starting location (circular route)
- Include 5-8 stops between start and end
- Provide real, specific addresses or at minimum City, State, Country for every stop
- If a specific destination is requested, make sure it appears in every route
- Tailor the route length and number of stops to match the requested time on the road
- Incorporate any additional details or preferences the user provides
- Return exactly 3 routes"""

    user_message = f"Starting location: {location}"
    if destination:
        user_message += f"\nMust include this destination: {destination}"
    if duration:
        user_message += f"\nDesired time on the road: {duration}"
    if preferences:
        user_message += f"\nPreferences/interests: {preferences}"
    if extra_info:
        user_message += f"\nAdditional details: {extra_info}"

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        raw = response.content[0].text.strip()
        print("---- RAW RESPONSE FROM CLAUDE ----")
        print(raw[:500])
        print("----------------------------------")

        # Strip any markdown code fences
        if "```" in raw:
            raw = raw.split("```", 1)[1]         # drop everything before first ```
            if raw.startswith("json"):
                raw = raw[4:]                     # drop the word "json"
            raw = raw.rsplit("```", 1)[0].strip() # drop closing ```

        # Find the JSON array even if there's surrounding text
        start = raw.find("[")
        end   = raw.rfind("]")
        if start != -1 and end != -1:
            raw = raw[start:end+1]

        routes = json.loads(raw)

        for route in routes:
            addresses = [s["address"] for s in route["stops"]]
            route["maps_url"] = build_maps_url(addresses)

        # Store routes and return a session ID so map page can retrieve them
        session_id = str(uuid.uuid4())
        route_store[session_id] = routes

        return jsonify({"routes": routes, "session_id": session_id})

    except anthropic.AuthenticationError:
        return jsonify({"error": "Invalid API key."}), 401
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse route data from Claude: {e}. Raw: {raw[:300]}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/map/<session_id>/<int:idx>")
def map_view(session_id, idx):
    routes = route_store.get(session_id)
    if not routes or idx < 0 or idx >= len(routes):
        return "Route not found. Please go back and generate routes first.", 404
    route = routes[idx]
    return render_template("map.html", route_json=json.dumps(route))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
