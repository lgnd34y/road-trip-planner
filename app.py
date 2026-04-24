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
    edit_token = db.Column(db.String(36), unique=True, nullable=True)
    name       = db.Column(db.String(200), nullable=False)
    route_data = db.Column(db.Text, nullable=False)
    is_public  = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SharedRoute(db.Model):
    """A route sent from one user directly to another user's inbox."""
    id            = db.Column(db.Integer, primary_key=True)
    from_user_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    to_user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    from_username = db.Column(db.String(80),  nullable=False)   # denormalised for easy display
    route_name    = db.Column(db.String(200), nullable=False)
    route_data    = db.Column(db.Text,        nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


class TripGroup(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name       = db.Column(db.String(200), nullable=False)
    route_ids  = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RouteReview(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    route_id   = db.Column(db.Integer, db.ForeignKey("saved_route.id"), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    username   = db.Column(db.String(80), nullable=False)
    rating     = db.Column(db.Integer, nullable=False)   # 1-5
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TripJournal(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    route_id    = db.Column(db.Integer, db.ForeignKey("saved_route.id"), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content     = db.Column(db.Text, nullable=True)
    stop_ratings = db.Column(db.Text, nullable=True)  # JSON: {"0": 4, "1": 5, ...}
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()

# Migrate: add is_public column if it doesn't exist (SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS)
with app.app_context():
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE saved_route ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT 0"))
            conn.commit()
    except Exception:
        pass  # column already exists

# Migrate: create new tables if they don't exist
with app.app_context():
    db.create_all()  # safe to call again — creates new tables, skips existing


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


@app.route("/sw.js")
def service_worker():
    from flask import send_from_directory
    response = send_from_directory("static", "sw.js")
    response.headers["Content-Type"] = "application/javascript"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


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
    inbox  = SharedRoute.query.filter_by(to_user_id=current_user.id)\
                              .order_by(SharedRoute.created_at.desc()).all()
    for item in inbox:
        try:
            rd = json.loads(item.route_data)
            mid = rd.get("stops", [])[1:-1][:3]
            item.stop_preview = " → ".join(s.get("name", "") for s in mid if s.get("name"))
        except Exception:
            item.stop_preview = ""
    return render_template("saved.html", routes=routes, inbox=inbox)


@app.route("/routes/delete/<int:route_id>", methods=["POST"])
@login_required
def delete_route(route_id):
    route = SavedRoute.query.get_or_404(route_id)
    if route.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    db.session.delete(route)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/routes/share-to-user", methods=["POST"])
@login_required
def share_to_user():
    data     = request.json
    username = data.get("username", "").strip().lower()
    route    = data.get("route")

    if not username or not route:
        return jsonify({"error": "Username and route are required"}), 400

    target = User.query.filter(
        db.func.lower(User.username) == username
    ).first()
    if not target:
        return jsonify({"error": f"No account found with username \"{username}\""}), 404
    if target.id == current_user.id:
        return jsonify({"error": "You can't share a route with yourself"}), 400

    shared = SharedRoute(
        from_user_id  = current_user.id,
        to_user_id    = target.id,
        from_username = current_user.username,
        route_name    = route.get("name", "Shared Route"),
        route_data    = json.dumps(route)
    )
    db.session.add(shared)
    db.session.commit()
    return jsonify({"success": True, "to": target.username})


@app.route("/routes/inbox/save/<int:shared_id>", methods=["POST"])
@login_required
def inbox_save(shared_id):
    shared = SharedRoute.query.get_or_404(shared_id)
    if shared.to_user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    saved = SavedRoute(
        user_id    = current_user.id,
        share_id   = str(uuid.uuid4())[:10],
        name       = shared.route_name,
        route_data = shared.route_data
    )
    db.session.add(saved)
    db.session.delete(shared)
    db.session.commit()
    return jsonify({"success": True, "id": saved.id, "name": saved.name,
                    "share_id": saved.share_id,
                    "created_at": saved.created_at.strftime("%b %d, %Y")})


@app.route("/routes/inbox/dismiss/<int:shared_id>", methods=["POST"])
@login_required
def inbox_dismiss(shared_id):
    shared = SharedRoute.query.get_or_404(shared_id)
    if shared.to_user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    db.session.delete(shared)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/share/<share_id>")
def share_route(share_id):
    saved = SavedRoute.query.filter_by(share_id=share_id).first_or_404()
    return render_template("map.html", route_json=saved.route_data)


@app.route("/print")
def print_view():
    return render_template("print.html")


# ── Main ─────────────────────────────────────────────────────
@app.route("/")
def index():
    try:
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] Visit -- IP: {request.remote_addr}", flush=True)
    except Exception:
        pass
    inbox_count = 0
    if current_user.is_authenticated:
        inbox_count = SharedRoute.query.filter_by(to_user_id=current_user.id).count()
    return render_template("index.html", inbox_count=inbox_count)


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

    try:
        print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] Trip -- From: {location} | Dest: {destination or 'any'} | Duration: {duration or 'any'} | Nights: {nights or 'any'} | IP: {request.remote_addr}", flush=True)
    except Exception:
        pass

    client = anthropic.Anthropic(api_key=api_key, timeout=25.0)

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
    "highlight": "One vivid sentence on what makes this route unmissable — lead with the experience, not a list of features",
    "stops": [
      {
        "name": "Specific Attraction Name",
        "address": "Address or City, State",
        "description": "1 sentence — lead with what the traveler experiences or feels here, not just what exists. Be specific and vivid, not brochure-generic.",
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
        "plan": "1 sentence day flow — make it feel like a real day, not a schedule"
      }
    ],
    "flights": []
  }
]

Rules:
- First and last stop = starting location
- Include 5-7 specific named attractions between start and end
- No hotels (day trip)
- Each stop has 2 activities in attractions array
- flights is always [] for day trips
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
    "highlight": "One vivid sentence on what makes this route unmissable — lead with the experience, not a list of features",
    "stops": [
      {
        "name": "City or Place Name",
        "address": "City, State, Country",
        "description": "1 sentence — lead with what the traveler experiences or feels here, not just what exists. Be specific and vivid, not brochure-generic.",
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
        "plan": "1 sentence — describe the day like you're telling a friend, not writing a schedule"
      }
    ],
    "flights": [
      {
        "from": "Stop Name A",
        "to": "Stop Name B",
        "reason": "e.g. 9h drive vs ~1.5h flight",
        "search_url": "https://www.google.com/travel/flights?q=Flights+from+CityA+to+CityB"
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
- flights: add an entry for any leg between consecutive stops that likely exceeds 5 hours driving. Use [] if all legs are short driving distances.
- For flights search_url use: https://www.google.com/travel/flights?q=Flights+from+[City+A]+to+[City+B] (URL-encode city names with +)
- Return exactly 3 routes — be very concise"""

    # For long trips, add an explicit compression instruction
    nights_int = 0
    try:
        nights_int = int(nights) if nights else 0
    except ValueError:
        pass

    user_message = f"Starting location: {location}"
    if destination:
        user_message += f"\nMust include: {destination}"
    if nights:
        user_message += f"\nNumber of nights: {nights}"
    elif duration:
        user_message += f"\nTime on road: {duration}"
    if extra_info:
        user_message += f"\nDetails: {extra_info}"

    # Keep responses short to avoid timeouts
    if nights_int >= 7:
        user_message += f"\nIMPORTANT: This is a {nights_int}-night trip. Use max 5 stops total. Limit each description/note to 1 short sentence. Group every 2-3 nights into a single itinerary entry (so max 5 itinerary entries total). Be extremely concise."
    else:
        user_message += "\nIMPORTANT: Be very concise — 1 short sentence per description/note. Do not over-explain."

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=5000,
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

        try:
            routes = json.loads(raw)
        except json.JSONDecodeError:
            # Truncated — recover complete route objects that were fully written
            import re
            routes = []
            for m in re.finditer(r'\{[^{}]*"stops"\s*:\s*\[[\s\S]*?\]\s*[^{}]*\}', raw):
                try:
                    routes.append(json.loads(m.group()))
                except Exception:
                    pass
            if not routes:
                raise

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
    # "inline" means route data is carried in the URL hash — just serve the shell
    if session_id == "inline":
        return render_template("map.html", route_json="null")
    routes = route_store.get(session_id)
    if not routes or idx < 0 or idx >= len(routes):
        return render_template("map.html", route_json="null")
    return render_template("map.html", route_json=json.dumps(routes[idx]))


@app.route("/routes/copy/<int:route_id>", methods=["POST"])
@login_required
def copy_route(route_id):
    original = SavedRoute.query.get_or_404(route_id)
    if original.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    copy = SavedRoute(
        user_id=current_user.id,
        share_id=str(uuid.uuid4())[:10],
        name="Copy of " + original.name,
        route_data=original.route_data
    )
    db.session.add(copy)
    db.session.commit()
    return jsonify({"success": True, "id": copy.id, "name": copy.name, "share_id": copy.share_id,
                    "created_at": copy.created_at.strftime("%b %d, %Y")})


@app.route("/routes/invite/<int:route_id>", methods=["POST"])
@login_required
def invite_route(route_id):
    saved = SavedRoute.query.get_or_404(route_id)
    if saved.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    if not saved.edit_token:
        saved.edit_token = str(uuid.uuid4())
        db.session.commit()
    return jsonify({"edit_token": saved.edit_token})


@app.route("/routes/revoke/<int:route_id>", methods=["POST"])
@login_required
def revoke_invite(route_id):
    saved = SavedRoute.query.get_or_404(route_id)
    if saved.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    saved.edit_token = None
    db.session.commit()
    return jsonify({"success": True})


@app.route("/collab/<edit_token>")
def collab_edit(edit_token):
    saved = SavedRoute.query.filter_by(edit_token=edit_token).first_or_404()
    return render_template("collab.html", route_name=saved.name,
                           route_json=saved.route_data, edit_token=edit_token)


@app.route("/routes/collab-save/<edit_token>", methods=["POST"])
def collab_save(edit_token):
    saved = SavedRoute.query.filter_by(edit_token=edit_token).first_or_404()
    new_route = request.json.get("route")
    if not new_route:
        return jsonify({"error": "No route data"}), 400
    saved.route_data = json.dumps(new_route)
    saved.name = new_route.get("name", saved.name)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/costs", methods=["POST"])
def estimate_costs():
    data    = request.json
    api_key = data.get("api_key", "").strip() or DEFAULT_API_KEY
    route   = data.get("route")

    if not api_key:
        return jsonify({"error": "No API key"}), 400
    if not route:
        return jsonify({"error": "No route"}), 400

    stops = [s.get("address", "") for s in route.get("stops", []) if s.get("address")]
    region = stops[0] if stops else "USA"

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""A road trip is being planned through these locations: {', '.join(stops[:6])}.

Provide realistic CURRENT price estimates for this region. Return ONLY this JSON (no markdown):
{{
  "gas_price": <average fuel price in USD per gallon (or USD-equivalent per gallon if metric country)>,
  "mpg": <typical car fuel efficiency in MPG for a standard sedan>,
  "hotel_rate": <typical mid-range hotel per night in USD>,
  "food_rate": <typical daily food budget per person in USD (mix of restaurants and casual)>,
  "extras_rate": <typical daily activities/extras per person in USD>,
  "currency_note": "<brief note like 'Prices converted to USD from EUR' or 'US prices'>",
  "notes": "<1 sentence context e.g. 'Hotel rates reflect peak summer season in this region'>"
}}

Base these on real current prices for the specific region, not generic defaults."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1: raw = raw[s:e+1]
        return jsonify(json.loads(raw))
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/api/packing-list", methods=["POST"])
def packing_list():
    data    = request.json
    api_key = data.get("api_key", "").strip() or DEFAULT_API_KEY
    route   = data.get("route")

    if not api_key:
        return jsonify({"error": "No API key"}), 400
    if not route:
        return jsonify({"error": "No route"}), 400

    stops  = [s.get("name", "") for s in route.get("stops", [])]
    theme  = route.get("theme", "")
    nights = len(route.get("itinerary", [])) or 1

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""Create a practical packing list for this road trip:
Route theme: {theme}
Stops: {', '.join(stops[:8])}
Duration: {nights} night(s)

Return ONLY valid JSON (no markdown):
{{
  "categories": [
    {{"name": "Category Name", "items": ["item 1", "item 2", "item 3"]}}
  ]
}}

Include 5-7 categories (e.g. Clothing, Toiletries, Documents, Tech, Snacks & Drinks, Emergency Kit, Activity Gear). Tailor items to the route's theme and duration. Be practical and specific."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1: raw = raw[s:e+1]
        return jsonify(json.loads(raw))
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/explore")
def explore():
    routes = SavedRoute.query.filter_by(is_public=True)\
                             .order_by(SavedRoute.created_at.desc()).limit(60).all()
    parsed = []
    for r in routes:
        try:
            data = json.loads(r.route_data)
            parsed.append({
                "id": r.id,
                "name": r.name,
                "share_id": r.share_id,
                "created_at": r.created_at.strftime("%b %d, %Y"),
                "theme": data.get("theme", ""),
                "distance": data.get("distance", ""),
                "drive_time": data.get("drive_time", ""),
                "best_time": data.get("best_time", ""),
                "highlight": data.get("highlight", ""),
                "stop_count": len(data.get("stops", [])),
                "avg_rating": round(float(db.session.query(db.func.avg(RouteReview.rating)).filter_by(route_id=r.id).scalar() or 0), 1),
                "review_count": RouteReview.query.filter_by(route_id=r.id).count(),
            })
        except Exception:
            pass
    return render_template("explore.html", routes=parsed)


@app.route("/routes/toggle-public/<int:route_id>", methods=["POST"])
@login_required
def toggle_public(route_id):
    saved = SavedRoute.query.get_or_404(route_id)
    if saved.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    saved.is_public = not saved.is_public
    db.session.commit()
    return jsonify({"success": True, "is_public": saved.is_public})


@app.route("/trips")
@login_required
def trips():
    groups = TripGroup.query.filter_by(user_id=current_user.id)\
                            .order_by(TripGroup.created_at.desc()).all()
    saved  = SavedRoute.query.filter_by(user_id=current_user.id)\
                             .order_by(SavedRoute.created_at.desc()).all()
    # Build name lookup
    route_names = {r.id: r.name for r in saved}
    parsed_groups = []
    for g in groups:
        try:
            ids = json.loads(g.route_ids)
        except Exception:
            ids = []
        parsed_groups.append({
            "id": g.id,
            "name": g.name,
            "created_at": g.created_at.strftime("%b %d, %Y"),
            "routes": [{"id": rid, "name": route_names.get(rid, "(deleted)")} for rid in ids],
        })
    saved_list = [{"id": r.id, "name": r.name} for r in saved]
    return render_template("trips.html", groups=parsed_groups, saved_routes=saved_list)


@app.route("/trips/create", methods=["POST"])
@login_required
def create_trip():
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    group = TripGroup(user_id=current_user.id, name=name)
    db.session.add(group)
    db.session.commit()
    return jsonify({"success": True, "id": group.id, "name": group.name})


@app.route("/trips/<int:group_id>/add", methods=["POST"])
@login_required
def trip_add_route(group_id):
    group = TripGroup.query.get_or_404(group_id)
    if group.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    route_id = request.json.get("route_id")
    try:
        ids = json.loads(group.route_ids)
    except Exception:
        ids = []
    if route_id not in ids:
        ids.append(route_id)
    group.route_ids = json.dumps(ids)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/trips/<int:group_id>/remove", methods=["POST"])
@login_required
def trip_remove_route(group_id):
    group = TripGroup.query.get_or_404(group_id)
    if group.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    route_id = request.json.get("route_id")
    try:
        ids = json.loads(group.route_ids)
    except Exception:
        ids = []
    ids = [i for i in ids if i != route_id]
    group.route_ids = json.dumps(ids)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/trips/<int:group_id>/delete", methods=["POST"])
@login_required
def delete_trip(group_id):
    group = TripGroup.query.get_or_404(group_id)
    if group.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    db.session.delete(group)
    db.session.commit()
    return jsonify({"success": True})


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


@app.route("/routes/notes/<int:route_id>", methods=["POST"])
@login_required
def save_route_notes(route_id):
    saved = SavedRoute.query.get_or_404(route_id)
    if saved.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    note = request.json.get("note", "")[:2000]
    try:
        data = json.loads(saved.route_data)
        data["user_notes"] = note
        saved.route_data = json.dumps(data)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/guided/suggestions", methods=["POST"])
def guided_suggestions():
    data     = request.json
    api_key  = data.get("api_key", "").strip() or DEFAULT_API_KEY
    location = data.get("location", "").strip()

    if not api_key:
        return jsonify({"error": "No API key"}), 400
    if not location:
        return jsonify({"error": "Location required"}), 400

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""Suggest 6 diverse road trip destinations reachable from {location}. Return ONLY valid JSON (no markdown):
{{
  "suggestions": [
    {{
      "name": "City or region name only (e.g. 'Sedona, AZ' or 'Rocky Mountain National Park')",
      "theme": "2-3 word vibe (e.g. 'Desert Adventure' or 'Coastal Escape')",
      "description": "One sentence — lead with what the traveler experiences or feels, not just what exists there. Be specific and vivid, not brochure-generic.",
      "emoji": "Single relevant emoji"
    }}
  ]
}}
Vary distance, terrain, and vibe (coastal, mountain, city, rural, historical, adventure). Use real place names only — no marketing slogans."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1: raw = raw[s:e+1]
        return jsonify(json.loads(raw))
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/chat", methods=["POST"])
def chat_route():
    data    = request.json
    api_key = data.get("api_key", "").strip() or DEFAULT_API_KEY
    message = data.get("message", "").strip()
    route   = data.get("route")    # single route (edit panel)
    routes  = data.get("routes")   # all routes (global chat)

    if not api_key:
        return jsonify({"reply": "No API key available for the AI assistant."}), 400
    if not message:
        return jsonify({"reply": "No message provided."}), 400

    client = anthropic.Anthropic(api_key=api_key)

    if route:
        # Single-route editing context
        system = """You are a helpful road trip planning assistant. The user is editing a road trip route.

If the user asks to modify the route (add/remove/reorder stops, change hotels, rename route, etc.) respond ONLY with valid JSON:
{"reply": "Brief explanation of what you changed", "updated_route": <full updated route JSON with ALL original fields preserved>}

If the user is just asking a question with no route changes, respond ONLY with:
{"reply": "Your answer here"}

Preserve all fields (name, theme, distance, drive_time, best_time, highlight, stops, itinerary, maps_url, flights) in updated_route.
Return ONLY valid JSON. No markdown."""
        user_content = f"Current route:\n{json.dumps(route)}\n\nUser: {message}"
    elif routes:
        # Global chat with all generated routes as context
        system = """You are a friendly road trip planning assistant. The user has generated road trip routes and may have questions about them or general travel questions. Answer helpfully and conversationally. Do NOT return updated_route — just answer questions.

Respond ONLY with valid JSON:
{"reply": "Your helpful answer here"}

No markdown. Be concise and friendly."""
        user_content = f"User's current trip options:\n{json.dumps(routes)}\n\nUser question: {message}"
    else:
        # No route context — general travel assistant
        system = """You are a friendly road trip planning assistant. Answer travel questions helpfully and conversationally.

Respond ONLY with valid JSON:
{"reply": "Your helpful answer here"}

No markdown. Be concise and friendly."""
        user_content = f"User question: {message}"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
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


@app.route("/api/optimize-route", methods=["POST"])
def optimize_route():
    data    = request.json
    api_key = data.get("api_key", "").strip() or DEFAULT_API_KEY
    route   = data.get("route")
    mode    = data.get("mode", "shortest")  # "shortest" or "scenic"

    if not api_key:
        return jsonify({"error": "No API key"}), 400
    if not route:
        return jsonify({"error": "No route"}), 400

    stops = route.get("stops", [])
    if len(stops) < 3:
        return jsonify({"error": "Need at least 3 stops to optimize"}), 400

    first, last = stops[0], stops[-1]
    middle = stops[1:-1]

    client = anthropic.Anthropic(api_key=api_key)
    stop_list = "\n".join(f"{i+1}. {s['name']} ({s['address']})" for i, s in enumerate(middle))
    prompt = f"""Reorder these middle stops for the {'shortest total driving distance' if mode == 'shortest' else 'most scenic and logical flow'}. Keep the same start ({first['name']}) and end ({last['name']}).

Middle stops to reorder:
{stop_list}

Return ONLY valid JSON (no markdown):
{{"order": [<1-based indices in new order>], "reason": "One sentence explaining the optimization"}}

Example: if 3 stops reordered as 2,1,3 → {{"order": [2,1,3], "reason": "..."}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1: raw = raw[s:e+1]
        result = json.loads(raw)
        order = result.get("order", [])
        reordered_middle = [middle[i - 1] for i in order if 1 <= i <= len(middle)]
        new_stops = [first] + reordered_middle + [last]
        return jsonify({"stops": new_stops, "reason": result.get("reason", "")})
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/api/alternative-routes", methods=["POST"])
def alternative_routes():
    data    = request.json
    api_key = data.get("api_key", "").strip() or DEFAULT_API_KEY
    route   = data.get("route")

    if not api_key:
        return jsonify({"error": "No API key"}), 400
    if not route:
        return jsonify({"error": "No route"}), 400

    stops = route.get("stops", [])
    start = stops[0]["address"] if stops else ""
    end   = stops[-1]["address"] if len(stops) > 1 else ""

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""The user has this road trip: {route.get('name')} from {start} to {end} with theme: {route.get('theme','')}.

Generate 2 alternative route variations with different themes/stops. Return ONLY valid JSON (no markdown):
[
  {{
    "name": "Alternative route name",
    "theme": "Different theme",
    "tagline": "One vivid sentence on what makes this different",
    "stops": ["Stop 1 name — City, State", "Stop 2 name — City, State", "Stop 3 name — City, State"]
  }}
]

Keep start ({start}) and end ({end}) the same. Make each alternative meaningfully different (e.g. coastal vs mountain, fast vs slow, cultural vs outdoor). Return exactly 2 alternatives."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        s, e = raw.find("["), raw.rfind("]")
        if s != -1 and e != -1: raw = raw[s:e+1]
        return jsonify({"alternatives": json.loads(raw)})
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/api/poi-suggestions", methods=["POST"])
def poi_suggestions():
    data    = request.json
    api_key = data.get("api_key", "").strip() or DEFAULT_API_KEY
    route   = data.get("route")

    if not api_key:
        return jsonify({"error": "No API key"}), 400
    if not route:
        return jsonify({"error": "No route"}), 400

    stops = route.get("stops", [])
    stop_names = [s.get("address", s.get("name", "")) for s in stops]

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""Suggest interesting points of interest along this road trip route: {' → '.join(stop_names[:6])}.

Return ONLY valid JSON (no markdown):
{{
  "pois": [
    {{
      "name": "POI name",
      "location": "City, State",
      "between": "Between Stop A and Stop B",
      "type": "National Park / Museum / Restaurant / Viewpoint / etc.",
      "why": "One vivid sentence on why it's worth stopping"
    }}
  ]
}}

Suggest 5-8 real, specific POIs that are actually along or near the route. Vary types (nature, food, history, quirky)."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1: raw = raw[s:e+1]
        return jsonify(json.loads(raw))
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/api/visa-check", methods=["POST"])
def visa_check():
    data       = request.json
    api_key    = data.get("api_key", "").strip() or DEFAULT_API_KEY
    route      = data.get("route")
    nationality = data.get("nationality", "US").strip()

    if not api_key:
        return jsonify({"error": "No API key"}), 400
    if not route:
        return jsonify({"error": "No route"}), 400

    stops = route.get("stops", [])
    countries = list({s.get("address", "").split(",")[-1].strip() for s in stops if s.get("address")})

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""Check entry/visa requirements for a {nationality} passport holder traveling to: {', '.join(countries)}.

Return ONLY valid JSON (no markdown):
{{
  "checks": [
    {{
      "country": "Country name",
      "requirement": "Visa-free / Visa on arrival / eVisa required / Visa required",
      "duration": "e.g. Up to 90 days",
      "notes": "Brief important note (e.g. passport validity, vaccination requirements)"
    }}
  ],
  "disclaimer": "Always verify with official embassy websites before travel."
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1: raw = raw[s:e+1]
        return jsonify(json.loads(raw))
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/api/toll-warnings", methods=["POST"])
def toll_warnings():
    data    = request.json
    api_key = data.get("api_key", "").strip() or DEFAULT_API_KEY
    route   = data.get("route")

    if not api_key:
        return jsonify({"error": "No API key"}), 400
    if not route:
        return jsonify({"error": "No route"}), 400

    stops = route.get("stops", [])
    stop_addresses = [s.get("address", "") for s in stops if s.get("address")]

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""For this road trip route: {' → '.join(stop_addresses[:6])}, identify known tolls, border crossings, and speed camera zones.

Return ONLY valid JSON (no markdown):
{{
  "warnings": [
    {{
      "type": "Toll Road / Border Crossing / Speed Camera Zone / Ferry",
      "location": "Specific road or area name",
      "between": "Between Stop A and Stop B",
      "detail": "Brief practical tip (e.g. 'Bring exact change' or 'E-ZPass accepted')",
      "estimated_cost": "e.g. $5-15 or Free"
    }}
  ],
  "tips": "One overall tip for this route regarding tolls/borders"
}}

Only include real, known toll roads and crossings for this specific route. If no tolls, return empty warnings array."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"): raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1: raw = raw[s:e+1]
        return jsonify(json.loads(raw))
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/routes/review/<int:route_id>", methods=["POST"])
@login_required
def add_review(route_id):
    saved = SavedRoute.query.get_or_404(route_id)
    data  = request.json
    rating = int(data.get("rating", 0))
    text   = data.get("text", "").strip()[:500]

    if not (1 <= rating <= 5):
        return jsonify({"error": "Rating must be 1-5"}), 400

    # Update or create
    existing = RouteReview.query.filter_by(route_id=route_id, user_id=current_user.id).first()
    if existing:
        existing.rating = rating
        existing.review_text = text
    else:
        db.session.add(RouteReview(
            route_id=route_id, user_id=current_user.id,
            username=current_user.username, rating=rating, review_text=text
        ))
    db.session.commit()
    avg = db.session.query(db.func.avg(RouteReview.rating)).filter_by(route_id=route_id).scalar() or 0
    return jsonify({"success": True, "avg_rating": round(float(avg), 1)})


@app.route("/routes/reviews/<int:route_id>")
def get_reviews(route_id):
    reviews = RouteReview.query.filter_by(route_id=route_id)\
                               .order_by(RouteReview.created_at.desc()).limit(20).all()
    avg = db.session.query(db.func.avg(RouteReview.rating)).filter_by(route_id=route_id).scalar() or 0
    return jsonify({
        "reviews": [{"username": r.username, "rating": r.rating,
                     "text": r.review_text, "date": r.created_at.strftime("%b %d, %Y")} for r in reviews],
        "avg_rating": round(float(avg), 1),
        "count": len(reviews)
    })


@app.route("/routes/journal/<int:route_id>", methods=["GET", "POST"])
@login_required
def route_journal(route_id):
    saved = SavedRoute.query.get_or_404(route_id)
    if saved.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    if request.method == "GET":
        journal = TripJournal.query.filter_by(route_id=route_id, user_id=current_user.id).first()
        if journal:
            return jsonify({"content": journal.content or "", "stop_ratings": json.loads(journal.stop_ratings or "{}")})
        return jsonify({"content": "", "stop_ratings": {}})

    data = request.json
    journal = TripJournal.query.filter_by(route_id=route_id, user_id=current_user.id).first()
    if journal:
        journal.content = data.get("content", "")[:5000]
        journal.stop_ratings = json.dumps(data.get("stop_ratings", {}))
        journal.updated_at = datetime.utcnow()
    else:
        journal = TripJournal(
            route_id=route_id, user_id=current_user.id,
            content=data.get("content", "")[:5000],
            stop_ratings=json.dumps(data.get("stop_ratings", {}))
        )
        db.session.add(journal)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/stats")
@login_required
def stats():
    routes = SavedRoute.query.filter_by(user_id=current_user.id).all()
    total_routes = len(routes)

    # Parse distances and extract state/country names
    total_miles = 0
    places = set()
    for r in routes:
        try:
            data = json.loads(r.route_data)
            dist_str = data.get("distance", "")
            # Extract number from strings like "1,234 miles" or "2,000 km"
            import re
            nums = re.findall(r'[\d,]+', dist_str)
            if nums:
                val = int(nums[0].replace(",", ""))
                if "km" in dist_str.lower():
                    val = int(val * 0.621371)
                total_miles += val
            for stop in data.get("stops", []):
                addr = stop.get("address", "")
                parts = [p.strip() for p in addr.split(",")]
                if len(parts) >= 2:
                    places.add(parts[-1])  # last part = country or state
        except Exception:
            pass

    return render_template("stats.html",
        total_routes=total_routes,
        total_miles=f"{total_miles:,}",
        places_visited=sorted(places),
        member_since=current_user.created_at.strftime("%B %Y") if current_user.created_at else "Unknown"
    )


@app.route("/routes/fork/<share_id>", methods=["POST"])
@login_required
def fork_route(share_id):
    original = SavedRoute.query.filter_by(share_id=share_id, is_public=True).first_or_404()
    forked = SavedRoute(
        user_id   = current_user.id,
        share_id  = str(uuid.uuid4())[:10],
        name      = original.name + " (Fork)",
        route_data= original.route_data
    )
    db.session.add(forked)
    db.session.commit()
    return jsonify({"success": True, "redirect": "/routes/saved"})


@app.route("/trip-mode/<share_id>")
def trip_mode(share_id):
    saved = SavedRoute.query.filter_by(share_id=share_id).first_or_404()
    return render_template("trip_mode.html", route_json=saved.route_data, route_name=saved.name)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
