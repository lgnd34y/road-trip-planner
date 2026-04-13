import anthropic
import json
import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "road-trip-dev-" + str(uuid.uuid4()))

# Database — uses SQLite locally, PostgreSQL on Render if DATABASE_URL is set
database_url = os.environ.get("DATABASE_URL", "sqlite:///routes.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)

DEFAULT_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
route_store = {}  # in-memory store for freshly generated routes


# ── Models ──────────────────────────────────────────────────
class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    routes        = db.relationship("SavedRoute", backref="user", lazy=True, cascade="all, delete-orphan")


class SavedRoute(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    share_id   = db.Column(db.String(12), unique=True, nullable=False)
    name       = db.Column(db.String(200), nullable=False)
    route_data = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()


# ── Helpers ─────────────────────────────────────────────────
def build_maps_url(addresses):
    from urllib.parse import quote
    return "https://www.google.com/maps/dir/" + "/".join(quote(a) for a in addresses)


# ── Auth ─────────────────────────────────────────────────────
@app.route("/auth/signup", methods=["POST"])
def signup():
    data     = request.json
    username = data.get("username", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400

    user = User(username=username, email=email,
                password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({"success": True, "username": user.username})


@app.route("/auth/login", methods=["POST"])
def login():
    data     = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid username or password"}), 401

    login_user(user)
    return jsonify({"success": True, "username": user.username})


@app.route("/auth/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


# ── Save / share ─────────────────────────────────────────────
@app.route("/routes/save", methods=["POST"])
@login_required
def save_route():
    route = request.json.get("route")
    if not route:
        return jsonify({"error": "No route data"}), 400

    share_id = str(uuid.uuid4())[:10]
    saved = SavedRoute(user_id=current_user.id, share_id=share_id,
                       name=route.get("name", "My Route"),
                       route_data=json.dumps(route))
    db.session.add(saved)
    db.session.commit()
    return jsonify({"success": True, "share_id": share_id})


@app.route("/routes/saved")
@login_required
def saved_routes():
    routes = SavedRoute.query.filter_by(user_id=current_user.id)\
                             .order_by(SavedRoute.created_at.desc()).all()
    return render_template("saved.html", routes=routes)


@app.route("/routes/delete/<int:route_id>", methods=["POST"])
@login_required
def delete_route(route_id):
    route = SavedRoute.query.get_or_404(route_id)
    if route.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    db.session.delete(route)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/share/<share_id>")
def share_route(share_id):
    saved = SavedRoute.query.filter_by(share_id=share_id).first_or_404()
    return render_template("map.html", route_json=saved.route_data)


# ── Main ─────────────────────────────────────────────────────
@app.route("/")
def index():
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] 👀 Visit — IP: {request.remote_addr}", flush=True)
    return render_template("index.html")


@app.route("/recommend", methods=["POST"])
def recommend():
    data        = request.json
    api_key     = data.get("api_key", "").strip() or DEFAULT_API_KEY
    location    = data.get("location", "").strip()
    destination = data.get("destination", "").strip()
    duration    = data.get("duration", "").strip()
    nights      = data.get("nights", "").strip()
    extra_info  = data.get("extra_info", "").strip()

    if not api_key:
        return jsonify({"error": "Please add your Anthropic API key"}), 400
    if not location:
        return jsonify({"error": "Location is required"}), 400

    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] 🚗 From: {location} | Dest: {destination or 'any'} | Duration: {duration or 'any'} | Nights: {nights or 'any'} | IP: {request.remote_addr}", flush=True)

    client = anthropic.Anthropic(api_key=api_key)

    is_day_trip = nights == "0"

    if is_day_trip:
        system_prompt = """You are an expert road trip planner. Plan 3 distinct single-day road trip itineraries.

Stops are specific named attractions/landmarks (NOT cities). Traveller leaves and returns home same day.

Return ONLY a valid JSON array (no markdown, no extra text):
[
  {
    "name": "Route name",
    "theme": "Theme",
    "distance": "Total round-trip distance",
    "drive_time": "Total drive time",
    "best_time": "Best season",
    "highlight": "One tip",
    "stops": [
      {
        "name": "Specific Attraction Name",
        "address": "Address or City, State",
        "description": "1 sentence on what this is",
        "attractions": [
          {"name": "Activity or feature", "note": "Brief tip"},
          {"name": "Activity or feature", "note": "Brief tip"}
        ],
        "hotel": null,
        "restaurants": [
          {"name": "Restaurant name", "cuisine": "Type", "notes": "Brief tip"}
        ]
      }
    ],
    "itinerary": [
      {
        "day": 1,
        "title": "Day 1 — Full Day Out",
        "stops": ["Attraction A", "Attraction B"],
        "plan": "1 sentence day flow"
      }
    ]
  }
]

Rules:
- First and last stop = starting location
- Include 5-7 specific named attractions between start and end
- No hotels (day trip)
- Each stop has 2 activities in attractions array
- Return exactly 3 routes — be very concise"""
    else:
        system_prompt = """You are an expert road trip planner. Provide 3 distinct road trip routes.

Return ONLY a valid JSON array (no markdown, no extra text):
[
  {
    "name": "Route name",
    "theme": "Theme description",
    "distance": "Total distance",
    "drive_time": "Total drive time",
    "best_time": "Best season",
    "highlight": "One tip",
    "stops": [
      {
        "name": "City or Place Name",
        "address": "City, State, Country",
        "description": "1 sentence on why visit",
        "attractions": [
          {"name": "Attraction name", "note": "Brief tip"},
          {"name": "Attraction name", "note": "Brief tip"}
        ],
        "hotel": {
          "name": "Hotel name",
          "address": "Neighborhood",
          "notes": "Brief tip"
        },
        "restaurants": [
          {"name": "Restaurant name", "cuisine": "Type", "notes": "Brief tip"}
        ]
      }
    ],
    "itinerary": [
      {
        "day": 1,
        "title": "Day 1 — Title",
        "stops": ["Stop A", "Stop B"],
        "plan": "1 sentence plan"
      }
    ]
  }
]

Rules:
- Start AND end at starting location (circular route)
- Include 4-6 stops between start and end
- Use City, State, Country for addresses
- If a destination is requested, include it in every route
- Tailor stops and days to the requested nights/duration
- Include at most 7 itinerary entries total; combine days for longer trips
- If no nights specified, default to 3-night trip
- Non-home stops only need hotel + attractions
- Return exactly 3 routes — be very concise"""

    user_message = f"Starting location: {location}"
    if destination:
        user_message += f"\nMust include: {destination}"
    if nights:
        user_message += f"\nNumber of nights: {nights}"
    elif duration:
        user_message += f"\nTime on road: {duration}"
    if extra_info:
        user_message += f"\nDetails: {extra_info}"

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        raw = response.content[0].text.strip()

        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()

        start, end = raw.find("["), raw.rfind("]")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]

        routes = json.loads(raw)

        for route in routes:
            route["maps_url"] = build_maps_url([s["address"] for s in route["stops"]])

        session_id = str(uuid.uuid4())
        route_store[session_id] = routes
        return jsonify({"routes": routes, "session_id": session_id})

    except anthropic.AuthenticationError:
        return jsonify({"error": "Invalid API key."}), 401
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse route data: {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/map/<session_id>/<int:idx>")
def map_view(session_id, idx):
    routes = route_store.get(session_id)
    if not routes or idx < 0 or idx >= len(routes):
        return "Route not found. Please go back and generate routes first.", 404
    return render_template("map.html", route_json=json.dumps(routes[idx]))


@app.route("/routes/update/<int:route_id>", methods=["POST"])
@login_required
def update_route(route_id):
    saved = SavedRoute.query.get_or_404(route_id)
    if saved.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    new_route = request.json.get("route")
    if not new_route:
        return jsonify({"error": "No route data"}), 400
    saved.route_data = json.dumps(new_route)
    saved.name = new_route.get("name", saved.name)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/chat", methods=["POST"])
def chat_route():
    data    = request.json
    api_key = data.get("api_key", "").strip() or DEFAULT_API_KEY
    message = data.get("message", "").strip()
    route   = data.get("route")

    if not api_key:
        return jsonify({"reply": "No API key available for the AI assistant."}), 400
    if not message:
        return jsonify({"reply": "No message provided."}), 400

    client = anthropic.Anthropic(api_key=api_key)

    system = """You are a helpful road trip planning assistant. The user is editing a road trip route.

If the user asks to modify the route (add/remove/reorder stops, change hotels, rename route, etc.) respond ONLY with valid JSON:
{"reply": "Brief explanation of what you changed", "updated_route": <full updated route JSON with ALL original fields preserved>}

If the user is just asking a question with no route changes, respond ONLY with:
{"reply": "Your answer here"}

Preserve all fields (name, theme, distance, drive_time, best_time, highlight, stops, itinerary, maps_url) in updated_route.
Return ONLY valid JSON. No markdown."""

    user_content = f"Current route:\n{json.dumps(route)}\n\nUser: {message}"

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            system=system,
            messages=[{"role": "user", "content": user_content}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1:
            raw = raw[s:e+1]
        result = json.loads(raw)
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"reply": response.content[0].text[:300]})
    except Exception as ex:
        return jsonify({"reply": f"Error: {str(ex)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
