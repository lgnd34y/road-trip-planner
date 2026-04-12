import anthropic
import os
import json
import webbrowser
import tempfile
from urllib.parse import quote


def build_maps_url(addresses: list) -> str:
    encoded = [quote(a) for a in addresses]
    return "https://www.google.com/maps/dir/" + "/".join(encoded)


def build_route_page(route: dict, maps_url: str) -> str:
    stops_html = ""
    for j, stop in enumerate(route["stops"]):
        if j == 0 or j == len(route["stops"]) - 1:
            icon = "🏁"
            label = "Start / End" if j == 0 else "Return"
        else:
            icon = "📌"
            label = f"Stop {j}"
        description = stop.get("description", "")
        stops_html += f"""
        <div class="stop" onclick="toggleDesc(this)">
            <div class="stop-icon">{icon}</div>
            <div class="stop-info">
                <div class="stop-header">
                    <div>
                        <div class="stop-name">{stop['name']}</div>
                        <div class="stop-address">{stop['address']}</div>
                        <div class="stop-label">{label}</div>
                    </div>
                    <div class="chevron">▼</div>
                </div>
                <div class="stop-desc">{description}</div>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{route['name']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f0f4f8;
            color: #1a202c;
            min-height: 100vh;
        }}
        header {{
            background: linear-gradient(135deg, #2d6a4f, #52b788);
            color: white;
            padding: 40px 30px 30px;
        }}
        header h1 {{ font-size: 2rem; margin-bottom: 6px; }}
        header p {{ font-size: 1.1rem; opacity: 0.9; }}
        .container {{ max-width: 720px; margin: 0 auto; padding: 30px 20px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-bottom: 30px;
        }}
        .stat {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        }}
        .stat-icon {{ font-size: 1.6rem; margin-bottom: 6px; }}
        .stat-label {{ font-size: 0.75rem; color: #718096; text-transform: uppercase; letter-spacing: 0.05em; }}
        .stat-value {{ font-size: 1rem; font-weight: 600; margin-top: 4px; }}
        .highlight {{
            background: #fffbea;
            border-left: 4px solid #f6ad55;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 30px;
            font-size: 0.97rem;
        }}
        .highlight strong {{ color: #c05621; }}
        h2 {{ font-size: 1.2rem; margin-bottom: 16px; color: #2d3748; }}
        .stops {{ display: flex; flex-direction: column; gap: 12px; margin-bottom: 30px; }}
        .stop {{
            background: white;
            border-radius: 10px;
            padding: 16px;
            display: flex;
            align-items: flex-start;
            gap: 14px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
            cursor: pointer;
            transition: box-shadow 0.2s;
        }}
        .stop:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.12); }}
        .stop-info {{ flex: 1; }}
        .stop-header {{ display: flex; justify-content: space-between; align-items: flex-start; }}
        .stop-icon {{ font-size: 1.4rem; margin-top: 2px; }}
        .stop-name {{ font-weight: 600; font-size: 1rem; }}
        .stop-address {{ color: #718096; font-size: 0.88rem; margin-top: 3px; }}
        .stop-label {{ font-size: 0.75rem; color: #52b788; font-weight: 600; margin-top: 4px; text-transform: uppercase; }}
        .chevron {{ color: #a0aec0; font-size: 0.75rem; margin-top: 4px; transition: transform 0.25s; }}
        .stop.open .chevron {{ transform: rotate(180deg); }}
        .stop-desc {{
            display: none;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #e2e8f0;
            font-size: 0.92rem;
            color: #4a5568;
            line-height: 1.6;
        }}
        .stop.open .stop-desc {{ display: block; }}
        .maps-btn {{
            display: block;
            background: linear-gradient(135deg, #2d6a4f, #52b788);
            color: white;
            text-align: center;
            padding: 16px;
            border-radius: 12px;
            text-decoration: none;
            font-size: 1.05rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            box-shadow: 0 4px 14px rgba(82,183,136,0.4);
            transition: opacity 0.2s;
        }}
        .maps-btn:hover {{ opacity: 0.9; }}
    </style>
</head>
<body>
    <header>
        <h1>🚗 {route['name']}</h1>
        <p>{route['theme']}</p>
    </header>
    <div class="container">
        <div class="stats">
            <div class="stat">
                <div class="stat-icon">📏</div>
                <div class="stat-label">Distance</div>
                <div class="stat-value">{route['distance']}</div>
            </div>
            <div class="stat">
                <div class="stat-icon">🕐</div>
                <div class="stat-label">Drive Time</div>
                <div class="stat-value">{route['drive_time']}</div>
            </div>
            <div class="stat">
                <div class="stat-icon">📅</div>
                <div class="stat-label">Best Time</div>
                <div class="stat-value">{route['best_time']}</div>
            </div>
        </div>

        <div class="highlight">
            <strong>⭐ Don't Miss:</strong> {route['highlight']}
        </div>

        <h2>📍 Route Stops</h2>
        <div class="stops">{stops_html}
        </div>

        <a class="maps-btn" href="{maps_url}" target="_blank">
            🗺️ Open Full Route in Google Maps
        </a>
    </div>
    <script>
        function toggleDesc(el) {{
            el.classList.toggle('open');
        }}
    </script>
</body>
</html>"""


def get_road_trip_recommendations(location: str, duration: str = "", destination: str = "", preferences: str = "", extra_info: str = "") -> None:
    client = anthropic.Anthropic()

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
      {"name": "Place Name", "address": "Full street address or City, State, Country", "description": "2-3 sentence description of what this place is and why it's worth visiting"},
      ...
    ]
  }
]

Rules:
- Each route's stops must start AND end at the starting location (circular route)
- Include 5-8 stops between start and end
- Provide real, specific addresses or at minimum "City, State, Country" for every stop
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

    print("\n🗺️  Planning your road trips...\n")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0].strip()

    routes = json.loads(raw)

    # Display all routes in terminal
    for i, route in enumerate(routes, 1):
        print(f"\n{'=' * 60}")
        print(f"  Route {i}: {route['name']}")
        print(f"  Theme:      {route['theme']}")
        print(f"{'=' * 60}")
        print(f"  📏 Distance:   {route['distance']}")
        print(f"  🕐 Drive Time: {route['drive_time']}")
        print(f"  📅 Best Time:  {route['best_time']}")
        print(f"  ⭐ Highlight:  {route['highlight']}")
        print(f"\n  📍 Stops:")
        for j, stop in enumerate(route["stops"]):
            icon = "🏁" if j == 0 or j == len(route["stops"]) - 1 else "📌"
            print(f"     {icon} {stop['name']}")
            print(f"        {stop['address']}")

    # Ask which route to open
    print(f"\n{'=' * 60}")
    print("Open a route? Enter 1, 2, 3, or 'skip':")
    choice = input("  Choice: ").strip().lower()

    if choice in ("1", "2", "3"):
        idx = int(choice) - 1
        if idx < len(routes):
            route = routes[idx]
            addresses = [stop["address"] for stop in route["stops"]]
            maps_url = build_maps_url(addresses)

            # Build and open the route webpage
            html = build_route_page(route, maps_url)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
                f.write(html)
                page_path = f.name

            print(f"\n🌐 Opening route page for: {route['name']}")
            webbrowser.open(f"file:///{page_path}")

            avoid_keywords = ["highway", "highways", "motorway", "toll", "tolls", "freeway"]
            if any(word in (extra_info + preferences).lower() for word in avoid_keywords):
                print("\n⚠️  Route preference tip:")
                print("   Google Maps doesn't support route options via links.")
                print("   Once Maps opens, click the 3 dots (⋮) → Route options")
                print("   and set 'Avoid highways' or 'Avoid tolls' manually.")


def main():
    print("=" * 60)
    print("       🚗  ROAD TRIP ROUTE RECOMMENDER  🚗")
    print("=" * 60)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n⚠️  ANTHROPIC_API_KEY environment variable not set.")
        print("In PowerShell: $env:ANTHROPIC_API_KEY=\"your-key-here\"\n")
        return

    while True:
        print("\nEnter your starting location (or 'quit' to exit):")
        location = input("  Location: ").strip()

        if location.lower() in ("quit", "exit", "q"):
            print("\nHappy travels! 🌟\n")
            break

        if not location:
            print("Please enter a valid location.")
            continue

        print("Is there a specific place you'd like to visit? (e.g. Grand Canyon, Paris) — press Enter to skip:")
        destination = input("  Destination: ").strip()

        print("How long do you want to be on the road? (e.g. 2 hours, 1 day, weekend, 1 week) — press Enter to skip:")
        duration = input("  Duration: ").strip()

        print("Any preferences? (e.g. mountains, beaches, history, food) — press Enter to skip:")
        preferences = input("  Preferences: ").strip()

        print("Anything else we should know? (e.g. travelling with kids, avoiding highways, budget trip) — press Enter to skip:")
        extra_info = input("  Details: ").strip()

        try:
            get_road_trip_recommendations(location, duration, destination, preferences, extra_info)
        except anthropic.AuthenticationError:
            print("\n❌ Invalid API key. Check your ANTHROPIC_API_KEY.")
            break
        except anthropic.APIConnectionError:
            print("\n❌ Connection error. Check your internet connection.")
        except json.JSONDecodeError as e:
            print(f"\n❌ Failed to parse route data: {e}")
        except Exception as e:
            print(f"\n❌ Error: {e}")

        print("\nWould you like another road trip recommendation? (yes/no):")
        again = input("  ").strip().lower()
        if again not in ("yes", "y"):
            print("\nHappy travels! 🌟\n")
            break


if __name__ == "__main__":
    main()
