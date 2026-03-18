from flask import Blueprint, render_template, request, session, redirect, current_app,jsonify
import os, json, re, requests, urllib.parse, random
from groq import Groq
from dotenv import load_dotenv
import MySQLdb.cursors
load_dotenv()
trips_routes = Blueprint("trips", __name__)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@trips_routes.route("/view-trip/<int:trip_id>")
def view_trip(trip_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = current_app.config["MYSQL_CONNECTION"].connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)

    # Fetch trip for the current user
    cursor.execute("""
        SELECT * FROM trips
        WHERE id=%s AND user_id=%s
    """, (trip_id, session["user_id"]))
    trip = cursor.fetchone()

    if not trip:
        cursor.close()
        return "Trip not found", 404

    #  Load trip JSON
    trip_data = json.loads(trip["ai_data"])

    #  Fetch visited_places for this trip
    cursor.execute("""
        SELECT place_name, visited
        FROM visited_places
        WHERE trip_id=%s
    """, (trip_id,))
    visited_rows = cursor.fetchall()
    cursor.close()

    #  Create a map of place_name -> visited
    visited_map = {row["place_name"]: row["visited"] for row in visited_rows}

    #  Merge visited info into daily_plan
    for day in trip_data.get("daily_plan", []):
        day["visited"] = visited_map.get(day["place"], False)
    # After merging visited info
    trip_data["trip_id"] = trip_id
    #  Render template
    return render_template(
        "trip_result.html",
        trip=trip_data,
        destination=trip["destination"],
        duration=trip["duration"],
        travel_type=trip["travel_type"],
        is_view=True,
        trip_id=trip_id
    )


@trips_routes.route("/edit-trip/<int:trip_id>")
def edit_trip(trip_id):

    if "user_id" not in session:
        return redirect("/login")
    session["editing_trip_id"] = trip_id
    conn = current_app.config["MYSQL_CONNECTION"].connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("""
        SELECT * FROM trips
        WHERE id=%s AND user_id=%s
    """, (trip_id, session["user_id"]))

    trip = cursor.fetchone()
    cursor.close()

    if not trip:
        return "Trip not found", 404

    trip_data = json.loads(trip["ai_data"])
    inputs = trip_data.get("inputs", {})

    return render_template(
    "create_trip.html",
    trip_id=trip_id,
    start_city=inputs.get("start_city"),
    destination=trip["destination"],
    duration=trip["duration"],
    travel_type=trip["travel_type"],
    start_date=trip["start_date"],
    budget_type=inputs.get("budget_type"),
    transport_mode=inputs.get("transport_mode"),
    trip_style=inputs.get("trip_style")
    )

# ---------------- Limits ----------------
TOP_ATTRACTIONS_LIMIT = 5
ACTIVITIES_LIMIT = 3
FOOD_LIMIT = 3
ACCOMMODATION_LIMIT = 3
ITINERARY_LIMIT = 6

UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS")
UNSPLASH_URL = "https://api.unsplash.com/search/photos"

MEALDB_URL = "https://www.themealdb.com/api/json/v1/1/search.php?s="

# ---------------- YouTube Vlogs ----------------
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def get_travel_vlogs(destination):
    search_query = f"{destination} travel vlog"
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": search_query,
        "type": "video",
        "maxResults": 3,  # ask API for only 3 results
        "key": YOUTUBE_API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        items = data.get("items", [])[:3]  # ensure only 3 items even if API returns more

        vlogs = []
        for item in items:
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            vlogs.append({
                "videoId": video_id,
                "title": title
            })

        return vlogs

    except Exception as e:
        print("YouTube API error:", e)
        return []

# ---- currency conversion (approx) ----
EUR_TO_INR = 90
USD_TO_INR = 83
GBP_TO_INR = 105
AUD_TO_INR = 55
# ---------------- Transport ranges ----------------
TRANSPORT_COST = {
    "same_city": (500, 1500),
    "domestic": (2000, 8000),
    "international": (40000, 90000)
}


# ---------------- Food cost per day ----------------
FOOD_COST = {
    "Budget": 800,
    "Moderate": 1500,
    "Luxury": 3500
}


# ---------------- Activity cost per day ----------------
ACTIVITY_COST = {
    "Budget": 500,
    "Moderate": 1200,
    "Luxury": 3000
}

INTERNATIONAL_CITIES = [ "paris","london","tokyo","new york","rome","dubai" ]
# ---------------- JSON Extractor ----------------
def extract_json(text):
    try:
        return json.loads(text)
    except:
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                cleaned = match.group()

                # Fix common AI JSON mistakes
                # Fix missing quotes on keys
                cleaned = re.sub(r'(\w+):', r'"\1":', cleaned)

                # Remove trailing commas
                cleaned = cleaned.replace(",}", "}").replace(",]", "]")

                return json.loads(cleaned)
        except:
            pass

    return {}


# ---------------- Currency extractor ----------------
def extract_price(price_string):

    if not price_string:
        return 0

    # remove commas
    clean = price_string.replace(",", "")

    numbers = re.findall(r"\d+", clean)

    if not numbers:
        return 0

    value = int(numbers[0])

    if "€" in price_string:
        return value * EUR_TO_INR

    if "$" in price_string:
        return value * USD_TO_INR
    if "£" in price_string:
        return value * GBP_TO_INR
    return value

def format_inr(amount):
    amount = int(amount)
    s = str(amount)

    if len(s) <= 3:
        return s

    last3 = s[-3:]
    rest = s[:-3]

    rest = ",".join(
        [rest[max(i-2, 0):i] for i in range(len(rest), 0, -2)][::-1]
    )

    return rest + "," + last3

# ---------------- Image Fetch ----------------
def fetch_image(query):

    placeholder = f"https://via.placeholder.com/600x400?text={urllib.parse.quote(query)}"
    if not UNSPLASH_KEY:
            return {"url": placeholder, "found": False}
    try:

        headers = {"Authorization": f"Client-ID {UNSPLASH_KEY}"}

        response = requests.get(
            UNSPLASH_URL,
            headers=headers,
            params={"query": query, "per_page": 1},
            timeout=5
        )

        data = response.json()

        if data.get("results"):
            return {
                "url": data["results"][0]["urls"]["regular"],
                "found": True
            }

    except Exception as e:
        print("Unsplash error:", e)

    return {"url": placeholder, "found": False}


# ---------------- Food Image ----------------
def fetch_food_image(food):

    placeholder = f"https://via.placeholder.com/600x400?text={urllib.parse.quote(food)}"

    try:

        response = requests.get(
            MEALDB_URL + urllib.parse.quote(food),
            timeout=5
        )

        data = response.json()

        if data.get("meals"):
            return {
                "url": data["meals"][0]["strMealThumb"],
                "found": True
            }

    except Exception as e:
        print("MealDB error:", e)

    return {"url": placeholder, "found": False}


# ---------------- Map Link ----------------
def generate_map_link(place, city):
    query = urllib.parse.quote(f"{place} {city}")
    return f"https://www.google.com/maps/search/?api=1&query={query}"


# ---------------- ROUTE ----------------
@trips_routes.route("/generate-trip", methods=["POST"])
def generate_trip():
    if "user_id" not in session:
        return redirect("/login")
    trip_id = request.form.get("trip_id")
    start_city = (request.form.get("start_city") or "").title()
    destination = (request.form.get("destination") or "").title()
    duration = int(request.form.get("duration")or 1)
    if not start_city or not destination or not duration:
        return "Invalid request", 400
    travel_type = request.form.get("travel_type")
    start_date = request.form.get("start_date")
    budget_type = request.form.get("budget_type")
    trip_style = request.form.get("trip_style")
    transport_mode = request.form.get("transport_mode")
    trip_purpose = request.form.get("trip_purpose")

# ---------------- Prompt ----------------
    prompt = f"""
You are a travel planning API.

Return ONLY valid JSON.
Do not include explanations or markdown.

Trip Details:
Start City: {start_city}
Destination: {destination}
Duration: {duration} days
Travel Type: {travel_type}
Budget Type: {budget_type}
Trip Style: {trip_style}
Preferred Transport: {transport_mode}
Trip Purpose: {trip_purpose}

Generate:

- EXACTLY 6 itinerary places in {destination} for {trip_purpose}
- EXACTLY 5 top attractions in {destination}
- EXACTLY 3 things to do in {destination}
- EXACTLY 3 famous foods in {destination}
- EXACTLY 3 accommodations in {destination}

Accommodation must include price_per_night in LOCAL currency.
If the destination is in India, use INR (₹).

If the destination is outside India, use the local currency of that country.
For example:
France → €
USA → $
UK → £
Japan → ¥
UAE → AED
IMPORTANT RULE: DO NOT LEAVE ANY FIELD EMPTY.
Transport Rules:
If start city and destination are in different countries → suggest flight.
If they are in the same country → suggest flight or train.
Never suggest car for international travel.
JSON format:

{{
"daily_plan":[
{{"place":"string","morning":"string","afternoon":"string","evening":"string","best_time":"HH:MM-HH:MM"}},
{{"place":"string","morning":"string","afternoon":"string","evening":"string","best_time":"HH:MM-HH:MM"}},
{{"place":"string","morning":"string","afternoon":"string","evening":"string","best_time":"HH:MM-HH:MM"}},
{{"place":"string","morning":"string","afternoon":"string","evening":"string","best_time":"HH:MM-HH:MM"}},
{{"place":"string","morning":"string","afternoon":"string","evening":"string","best_time":"HH:MM-HH:MM"}},
{{"place":"string","morning":"string","afternoon":"string","evening":"string","best_time":"HH:MM-HH:MM"}}
],

"top_attractions":[
{{"name":"string","description":"string","best_time":"HH:MM-HH:MM"}},
{{"name":"string","description":"string","best_time":"HH:MM-HH:MM"}},
{{"name":"string","description":"string","best_time":"HH:MM-HH:MM"}},
{{"name":"string","description":"string","best_time":"HH:MM-HH:MM"}},
{{"name":"string","description":"string","best_time":"HH:MM-HH:MM"}}
],

"things_to_do":[
{{"name":"string","description":"string"}},
{{"name":"string","description":"string"}},
{{"name":"string","description":"string"}}
],

"famous_food":[
{{"name":"string","description":"string"}},
{{"name":"string","description":"string"}},
{{"name":"string","description":"string"}}
],

"accommodations":[
{{"name":"string","type":"Hotel","price_per_night":"€120"}},
{{"name":"string","type":"Hotel","price_per_night":"€150"}},
{{"name":"string","type":"Hotel","price_per_night":"€200"}}
],

"transport":[
"Best way to travel from {start_city} to {destination}",
"Common local transport options in the {destination} "
]
}}
"""
# ---------------- AI Call ----------------

    try:
   
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            timeout=10
        )

        ai_text = response.choices[0].message.content
        trip_data = extract_json(ai_text)
        
        #-----Fallback if AI fails-------
        if not trip_data:
             trip_data = {
                "daily_plan": [],
                "top_attractions": [],
                "things_to_do": [],
                "famous_food": [],
                "accommodations": [],
                "transport": []
            }
             # ---------------- Transport Cleanup ----------------
        clean_transport = []

        for t in trip_data.get("transport", []):
            if isinstance(t, dict):
        # AI returned object like {type:"flight"...}
                 clean_transport.append(
                 f"{t.get('type', '').title()} - {t.get('duration', '')}"
                )
            elif isinstance(t, str):
                clean_transport.append(t)
            else:
                clean_transport.append(str(t))

        trip_data["transport"] = clean_transport
        # ---------------- Transport Fallback ----------------
        if not trip_data["transport"]:
            if start_city.lower() == destination.lower():
                 trip_data["transport"] = ["Local travel by car/train/bus"]
            elif destination.lower() in INTERNATIONAL_CITIES:
                 trip_data["transport"] = [f"Flight from {start_city} to {destination}"]
            else:
             trip_data["transport"] = [f"Flight or train from {start_city} to {destination}"]
    except Exception as e:
        print("AI error:", e)
        trip_data = {
                "daily_plan": [],
                "top_attractions": [],
                "things_to_do": [],
                "famous_food": [],
                "accommodations": [],
                "transport": []
            }

# ---------------- Safety Defaults ----------------

    trip_data.setdefault("daily_plan", [])
    trip_data.setdefault("top_attractions", [])
    trip_data.setdefault("things_to_do", [])
    trip_data.setdefault("famous_food", [])
    trip_data.setdefault("accommodations", [])
    trip_data.setdefault("transport", [])

# ---------------- Repeat Itinerary ----------------

    original_daily = trip_data.get("daily_plan", [])

    final_daily = []

    if original_daily:

        for i in range(duration):

            card = original_daily[i % len(original_daily)].copy()

            card["day"] = i + 1

            img = fetch_image(f"{card['place']} {destination}")

            card["image"] = img["url"]
            card["image_found"] = img["found"]

            card["map_link"] = generate_map_link(card["place"], destination)

            final_daily.append(card)

    trip_data["daily_plan"] = final_daily


# ---------------- Attractions ----------------

    attractions = trip_data.get("top_attractions", [])[:TOP_ATTRACTIONS_LIMIT]

    for place in attractions:

        img = fetch_image(f"{place['name']} {destination}")

        place["image"] = img["url"]
        place["image_found"] = img["found"]

        place["map_link"] = generate_map_link(place["name"], destination)

    trip_data["top_attractions"] = attractions


# ---------------- Food ----------------

    foods = trip_data.get("famous_food", [])[:FOOD_LIMIT]

    for food in foods:

        img = fetch_food_image(food["name"])

        food["image"] = img["url"]
        food["image_found"] = img["found"]

    trip_data["famous_food"] = foods


# ---------------- Accommodation ----------------

    stays = trip_data.get("accommodations", [])[:ACCOMMODATION_LIMIT]

    hotel_prices = []

    for stay in stays:

        price = extract_price(stay.get("price_per_night"))
        hotel_prices.append(price)

        img = fetch_image(f"{stay['name']} hotel {destination}")

        stay["image"] = img["url"]
        stay["image_found"] = img["found"]

        stay["map_link"] = generate_map_link(stay["name"], destination)

    trip_data["accommodations"] = stays


# ---------------- Budget Calculation ----------------
    
    # ---- accommodation average ----
    if hotel_prices:
        avg_price = sum(hotel_prices) / len(hotel_prices)
        accommodation_cost = avg_price * duration
    else:
        accommodation_cost = 0

    # ---- food ----
    food_cost = FOOD_COST.get(budget_type, 1500) * duration

    # ---- activities ----
    activity_cost = ACTIVITY_COST.get(budget_type, 1200) * duration

    # ---- transport ----
    if start_city.lower() == destination.lower():
        transport_cost = random.randint(*TRANSPORT_COST["same_city"])
    elif destination.lower() in INTERNATIONAL_CITIES:
        transport_cost = random.randint(*TRANSPORT_COST["international"])
    else:
        transport_cost = random.randint(*TRANSPORT_COST["domestic"])

    total_budget = int(accommodation_cost + food_cost + activity_cost + transport_cost)
    
    trip_data["budget"] = {
        "accommodation": int(accommodation_cost),
        "food": int(food_cost),
        "activities": int(activity_cost),
        "transport": int(transport_cost),

        # formatted values 👇
        "accommodation_fmt": format_inr(accommodation_cost),
        "food_fmt": format_inr(food_cost),
        "activities_fmt": format_inr(activity_cost),
        "transport_fmt": format_inr(transport_cost)
    }

    trip_data["budget_total"] = total_budget
    trip_data["budget_total_fmt"] = format_inr(total_budget)

    per_day = round(total_budget / duration) if duration else 0
    trip_data["per_day_cost"] = per_day
    trip_data["per_day_cost_fmt"] = format_inr(per_day)

# ---------------- Add Summary Data ----------------

    trip_data["destination"] = destination
    trip_data["duration"] = duration
    trip_data["travel_type"] = travel_type
    trip_data["budget_type"] = budget_type
    # ---------------- Travel Vlogs ----------------
    trip_data["vlogs"] = get_travel_vlogs(destination)
    trip_data["inputs"] = {
    "start_city": start_city,
    "destination": destination,
    "start_date": start_date,
    "duration": duration,
    "budget_type": budget_type,
    "travel_type": travel_type,
    "transport_mode": transport_mode,
    "trip_style": trip_style
    }
    # Save latest trip in session
    session["latest_trip"] = trip_data

# Redirect instead of rendering directly
    return redirect("/trip-result")

# ---------------- Save Trip To Database ----------------
@trips_routes.route("/save-trip", methods=["POST"])
def save_trip():
    if "user_id" not in session:
        return {"success": False, "error": "Unauthorized"}, 401

    trip_data = session.get("latest_trip")
    if not trip_data:
        return {"success": False, "error": "No trip data in session"}, 400

    conn = current_app.config["MYSQL_CONNECTION"].connection
    cursor = conn.cursor()

    try:
        ai_json = json.dumps(trip_data)

        #  CHECK IF EDIT MODE
        if "editing_trip_id" in session:
            trip_id = session["editing_trip_id"]

            cursor.execute("""
                UPDATE trips
                SET destination=%s, start_date=%s, duration=%s,
                    budget=%s, travel_type=%s, ai_data=%s
                WHERE id=%s AND user_id=%s
            """, (
                trip_data["destination"],
                trip_data["inputs"].get("start_date"),
                trip_data["duration"],
                str(trip_data["budget_total"]),
                trip_data["travel_type"],
                ai_json,
                trip_id,
                session["user_id"]
            ))

            conn.commit()
            cursor.close()

            #  clear edit mode
            session.pop("editing_trip_id", None)

            return {"success": True, "updated": True, "trip_id": trip_id}

        #  NORMAL SAVE (INSERT)
        cursor.execute("""
            INSERT INTO trips (user_id, destination, start_date, duration, budget, travel_type, ai_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            session["user_id"],
            trip_data["destination"],
            trip_data["inputs"].get("start_date"),
            trip_data["duration"],
            str(trip_data["budget_total"]),
            trip_data["travel_type"],
            ai_json
        ))

        trip_id = cursor.lastrowid
        conn.commit()
        cursor.close()

        trip_data["trip_id"] = trip_id
        session["latest_trip"] = trip_data

        return {"success": True, "trip_id": trip_id}

    except Exception as e:
        cursor.close()
        print("Error saving trip:", e)
        return {"success": False, "error": "Error saving trip"}, 500


@trips_routes.route("/trip-result")
def trip_result():
    trip_data = session.get("latest_trip")

    if not trip_data:
        return redirect("/create-trip")  # No trip in session

    return render_template(
        "trip_result.html",
        trip=trip_data,
        destination=trip_data["destination"],
        duration=trip_data["duration"],
        travel_type=trip_data["travel_type"],
        budget_type=trip_data["budget_type"],
        is_view=False
    )

@trips_routes.route("/toggle-visited", methods=["POST"])
def toggle_visited():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()
    trip_id = data.get("trip_id")
    place_name = data.get("place_name")
    visited = data.get("visited")

    if not all([trip_id, place_name]) or visited is None:
        return jsonify({"success": False, "error": "Missing data"}), 400

    conn = current_app.config["MYSQL_CONNECTION"].connection
    cursor = conn.cursor(MySQLdb.cursors.DictCursor)

    try:
        # Check if this place already exists
        cursor.execute("""
            SELECT id FROM visited_places 
            WHERE trip_id=%s AND place_name=%s
        """, (trip_id, place_name))
        row = cursor.fetchone()

        if row:
            # Update existing row
            cursor.execute("""
                UPDATE visited_places 
                SET visited=%s
                WHERE id=%s
            """, (visited, row["id"]))
        else:
            # Insert new row
            cursor.execute("""
                INSERT INTO visited_places (trip_id, place_name, visited)
                VALUES (%s, %s, %s)
            """, (trip_id, place_name, visited))

        conn.commit()
        cursor.close()
        return jsonify({"success": True})

    except Exception as e:
        cursor.close()
        print("Error toggling visited:", e)
        return jsonify({"success": False, "error": "Database error"}), 500