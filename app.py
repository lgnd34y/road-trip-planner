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
    inbox  = SharedRoute.query.filter_by(to_user_id=current_user.id)\
                              .order_by(SharedRoute.created_at.desc()).all()
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
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] 👀 Visit — IP: {request.remote_addr}", flush=True)
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

    # Long trips: fewer stops, shorter text, grouped itinerary days to stay under token limit
    if nights_int >= 7:
        user_message += f"\nIMPORTANT: This is a {nights_int}-night trip. Use max 5 stops total. Limit each description/note to 1 short sentence. Group every 2-3 nights into a single itinerary entry (so max 5 itinerary entries total). Be extremely concise — every extra word risks truncating the JSON."

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=6000,
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
            model="claude-opus-4-6",
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
            model="claude-opus-4-6",
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
