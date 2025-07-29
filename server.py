from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import csv
from io import StringIO
import os
import pickle

app = Flask(__name__)
app.secret_key = 'supersecretkey'
DB_NAME = 'attendance.db'

# Initialize DB
def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            course TEXT NOT NULL,
            status TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            course TEXT NOT NULL,
            level TEXT NOT NULL,
            section TEXT NOT NULL,
            captures INTEGER DEFAULT 0,
            date_registered TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def mark_present(name, date, time):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT course FROM students WHERE name = ?", (name,))
    result = cursor.fetchone()
    if result:
        course = result[0]
        cursor.execute("""
            SELECT * FROM attendance WHERE name = ? AND date = ?
        """, (name, date))
        already_marked = cursor.fetchone()
        if not already_marked:
            cursor.execute("""
                INSERT INTO attendance (name, course, status, date, time)
                VALUES (?, ?, ?, ?, ?)
            """, (name, course, 'Present', date, time))
            conn.commit()
    conn.close()

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[2], password):
            session['admin'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid credentials')
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'admin' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/api/dashboard-data')
def dashboard_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, phone, course, level, section, date_registered FROM students")
    students = cursor.fetchall()
    conn.close()

    data = []
    for s in students:
        data.append({
            'id': s[0],
            'fullname': s[1],
            'index_number': f"DLIT2025A{s[0]:03}",
            'email': s[2],
            'phone': s[3],
            'course': s[4],
            'level': s[5],
            'section': s[6],
            'date_registered': s[7]
        })

    return jsonify(data)

@app.route('/register')
def register():
    if 'admin' not in session:
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/recognize')
def recognize():
    if 'admin' not in session:
        return redirect(url_for('login'))
    return render_template('recognize.html')

@app.route('/all_schedules')
def all_schedules():
    if 'admin' not in session:
        return redirect(url_for('login'))
    return render_template('all_schedules.html')

@app.route('/api/all_attendance')
def api_all_attendance():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT name, course, status, date, time FROM attendance ORDER BY date DESC, time DESC')
    rows = cursor.fetchall()
    conn.close()
    records = [
        {'name': row[0], 'course': row[1], 'status': row[2], 'date': row[3], 'time': row[4]}
        for row in rows
    ]
    return jsonify({'records': records})

@app.route('/download_csv')
def download_csv():
    if 'admin' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT name, course, status, date, time FROM attendance')
    data = cursor.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Course', 'Status', 'Date', 'Time'])
    writer.writerows(data)
    output.seek(0)

    return send_file(
        output,
        mimetype='text/csv',
        download_name='attendance.csv',
        as_attachment=True
    )

@app.route('/registered_users')
def registered_users():
    if 'admin' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template('registered_users.html', users=users)

@app.route("/create_user", methods=["GET", "POST"])
def create_user():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            conn.close()
            return "Username and password are required", 400

        hashed_pw = generate_password_hash(password)

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return "User already exists!", 409

        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
        conn.commit()

    cursor.execute("SELECT id, username FROM users")
    users = cursor.fetchall()
    conn.close()

    return render_template("create_user.html", users=users)

@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("create_user"))

@app.route('/train')
def train():
    if 'admin' not in session:
        return redirect(url_for('login'))
    return render_template('train.html')

@app.route('/todays_schedule')
def todays_schedule():
    if 'admin' not in session:
        return redirect(url_for('login'))
    return render_template('todays_schedule.html')

@app.route('/api/save-user', methods=['POST'])
def save_user():
    data = request.get_json()
    required_fields = ['name', 'email', 'phone', 'course', 'level', 'section']
    if not all(data.get(field) for field in required_fields):
        return jsonify({'message': 'All fields are required'}), 400

    name = data['name']
    email = data['email']
    phone = data['phone']
    course = data['course']
    level = data['level']
    section = data['section']
    date_registered = datetime.now().strftime('%Y-%m-%d')

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO students (name, email, phone, course, level, section, captures, date_registered)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (name, email, phone, course, level, section, 0, date_registered))
    student_id = c.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'message': 'Student registered successfully', 'student_id': student_id})

@app.route('/api/edit-student/<int:student_id>', methods=['PUT'])
def edit_student(student_id):
    data = request.get_json()
    fields = ['name', 'email', 'phone', 'course', 'level', 'section']
    updates = [data.get(field) for field in fields]

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE students SET name = ?, email = ?, phone = ?, course = ?, level = ?, section = ?
        WHERE id = ?
    ''', (*updates, student_id))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Student updated successfully'})

@app.route('/api/delete-user/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Student deleted successfully'}), 200

@app.route('/api/dashboard-cards')
def dashboard_cards():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM students")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT course) FROM students")
    total_courses = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM schedules")
    total_schedules = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM attendance")
    attendance_records = c.fetchone()[0]

    conn.close()

    return jsonify({
        'totalUsers': total_users,
        'totalCourses': total_courses,
        'totalSchedules': total_schedules,
        'attendanceRecords': attendance_records
    })

@app.route('/api/known_faces')
def get_known_faces():
    data = []
    for filename in os.listdir('encodings/'):
        with open(f'encodings/{filename}', 'rb') as f:
            encodings = pickle.load(f)
            label = filename.replace('.pkl', '')
            data.append({
                'label': label,
                'descriptors': [enc.tolist() for enc in encodings]
            })
    return jsonify(data)

@app.route('/api/mark_attendance', methods=['POST'])
def mark_attendance():
    name = request.json.get('name')
    now = datetime.now()
    mark_present(name, now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'))
    return jsonify({'status': 'success'})
dataset_dir = 'captured_faces'  # or your folder


@app.route('/captured_faces')
def captured_faces():
    images = []
    for student_folder in os.listdir(dataset_dir):
        folder_path = os.path.join(dataset_dir, student_folder)
        if os.path.isdir(captured_faces):
            for img_file in os.listdir(captured_faces):
                # Generate static URL for images
                img_url = url_for('static', filename=f'images/{student_folder}/{img_file}')
                images.append(img_url)
    return render_template('captured_faces.html', images=images)

@app.route('/images/<student>/<filename>')
def serve_image(student, filename):
    return send_from_directory(os.path.join(dataset_dir, student), filename)

import cv2
import numpy as np
import base64



# Directory to store face images
FACE_IMAGES_DIR = 'faces'

if not os.path.exists(FACE_IMAGES_DIR):
    os.makedirs(FACE_IMAGES_DIR)

@app.route('/api/add-user', methods=['POST'])
def add_user():
    data = request.get_json()
    # Save user data to database as needed
    # For simplicity, just return success
    return jsonify({'status': 'success', 'message': 'User added'})

@app.route('/api/train-face', methods=['POST'])
def train_face():
    data = request.get_json()
    image_data = data['image']
    name = data['name']
    # Decode base64 image
    header, encoded = image_data.split(',', 1)
    img_bytes = base64.b64decode(encoded)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # Save image for training
    filename = os.path.join(FACE_IMAGES_DIR, f"{name}.png")
    cv2.imwrite(filename, img)

    # Here, you can implement face detection with OpenCV
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    for (x, y, w, h) in faces:
        face_roi = gray[y:y+h, x:x+w]
        # Save or process face_roi as needed for training your model
        # For example, add to a dataset for training your face recognition model
        # This example just saves the detected face
        face_filename = os.path.join(FACE_IMAGES_DIR, f"{name}_face.png")
        cv2.imwrite(face_filename, face_roi)

    # TODO: Implement training your face recognition model with the dataset

    return jsonify({'status': 'success', 'message': 'Face trained'})


if __name__ == '__main__':
    initialize_db()
    app.run(debug=True)
