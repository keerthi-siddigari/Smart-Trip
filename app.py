from flask import Flask, render_template, session, redirect
from flask_mysqldb import MySQL
from auth import auth_routes, init_mysql
from trips import trips_routes
from flask import jsonify,request
from recommendations import get_recommendations
import json
import os
import MySQLdb.cursors
from datetime import date, datetime
app = Flask(__name__)
from dotenv import load_dotenv
load_dotenv()
# ----------------- SECRET KEY -----------------
app.secret_key = os.getenv("SECRET_KEY")

# ----------------- MySQL CONFIG -----------------


app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DB")
app.config['MYSQL_PORT'] = int(os.getenv("MYSQL_PORT"))
app.config['MYSQL_SSL_CA'] = '/etc/ssl/certs/ca-certificates.crt'
# ----------------- MySQL INSTANCE -----------------
mysql = MySQL(app)
app.config["MYSQL_CONNECTION"] = mysql
# Initialize MySQL in auth.py
init_mysql(mysql)

# Register blueprints
app.register_blueprint(auth_routes)
app.register_blueprint(trips_routes)


# ----------------- Dashboard  -----------------
@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect("/login")

    user_id = session['user_id']

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
    "SELECT travel_preferences FROM users WHERE id=%s",
    (user_id,)
    )

    user = cursor.fetchone()

    
    preferences = json.loads(user["travel_preferences"])
    if preferences:
        recommended_places = get_recommendations(preferences)
    else:
        recommended_places=[]
    cursor.execute("""
        SELECT id, destination, duration, budget, travel_type, start_date, status
        FROM trips
        WHERE user_id=%s
        ORDER BY id DESC
    """, (user_id,))

    trips = cursor.fetchall()
    cursor.close()
    from trips import format_inr  # import the function

    for trip in trips:
     trip['budget_fmt'] = format_inr(int(trip['budget']))
    total_trips = len(trips)
    from datetime import date, datetime

    today = date.today()

    for trip in trips:
    # Convert start_date from string to date if needed
        if isinstance(trip['start_date'], str):
         trip_date = datetime.strptime(trip['start_date'], "%Y-%m-%d").date()
        else:
         trip_date = trip['start_date']

    # If trip is past and not marked completed, update status
        if trip_date < today and trip['status'] != 'Completed':
            trip['status'] = 'Completed'
        # Optional: update in database
            cursor = mysql.connection.cursor()
            cursor.execute("UPDATE trips SET status=%s WHERE id=%s", ('Completed', trip['id']))
            mysql.connection.commit()
            cursor.close()
    upcoming_trips = len([t for t in trips if t['status'] == 'Upcoming'])
    completed_trips = len([t for t in trips if t['status'] == 'Completed'])

    username = session.get("username", "Traveler")

    return render_template(
    "dashboard.html",
    trips=trips,
    username=username,
    total_trips=total_trips,
    upcoming_trips=upcoming_trips,
    completed_trips=completed_trips,
    recommended_places=recommended_places
    )



@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT username, email, travel_preferences
        FROM users
        WHERE id = %s
    """, (user_id,))

    user = cursor.fetchone()
    cursor.close()

    # convert JSON preferences
    if user and user["travel_preferences"]:
        user["travel_preferences"] = json.loads(user["travel_preferences"])
    else:
        user["travel_preferences"] = []

    return render_template("profile.html", user=user)
@app.route("/delete-trip/<int:trip_id>", methods=["POST"])
def delete_trip(trip_id):
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    user_id = session['user_id']

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("DELETE FROM trips WHERE id=%s AND user_id=%s", (trip_id, user_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"success": True, "message": "Trip deleted"})
    except Exception as e:
        print("Error deleting trip:", e)
        return jsonify({"success": False, "message": "Error deleting trip"}), 500

# ----------------- Other routes -----------------

@app.route("/")
def landing():
    user_logged_in = 'user_id' in session
    return render_template("index.html", user_logged_in=user_logged_in)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/features")
def features():
    return render_template("features.html")


@app.route("/create-trip")
def create_trip():
    if 'user_id' not in session:
        return redirect("/login")
    # Clear editing flag for new trips
    session.pop("editing_trip_id", None)
    # Query params
    prefill_flag = request.args.get("prefill")  # e.g., ?prefill=1
    destination_param = request.args.get("destination")  # e.g., from recommended trip

    # Default empty form
    form_data = {
        "start_city": "",
        "destination": "",
        "duration": 1,
        "travel_type": "",
        "start_date": date.today().isoformat(),
        "budget_type": "Moderate",
        "transport_mode": "",
        "trip_style": ""
    }

    if prefill_flag and "latest_trip" in session:
        # Case 1: Try Again → prefill all values
        inputs = session["latest_trip"].get("inputs", {})
        form_data.update({
            "start_city": inputs.get("start_city", ""),
            "destination": inputs.get("destination", ""),
            "duration": inputs.get("duration", 1),
            "travel_type": inputs.get("travel_type", ""),
            "start_date": inputs.get("start_date", ""),
            "budget_type": inputs.get("budget_type", ""),
            "transport_mode": inputs.get("transport_mode", ""),
            "trip_style": inputs.get("trip_style", "")
        })
    elif destination_param:
        # Case 2: Clicked on recommendation → only destination prefilled
        form_data["destination"] = destination_param

    return render_template("create_trip.html", **form_data)


@app.route("/update-profile", methods=["POST"])
def update_profile():

    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    data = request.get_json()

    username = data.get("username")
    email = data.get("email")
    preferences = data.get("preferences", [])

    # convert list → JSON string for DB
    preferences_json = json.dumps(preferences)

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cursor.execute("""
            UPDATE users
            SET username=%s, email=%s, travel_preferences=%s
            WHERE id=%s
        """, (username, email, preferences_json, session["user_id"]))

        mysql.connection.commit()
        cursor.close()

        session["username"] = username  # update session

        return jsonify({"success": True})

    except Exception as e:
        print("Profile update error:", e)
        return jsonify({"success": False, "error": "Database error"}), 500
    

from werkzeug.security import check_password_hash, generate_password_hash

@app.route("/change-password", methods=["POST"])
def change_password():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    current = data.get("current_password")
    new_pass = data.get("new_password")
    confirm = data.get("confirm_password")

    if not current or not new_pass or not confirm:
         return jsonify({"error": "All password fields are required"}), 400
    # Check if new password matches confirm
    if new_pass != confirm:
        return jsonify({"error": "New password and confirm password do not match"}), 400

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT password FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()

    if not user or not check_password_hash(user["password"], current):
        return jsonify({"error": "Current password is incorrect"}), 400

    hashed = generate_password_hash(new_pass)
    cursor.execute("UPDATE users SET password=%s WHERE id=%s", (hashed, session["user_id"]))
    mysql.connection.commit()
    cursor.close()

    return jsonify({"success": True})

@app.route("/delete-account", methods=["POST"])
def delete_account():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM users WHERE id=%s", (session["user_id"],))
        mysql.connection.commit()
        cursor.close()
        
        # Clear the session
        session.clear()

        return jsonify({"success": True})
    except Exception as e:
        print("Error deleting account:", e)
        return jsonify({"success": False, "error": "Database error"}), 500

@app.route("/delete-account", methods=["GET"])
@app.route("/update-profile", methods=["GET"])
@app.route("/change-password", methods=["GET"])
def redirect_to_login():
    return redirect("/login")       

@app.route("/get-locationiq-key")
def get_locationiq_key():
    return {"key": os.getenv("LOCATIONIQ_KEY")}

@app.route("/.well-known/appspecific/com.chrome.devtools.json")
def dummy_well_known():
    return "", 204  # 204 = No Content

@app.after_request
def add_header(response):
    response.cache_control.no_store = True
    return response

from flask_session import Session

# Use server-side session
app.config["SESSION_TYPE"] = "filesystem"   # stores sessions in server filesystem
app.config["SESSION_FILE_DIR"] = "./flask_session"  # optional custom folder
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True    # signs session cookies
Session(app)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)