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
        "address": "City, State, Country",
        "description": "1-2 sentences on why this stop is worth visiting",
        "hotel": {
          "name": "Hotel or lodging name",
          "address": "Neighborhood or city",
          "notes": "Brief tip"
        },
        "restaurants": [
          {
            "name": "Restaurant name",
            "cuisine": "Cuisine type",
            "notes": "Brief tip"
          }
        ]
      }
    ],
    "itinerary": [
      {
        "day": 1,
        "title": "Day 1 — Departure",
        "stops": ["Stop Name A", "Stop Name B"],
        "plan": "1-2 sentences on what to do and where to sleep"
      }
    ]
  }
]

Rules:
- Each route's stops must start AND end at the starting location (circular route)
- Include 5-7 stops between start and end
- Provide City, State, Country for every stop address
- If a specific destination is requested, make sure it appears in every route
- Tailor the route length, stops, and itinerary days to match the requested nights/duration
- The itinerary must have exactly as many days as the number of nights + 1 (e.g. 3 nights = 4 days, last day returns home)
- If no nights specified, use the duration or default to a 3-night trip
- Every non-home stop must include a hotel suggestion and 1 restaurant suggestion
- Incorporate any additional details the user provides
- Return exactly 3 routes — be concise to stay within token limits"""

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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
