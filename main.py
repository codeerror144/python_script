from flask import Flask, render_template, jsonify
from datetime import datetime
import mysql.connector
import os
import subprocess

app = Flask(__name__)

# Database configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "slsubits_db"
}

# Home Route (Dashboard)
@app.route("/")
def index():
    return render_template("login.html")

# Function to fetch statistics for the dashboard
@app.route("/dashboard_data")
def dashboard_data():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # Today's Logged-In Users
        today = datetime.now().strftime("%Y-%m-%d")
        query_today = f"SELECT COUNT(DISTINCT user_id) FROM attendances WHERE DATE(login_time) = '{today}'"
        cursor.execute(query_today)
        users_logged_today = cursor.fetchone()[0]

        # Recent Entries
        query_recent = f"SELECT COUNT(*) FROM attendances WHERE login_time >= NOW() - INTERVAL 1 DAY"
        cursor.execute(query_recent)
        recent_entries = cursor.fetchone()[0]

        # Active Users
        query_active = f"SELECT COUNT(*) FROM attendances WHERE logout_time IS NULL"
        cursor.execute(query_active)
        active_users = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return jsonify({
            "users_logged_today": users_logged_today,
            "recent_entries": recent_entries,
            "active_users": active_users
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# Run Facial Recognition Script
@app.route("/run_facial_recognition")
def run_facial_recognition():
    try:
        subprocess.run(["python", os.path.join( "facial_recognition.py")])
        return "Facial Recognition Script Executed Successfully"
    except Exception as e:
        return f"Error: {str(e)}"

# Run Attendance Script
@app.route("/run_attendance")
def run_attendance():
    try:
        subprocess.run(["python", os.path.join( "attendance.py")])
        return "Attendance Script Executed Successfully"
    except Exception as e:
        return f"Error: {str(e)}"

# Run Flask App
if __name__ == "__main__":
    app.run(debug=True)
