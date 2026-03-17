from flask import Blueprint, request, jsonify, render_template, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import re
import json  # For handling travel_preferences
import MySQLdb.cursors
auth_routes = Blueprint('auth', __name__)

mysql = None

def init_mysql(mysql_instance):
    global mysql
    mysql = mysql_instance

EMAIL_REGEX = r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'


# ----------------- Render login page -----------------
@auth_routes.route('/login', methods=['GET'])
def login_page():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('login.html')


# ----------------- Render signup page -----------------
@auth_routes.route('/signup', methods=['GET'])
def signup_page():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('signup.html')


# ---------------- Signup API ----------------
@auth_routes.route('/signup', methods=['POST'])
def signup_api():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    travel_preferences = data.get('travel_preferences', [])  # Get preferences from front-end

    if not username or not email or not password:
        return jsonify({'error': 'All fields are required'}), 400

    if not re.match(EMAIL_REGEX, email.lower()):
        return jsonify({'error': 'Invalid email format'}), 400

    hashed_password = generate_password_hash(password)

    # Convert preferences list to JSON string for storage
    travel_preferences_json = json.dumps(travel_preferences)

    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(
            "INSERT INTO users (username, email, password, travel_preferences) VALUES (%s, %s, %s, %s)",
            (username, email.lower(), hashed_password, travel_preferences_json)
        )
        mysql.connection.commit()
        cur.close()

        return jsonify({'message': 'User created successfully!'}), 201

    except Exception as e:
        error_code = e.args[0] if len(e.args) > 0 else None

        # Duplicate entry error (MySQL 1062)
        if error_code == 1062:
            return jsonify({
                'error': 'Account already exists. Redirecting to login...',
                'redirect': '/login'
            }), 409

        print("Signup error:", e)
        return jsonify({'error': 'Server error, try again later.'}), 500


# ---------------- Login API ----------------
@auth_routes.route('/login', methods=['POST'])
def login_api():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    if not re.match(EMAIL_REGEX, email.lower()):
        return jsonify({'error': 'Invalid email format'}), 400

    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(
            "SELECT id, username, email, password, travel_preferences FROM users WHERE email=%s",
            (email.lower(),)
        )
        user = cur.fetchone()
        cur.close()

        if not user:
    # Email not found → account deleted or never existed
            return jsonify({'error': 'Account does not exist'}), 404

        if not check_password_hash(user['password'], password):
    # Wrong password
            return jsonify({'error': 'Incorrect password'}), 401

# Successful login
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['preferences'] = json.loads(user['travel_preferences']) if user['travel_preferences'] else []
        return jsonify({'message': 'Login successful'}), 200

    except Exception as e:
        print("Login error:", e)
        return jsonify({'error': 'Server error, try again later'}), 500


# ---------------- Logout ----------------
@auth_routes.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ---------------- Forgot Password Page ----------------
@auth_routes.route('/forgot-password', methods=['GET'])
def forgot_password_page():
    return render_template('forgot.html')


# ---------------- Reset Password Page ----------------
@auth_routes.route('/reset-password', methods=['GET'])
def reset_password_page():
    return render_template('reset_password.html')


# ---------------- Reset Password API ----------------
@auth_routes.route('/reset-password', methods=['POST'])
def reset_password_api():
    data = request.json
    email = data.get('email')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not email or not new_password or not confirm_password:
        return jsonify({'error': 'All fields are required'}), 400

    if new_password != confirm_password:
        return jsonify({'error': 'Passwords do not match'}), 400

    if not re.match(EMAIL_REGEX, email.lower()):
        return jsonify({'error': 'Invalid email format'}), 400

    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT id FROM users WHERE email=%s", (email.lower(),))
        user = cur.fetchone()

        if not user:
            cur.close()
            return jsonify({'error': 'Email not found'}), 404

        hashed_password = generate_password_hash(new_password)
        cur.execute(
            "UPDATE users SET password=%s WHERE email=%s",
            (hashed_password, email.lower())
        )
        mysql.connection.commit()
        cur.close()

        return jsonify({'message': 'Password reset successful'}), 200

    except Exception as e:
        print("Reset password error:", e)
        return jsonify({'error': 'Server error, try again later'}), 500