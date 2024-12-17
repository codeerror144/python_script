from flask import Flask, jsonify, request
from attendance import start_attendance_monitoring
from facial_recognition import process_frame
from fetch_rfid_uid import fetch_uid
import threading

app = Flask(__name__)



@app.before_request
def verify_token():
    
    token = request.headers.get("Authorization")
    if token != f"Bearer {SECRET_TOKEN}":
        return jsonify({"error": "Unauthorized"}), 403

@app.route('/logbook-monitoring', methods=['POST'])
def logbook_monitoring():
   
    threading.Thread(target=process_frame).start()
    return jsonify({"message": "Logbook monitoring has started."})

@app.route('/attendance-monitoring', methods=['POST'])
def attendance_monitoring():
    threading.Thread(target=start_attendance_monitoring).start()
    return jsonify({"message": "Attendance monitoring has started."})

@app.route('/fetch-rfid-uid', methods=['GET'])
def fetch_rfid():
    try:
        uid = fetch_uid()
        return jsonify({"uid": uid})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    print("Starting Flask API...")
    app.run(host='0.0.0.0', port=5000)
