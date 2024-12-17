from mtcnn import MTCNN
import cv2
import numpy as np
import face_recognition
import pymysql
from datetime import datetime, timedelta
import os
import tkinter as tk
from tkinter import Label
from PIL import Image, ImageTk
import threading
from smartcard.System import readers
import logging
import time 
import threading



logging.basicConfig(filename='rfid_errors.log', level=logging.ERROR)


detector = MTCNN()


try:
    db = pymysql.connect(
        host="localhost",
        user="root",
        password="",
        database="slsubits_db"
    )
    print("Employee Attendance: Database connection successful.")
except Exception as e:
    print(f"Database connection failed: {e}")

cursor = db.cursor()


morning_login_start = datetime.strptime("08:00", "%H:%M").time()
morning_login_end = datetime.strptime("09:50", "%H:%M").time()
morning_logout_start = datetime.strptime("11:30", "%H:%M").time()
morning_logout_end = datetime.strptime("11:45", "%H:%M").time()

afternoon_login_start = datetime.strptime("12:00", "%H:%M").time()
afternoon_login_end = datetime.strptime("14:06", "%H:%M").time()
afternoon_logout_start = datetime.strptime("14:10", "%H:%M").time()
afternoon_logout_end = datetime.strptime("17:30", "%H:%M").time()


last_recognized = {}

def load_registered_employee_faces():
    known_face_encodings = []
    known_face_ids = []
    known_face_names = []
    cursor.execute("SELECT id, user_id, captured_image FROM biometrics WHERE user_id IN (SELECT id FROM users WHERE type = 'Employee')")
    results = cursor.fetchall()

    for row in results:
        user_id = row[1]
        img_path = row[2]
        
        if img_path.startswith("public/"):
            absolute_path = os.path.join("C:/laragon/www/bits_logbook", img_path)  
        else:
            absolute_path = os.path.join("C:/laragon/www/bits_logbook/public", img_path)  
        
       
        print(f"Trying to load image from: {absolute_path}")
        
        
        if os.path.exists(absolute_path):  
            try:
                image = face_recognition.load_image_file(absolute_path)
                face_encodings = face_recognition.face_encodings(image)
                if face_encodings:
                    known_face_encodings.append(face_encodings[0])
                    known_face_ids.append(user_id)

                    cursor.execute("SELECT name FROM users WHERE id = %s", (user_id,))
                    name_result = cursor.fetchone()
                    known_face_names.append(name_result[0] if name_result else "Unknown")
                else:
                    logging.error(f"No face encodings found for image at {absolute_path}")
            except Exception as e:
                logging.error(f"Error loading image {absolute_path}: {e}")
        else:
            logging.error(f"Image path {absolute_path} does not exist")
    
    return known_face_encodings, known_face_ids, known_face_names



def get_saved_rfid_for_user(user_id):
    cursor.execute("SELECT rfid_data FROM biometrics WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None


def read_rfid_tag():
    try:
        r = readers()
        if not r:
            return None  
        
        reader = r[0]
        connection = reader.createConnection()
        
        try:
            connection.connect()
        except Exception as e:
            logging.error(f"Failed to connect to the reader: {e}")
            return None
        
        get_uid = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        
        try:
            data, sw1, sw2 = connection.transmit(get_uid)
            if sw1 == 0x90 and sw2 == 0x00:
                return ''.join(format(x, '02X') for x in data).upper()
            else:
                logging.error(f"Failed to read RFID: SW1={sw1}, SW2={sw2}")
                return None
        except Exception as e:
            logging.error(f"Error reading RFID tag: {e}")
            return None
    except Exception as e:
        logging.error(f"Reader initialization failed: {e}")
        return None



def wait_for_rfid_tag(timeout=15):
    """Wait for RFID tag in a non-blocking manner with a timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        rfid_uid = read_rfid_tag()
        if rfid_uid:
            return rfid_uid
        time.sleep(0.1)  
    return None


def log_employee_attendance(user_id, attendance_type):
    current_time = datetime.now()
    log_time = current_time.time()
    current_date = current_time.date()

    
    if morning_login_start <= log_time <= morning_logout_end:
        session = "morning"
    elif afternoon_login_start <= log_time <= afternoon_logout_end:
        session = "afternoon"
    else:
        return "The Time is Out for Attendance"

    
    cursor.execute(
        """
        SELECT login_time, logout_time 
        FROM attendances 
        WHERE user_id = %s AND session = %s AND DATE(login_time) = %s
        """,
        (user_id, session, current_date)
    )
    result = cursor.fetchone()

    if result:
        if attendance_type == "login_time":
            if result[0] is not None:  
                return f"You already logged in for the {session} session today."
        elif attendance_type == "logout_time":
            if result[1] is not None:  
                return f"You already logged out for the {session} session today."

    if attendance_type == "login_time":
       
        if (morning_login_start <= log_time <= morning_login_end) or (afternoon_login_start <= log_time <= afternoon_login_end):
            cursor.execute(
                """
                INSERT INTO attendances (user_id, session, login_time) 
                VALUES (%s, %s, %s)
                """,
                (user_id, session, current_time)
            )
            db.commit()
            return f"Successfully Logged In for the {session} session."
        else:
            return "The Time is Out for Login"

    elif attendance_type == "logout_time":
     
        if (morning_logout_start <= log_time <= morning_logout_end) or (afternoon_logout_start <= log_time <= afternoon_logout_end):
            cursor.execute(
                """
                UPDATE attendances 
                SET logout_time = %s 
                WHERE user_id = %s AND session = %s AND DATE(login_time) = %s
                """,
                (current_time, user_id, session, current_date)
            )
            db.commit()
            return f"Successfully Logged Out for the {session} session."
        else:
            return "The Time is Out for Logout"



def update_message(message, message_label):
    message_label.config(text=message)



def handle_rfid_prompt(user_id, message_label, attendance_type):
    def rfid_check():
        update_message(f"Please Tap Your RFID tag to {'Login' if attendance_type == 'login_time' else 'Logout'}.", message_label)
        rfid_tag = wait_for_rfid_tag()  
        if rfid_tag:
            saved_rfid = get_saved_rfid_for_user(user_id)
            if rfid_tag == saved_rfid:
                result = log_employee_attendance(user_id, attendance_type)
                update_message(result, message_label)
            else:
                update_message("Invalid RFID tag. Attendance not logged.", message_label)
        else:
            update_message("RFID tag not detected. Ready for next user.", message_label)


    rfid_thread = threading.Thread(target=rfid_check, daemon=True)
    rfid_thread.start()

def process_camera_frame(camera, label, message_label, attendance_type):
    global last_recognized
    ret, frame = camera.read()
    if not ret:
        return None


    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    detected_faces = detector.detect_faces(rgb_small_frame)

    face_locations = []
    for face in detected_faces:
        x, y, width, height = face['box']
        top, right, bottom, left = y, x + width, y + height, x
        face_locations.append((top, right, bottom, left))

   
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
       
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.5)
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

        
        best_match_index = np.argmin(face_distances)
        is_recognized = matches[best_match_index] and face_distances[best_match_index] < 0.5

        if is_recognized:
            user_id = known_face_ids[best_match_index]
            employee_name = known_face_names[best_match_index]
            now = datetime.now()

            # Prevent duplicate recognition within a time window
            if user_id not in last_recognized or (now - last_recognized[user_id] > timedelta(seconds=30)):
                last_recognized[user_id] = now
                handle_rfid_prompt(user_id, message_label, attendance_type)

            # Draw a green rectangle for recognized faces
            top, right, bottom, left = [int(coord * 4) for coord in [top, right, bottom, left]]
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, employee_name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        else:
            
            employee_name = "Unknown"
            top, right, bottom, left = [int(coord * 4) for coord in [top, right, bottom, left]]
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.putText(frame, employee_name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)


    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame)
    imgtk = ImageTk.PhotoImage(image=img)
    label.imgtk = imgtk
    label.configure(image=imgtk)



def start_camera_thread(camera, label, message_label, attendance_type):
    def run():
        while True:
            process_camera_frame(camera, label, message_label, attendance_type)
    camera_thread = threading.Thread(target=run, daemon=True)
    camera_thread.start()

def start_attendance_monitoring():
    root = tk.Tk()
    root.title("Employee Attendance Monitoring")
    root.geometry("800x600")
    root.resizable(True, True)

    header = tk.Label(root, text="Employee Attendance System", font=("Arial", 24), bg="blue", fg="white")
    header.pack(fill=tk.X, pady=10)

    message_label = tk.Label(root, text="Please position your face in front of the camera for attendance check.", font=("Arial", 14), fg="black")
    message_label.pack(pady=10)

    login_frame = tk.Frame(root, bd=2, relief=tk.SOLID)
    login_frame.pack(side=tk.LEFT, padx=20, pady=20)

    login_title = tk.Label(login_frame, text="Login Camera", font=("Arial", 16, "bold"), fg="green")
    login_title.pack(pady=5)

    login_label = Label(login_frame)
    login_label.pack()

    logout_frame = tk.Frame(root, bd=2, relief=tk.SOLID)
    logout_frame.pack(side=tk.RIGHT, padx=20, pady=20)

    logout_title = tk.Label(logout_frame, text="Logout Camera", font=("Arial", 16, "bold"), fg="red")
    logout_title.pack(pady=5)

    logout_label = Label(logout_frame)
    logout_label.pack()

    global known_face_encodings, known_face_ids, known_face_names
    known_face_encodings, known_face_ids, known_face_names = load_registered_employee_faces()

    login_camera = cv2.VideoCapture(0)
    logout_camera = cv2.VideoCapture(1)

    start_camera_thread(login_camera, login_label, message_label, "login_time")
    start_camera_thread(logout_camera, logout_label, message_label, "logout_time")

    root.mainloop()

# Start the system
start_attendance_monitoring()
