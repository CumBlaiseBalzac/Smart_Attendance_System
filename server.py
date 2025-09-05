from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import csv
from io import StringIO
import os
import pickle
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import cv2
import numpy as np
import base64



app = Flask(__name__)
app.secret_key = 'supersecretkey'
DB_NAME = 'attendance.db'


def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create students table with all columns, including last_attendance
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        course_id INTEGER,
        course_code TEXT,
        level TEXT,
        section TEXT,
        captures INTEGER,
        date_registered TEXT,
        FOREIGN KEY (course_id) REFERENCES courses(id)
    )
    ''')

    # Create other tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
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
    cursor.execute('''
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    date TEXT,
    time TEXT,
    status TEXT DEFAULT 'Present',
    FOREIGN KEY(student_id) REFERENCES students(id)
)
''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    ''')

    # Mapping table for many-to-many relationship between students and courses
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS student_courses (
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        PRIMARY KEY (student_id, course_id),
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    )
    ''')
    
    # Backfill courses from legacy students.course values
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO courses (name)
            SELECT DISTINCT course FROM students
            WHERE course IS NOT NULL AND TRIM(course) <> ''
        ''')
        cursor.execute('''
            INSERT OR IGNORE INTO student_courses (student_id, course_id)
            SELECT s.id, c.id
            FROM students s
            JOIN courses c ON c.name = s.course
            WHERE s.course IS NOT NULL AND TRIM(s.course) <> ''
        ''')
    except Exception as e:
        print(f"Backfill mapping failed or not needed: {e}")

    # Add unique constraint to prevent duplicate attendance (if it doesn't exist)
    try:
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique 
            ON attendance (name, course, date)
        ''')
        print("Added unique constraint to prevent duplicate attendance")
    except Exception as e:
        print(f"Unique constraint may already exist or failed to create: {e}")

    conn.commit()
    conn.close()
'''
def mark_present(student_id, course_id, date, time):
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()

    # Ensure student exists
    c.execute("SELECT 1 FROM students WHERE id = ?", (student_id,))
    if not c.fetchone():
        conn.close()
        return  # student_id invalid

    # Prevent duplicate attendance
    c.execute("""
        SELECT 1 
          FROM attendance 
         WHERE student_id = ? 
           AND course_id = ? 
           AND date = ?
    """, (student_id, course_id, date))
    if c.fetchone():
        conn.close()
        return  

    # Insert the new attendance record
    c.execute("""
        INSERT INTO attendance (student_id, course_id, date, time, status)
        VALUES (?, ?, ?, ?, 'Present')
    """, (student_id, course_id, date, time))
    conn.commit()
    conn.close()
'''
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
    # Aggregate courses per student using the mapping table if present; fallback to students.course
    cursor.execute('''
        SELECT s.id,
               s.name,
               s.email,
               s.phone,
               COALESCE(
                   (
                       SELECT GROUP_CONCAT(c.name, ', ')
                       FROM student_courses sc
                       JOIN courses c ON c.id = sc.course_id
                       WHERE sc.student_id = s.id
                   ), s.course
               ) AS courses,
               s.course_code,
               s.level,
               s.section,
               s.date_registered
        FROM students s
        GROUP BY s.id
        ORDER BY s.name
    ''')
    rows = cursor.fetchall()
    conn.close()

    # De-duplicate students by email (preferred) or by normalized name, merging courses
    merged = {}
    for r in rows:
        sid, name, email, phone, courses_csv, course_code, level, section, date_registered = r
        key = (email or '').strip().lower() or (name or '').strip().lower()
        # Prepare courses set from comma-separated string
        courses_set = set()
        if courses_csv:
            for part in str(courses_csv).split(','):
                cname = part.strip()
                if cname:
                    courses_set.add(cname)
        if key not in merged:
            merged[key] = {
                'id': sid,
                'fullname': name,
                'email': email,
                'phone': phone,
                'courses': courses_set,
                'course_code': course_code,
                'level': level,
                'section': section,
                'date_registered': date_registered,
            }
        else:
            m = merged[key]
            # Keep the smallest id as canonical and use its courses only
            if sid < m['id']:
                m['id'] = sid
                m['courses'] = set(courses_set)
            # Prefer non-empty values for contact/fields if current is empty
            if (not m['fullname']) and name:
                m['fullname'] = name
            if (not m['email']) and email:
                m['email'] = email
            if (not m['phone']) and phone:
                m['phone'] = phone
            if (not m['course_code']) and course_code:
                m['course_code'] = course_code
            if (not m['level']) and level:
                m['level'] = level
            if (not m['section']) and section:
                m['section'] = section
            # Keep earliest registration date if both present (ISO yyyy-mm-dd compares lexicographically)
            if m['date_registered'] and date_registered:
                m['date_registered'] = min(m['date_registered'], date_registered)
            elif date_registered:
                m['date_registered'] = date_registered
            # IMPORTANT: Do not merge courses from duplicates; display canonical student's set only.

    # Build response list
    data = []
    for m in merged.values():
        course_str = ', '.join(sorted(m['courses'])) if m['courses'] else ''
        data.append({
            'id': m['id'],
            'fullname': m['fullname'],
            'index_number': f"DLIT2025A{m['id']:03}",
            'email': m['email'],
            'phone': m['phone'],
            'course': course_str,
            'course_code': m['course_code'],
            'level': m['level'],
            'section': m['section'],
            'date_registered': m['date_registered']
        })

    # Sort by name for stable output
    data.sort(key=lambda x: (x['fullname'] or '').lower())
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

@app.route('/todays_attendance')
def todays_attendance():
    return render_template('todays_attendance.html')

@app.route('/select_course')
def select_course():
    return render_template('select_course.html')

@app.route('/bulk_attendance')
def bulk_attendance_page():
    if 'admin' not in session:
        return redirect(url_for('login'))
    return render_template('bulk_attendance.html')

@app.route('/api/all_attendance')
def api_all_attendance():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, course, status, date, time FROM attendance ORDER BY date DESC, time DESC')
    rows = cursor.fetchall()
    conn.close()
    records = [
        {
            'id': row[0],
            'name': row[1],
            'course': row[2],
            'status': row[3],
            'date': row[4],
            'time': row[5]
        }
        for row in rows
    ]
    return jsonify({'records': records})

@app.route('/api/delete-attendance/<int:attendance_id>', methods=['DELETE'])
def delete_attendance(attendance_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE id = ?", (attendance_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Attendance record deleted'}), 200


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

@app.route('/api/todays-present')
def get_todays_present():
    today_date = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT s.id, s.name, s.email, s.phone, s.course, s.level, s.section, s.date_registered
        FROM students s
        JOIN attendance a ON s.name = a.name
        WHERE a.date = ?
    ''', (today_date,))
    students = cursor.fetchall()
    conn.close()

    data = []
    for s in students:
        data.append({
            'id': s[0],
            'fullname': s[1],
            'email': s[2],
            'phone': s[3],
            'course': s[4],
            'level': s[5],
            'section': s[6],
            'date_registered': s[7]
        })
    return jsonify(data)

@app.route("/api/save-user", methods=["POST"])
def save_user():
    data = request.get_json()

    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    # Accept an array of course names for multi-course selection, fallback to single 'course'
    course_names = data.get('course_names') or []
    single_course = (data.get('course') or '').strip()
    if single_course and not course_names:
        course_names = [single_course]
    course_code = (data.get('course_code') or '').strip()
    level = (data.get('level') or '').strip()
    section = (data.get('section') or '').strip()
    date_registered = datetime.now().strftime('%Y-%m-%d')

    if not all([name, email, phone, level, section]) or len(course_names) == 0:
        return jsonify({'status': 'error', 'message': 'Missing required fields or no courses selected'}), 400

    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # Find existing student by email (preferred) or name
        student_id = None
        c.execute("SELECT id FROM students WHERE email = ?", (email,))
        row = c.fetchone()
        if row:
            student_id = row[0]
            # Update existing student info
            c.execute('''
                UPDATE students
                   SET name = ?, phone = ?, level = ?, section = ?
                 WHERE id = ?
            ''', (name, phone, level, section, student_id))
        else:
            c.execute("SELECT id FROM students WHERE name = ?", (name,))
            row2 = c.fetchone()
            if row2:
                student_id = row2[0]
                c.execute('''
                    UPDATE students
                       SET email = ?, phone = ?, level = ?, section = ?
                     WHERE id = ?
                ''', (email, phone, level, section, student_id))
            else:
                # Insert new student; keep legacy columns course/course_code for compatibility (use first course)
                first_course = course_names[0] if course_names else ''
                c.execute('''
                    INSERT INTO students (name, email, phone, course, course_code, level, section, captures, date_registered)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, email, phone, first_course, course_code, level, section, 0, date_registered))
                student_id = c.lastrowid

        # Ensure courses exist and map them to the student
        for cname in course_names:
            cname = (cname or '').strip()
            if not cname:
                continue
            c.execute("INSERT OR IGNORE INTO courses (name) VALUES (?)", (cname,))
            c.execute("SELECT id FROM courses WHERE name = ?", (cname,))
            crow = c.fetchone()
            if crow:
                cid = crow[0]
                c.execute("INSERT OR IGNORE INTO student_courses (student_id, course_id) VALUES (?, ?)", (student_id, cid))

        # Save face image if provided
        image_data = data.get('image')
        if image_data:
            header, encoded = image_data.split(',', 1)
            img_bytes = base64.b64decode(encoded)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            folder_path = os.path.join('captured_faces', name)
            os.makedirs(folder_path, exist_ok=True)
            image_path = os.path.join(folder_path, 'student.png')
            cv2.imwrite(image_path, img)

        conn.commit()
        
        return jsonify({'status': 'success', 'message': 'Student registered/updated successfully', 'student_id': student_id})

    except sqlite3.Error as e:
        return jsonify({'status': 'error', 'message': f'Database error: {str(e)}'}), 500

    finally:
        conn.close()

@app.route('/api/edit-student/<id>', methods=['PUT'])
def edit_student(id):
    data = request.get_json()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Fetch existing student record
    cursor.execute("SELECT * FROM students WHERE id = ?", (id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student not found"}), 404

    # Use existing or new values
    name = data.get('fullname', student[1])
    email = data.get('email', student[2])
    phone = data.get('phone', student[3])
    course = data.get('course', student[4])
    course_code = data.get('course_code', student[5])  # handle course_code
    level = data.get('level', student[6])
    section = data.get('section', student[7])

    # Update record
    cursor.execute('''
        UPDATE students SET name=?, email=?, phone=?, course=?, course_code=?, level=?, section=?
        WHERE id=?
    ''', (name, email, phone, course, course_code, level, section, id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Student updated"})

@app.route('/api/delete-user/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Student deleted successfully'}), 200

@app.route('/api/students/<int:student_id>/courses', methods=['GET'])
def get_student_courses(student_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT c.name
          FROM student_courses sc
          JOIN courses c ON c.id = sc.course_id
         WHERE sc.student_id = ?
         ORDER BY c.name
    ''', (student_id,))
    names = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({'courses': names})

@app.route('/api/students/<int:student_id>/courses', methods=['PUT','POST'])
def set_student_courses(student_id):
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Admin access required'}), 401
    data = request.get_json(force=True) or {}
    course_names = data.get('course_names') or []
    # Normalize names and dedupe
    norm = []
    seen = set()
    for n in course_names:
        s = (n or '').strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            norm.append(s)
    if len(norm) == 0:
        return jsonify({'status': 'error', 'message': 'At least one course is required'}), 400
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Ensure student exists
        c.execute('SELECT id FROM students WHERE id = ?', (student_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Student not found'}), 404

        c.execute('BEGIN IMMEDIATE')
        # Clear existing mappings
        c.execute('DELETE FROM student_courses WHERE student_id = ?', (student_id,))
        # Upsert courses and re-map
        first_course = ''
        for idx, cname in enumerate(norm):
            c.execute('INSERT OR IGNORE INTO courses (name) VALUES (?)', (cname,))
            c.execute('SELECT id FROM courses WHERE name = ?', (cname,))
            cid = c.fetchone()[0]
            c.execute('INSERT OR IGNORE INTO student_courses (student_id, course_id) VALUES (?, ?)', (student_id, cid))
            if idx == 0:
                first_course = cname
        # Update legacy column for compatibility
        c.execute('UPDATE students SET course = ? WHERE id = ?', (first_course, student_id))

        c.execute('COMMIT')
        conn.close()
        return jsonify({'status': 'success', 'message': 'Courses updated successfully'})
    except Exception as e:
        try:
            c.execute('ROLLBACK')
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return jsonify({'status': 'error', 'message': f'Failed to set courses: {str(e)}'}), 500

@app.route('/api/dashboard-cards')
def dashboard_cards():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Count unique students by email (preferred) or name to align with dashboard table de-duplication
    c.execute("SELECT name, email FROM students")
    keys = set()
    for name, email in c.fetchall():
        key = (email or '').strip().lower() or (name or '').strip().lower()
        if key:
            keys.add(key)
    total_users = len(keys)

    c.execute("SELECT COUNT(*) FROM courses")
    total_courses = c.fetchone()[0]

    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today,))
    total_schedules = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM attendance")
    attendance_records = c.fetchone()[0]

    conn.close()

    resp = jsonify({
        'totalUsers': total_users,
        'totalCourses': total_courses,
        'totalSchedules': total_schedules,  
        'attendanceRecords': attendance_records,
    })
    # Prevent caching so manual refresh always reflects current state
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@app.route('/api/known_faces')
def get_known_faces():
    enc_path = os.path.join(os.getcwd(), 'encodings.pkl')

    if not os.path.exists(enc_path):
        return jsonify({'error': 'encodings.pkl not found'}), 500

    with open(enc_path, 'rb') as f:
        data = pickle.load(f)

    encodings = data['encodings']
    names = data['names']

   
    known = {}
    for name, enc in zip(names, encodings):
        if name not in known:
            known[name] = []
        known[name].append(enc)

    result = []
    for label, descriptors in known.items():
        result.append({
            'label': label,
            'descriptors': [enc.tolist() for enc in descriptors]
        })

    return jsonify(result)

def mark_present_by_name(student_name, course_identifier, date, time):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Find student by name
    c.execute("SELECT id FROM students WHERE name = ?", (student_name,))
    result = c.fetchone()
    if not result:
        conn.close()
        return 'error', 'Student not found', 404
    student_id = result[0]

    # Resolve course name
    course_name = course_identifier
    if isinstance(course_identifier, int):
        c.execute("SELECT name FROM courses WHERE id = ?", (course_identifier,))
        course_row = c.fetchone()
        if course_row:
            course_name = course_row[0]
        else:
            conn.close()
            return 'error', 'Course not found', 400

    # Ensure course exists
    c.execute("SELECT id FROM courses WHERE name = ?", (course_name,))
    row_course = c.fetchone()
    if not row_course:
        conn.close()
        return 'error', 'Course not found', 400
    course_id = row_course[0]

    # Validate enrollment: student must be registered to this course
    c.execute("""
        SELECT 1
          FROM student_courses
         WHERE student_id = ? AND course_id = ?
    """, (student_id, course_id))
    if not c.fetchone():
        conn.close()
        return 'error', 'Student not registered for the selected course', 403

    # Check for existing attendance (primary: by student_id)
    c.execute("SELECT 1 FROM attendance WHERE student_id = ? AND course = ? AND date = ?", (student_id, course_name, date))
    if c.fetchone():
        conn.close()
        return 'error', 'Attendance already marked for this student and course today', 400
    
    # Fallback check by name
    c.execute("SELECT 1 FROM attendance WHERE name = ? AND course = ? AND date = ?", (student_name, course_name, date))
    if c.fetchone():
        conn.close()
        return 'error', 'Attendance already marked for this student and course today', 400

    # Insert attendance with name and course (matching existing schema)
    c.execute("INSERT INTO attendance (name, course, student_id, date, time, status) VALUES (?, ?, ?, ?, ?, 'Present')",
              (student_name, course_name, student_id, date, time))
    conn.commit()
    conn.close()
    return 'success', 'Attendance marked', 200

@app.route('/api/mark_attendance', methods=['POST'])
def mark_attendance():
    payload     = request.get_json(force=True)
    student_name= payload.get('name')
    # Expect either course_id or course_name
    course_id   = payload.get('course_id')
    course_name = payload.get('course_name')

    if not student_name or not (course_id or course_name):
        return jsonify(status='error',
                       message='Missing student name or course info'), 400

    now      = datetime.utcnow()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')

    # Pass course_id int, or course_name string
    identifier = course_id if course_id else course_name
    status, message, code = mark_present_by_name(student_name,
                                                 identifier,
                                                 date_str,
                                                 time_str)
    return jsonify(status=status, message=message), code



def mark_present(name, course_id, date, time):
    print(f"Marking present: {name} for course_id {course_id} on {date} {time}")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Find student by name
    c.execute("SELECT id FROM students WHERE name = ?", (name,))
    result = c.fetchone()
    if not result:
        print("Student not found")
        conn.close()
        return
    student_id = result[0]
    
    # Get course name for consistency with attendance table schema
    course_name = None
    if isinstance(course_id, int):
        c.execute("SELECT name FROM courses WHERE id = ?", (course_id,))
        course_row = c.fetchone()
        if course_row:
            course_name = course_row[0]
        else:
            print("Course not found")
            conn.close()
            return
    else:
        course_name = course_id  # Assume it's already a course name
    
    # IMPROVED: Check for existing attendance using multiple strategies
    # Check by student_id and course_name (most reliable)
    c.execute("SELECT 1 FROM attendance WHERE student_id = ? AND course = ? AND date = ?", 
              (student_id, course_name, date))
    if c.fetchone():
        print("Attendance already marked (by student_id and course)")
        conn.close()
        return
    
    # Additional check by name and course (fallback)
    c.execute("SELECT 1 FROM attendance WHERE name = ? AND course = ? AND date = ?", 
              (name, course_name, date))
    if c.fetchone():
        print("Attendance already marked (by name and course)")
        conn.close()
        return
    
    # Insert attendance record with both name and student_id for consistency
    c.execute("INSERT INTO attendance (name, course, student_id, date, time, status) VALUES (?, ?, ?, ?, ?, 'Present')",
              (name, course_name, student_id, date, time))
    conn.commit()
    conn.close()
    print("Attendance marked successfully")

dataset_dir = 'captured_faces'
@app.route('/captured_faces')
def captured_faces():
    images = []
    for student_folder in os.listdir(dataset_dir):
        folder_path = os.path.join(dataset_dir, student_folder)
        if os.path.isdir(folder_path):
            for img_file in os.listdir(folder_path):
                # Generate URL to serve image
                img_url = url_for('serve_image', student=student_folder, filename=img_file)
                images.append(img_url)
    return render_template('captured_faces.html', images=images)

@app.route('/images/<student>/<filename>')
def serve_image(student, filename):
    return send_from_directory(os.path.join(dataset_dir, student), filename)


FACE_IMAGES_DIR = 'faces'

if not os.path.exists(FACE_IMAGES_DIR):
    os.makedirs(FACE_IMAGES_DIR)

@app.route('/api/add-user', methods=['POST'])
def add_user():
    data = request.get_json()
    
    return jsonify({'status': 'success', 'message': 'User added'})

# @app.route('/api/train-face', methods=['POST'])
# def train_face():
    data = request.get_json()
    image_data = data['image']
    name = data['name']
    
    header, encoded = image_data.split(',', 1)
    img_bytes = base64.b64decode(encoded)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    filename = os.path.join(FACE_IMAGES_DIR, f"{name}.png")
    cv2.imwrite(filename, img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    for (x, y, w, h) in faces:
        face_roi = gray[y:y+h, x:x+w]
     
        face_filename = os.path.join(FACE_IMAGES_DIR, f"{name}_face.png")
        cv2.imwrite(face_filename, face_roi)

    return jsonify({'status': 'success', 'message': 'Face trained'})

import os
import pickle
import face_recognition
from flask import jsonify, request
from datetime import date


FACE_IMAGES_DIR = 'captured_faces'
ENCODINGS_FILE = 'encodings.pkl'

@app.route('/api/train-face', methods=['POST'])
def train_face():
    all_encodings = []
    all_names = []
    trained = 0

    if not os.path.exists(FACE_IMAGES_DIR):
        return jsonify({'status': 'error', 'message': 'Image folder not found'}), 400

    for person_name in os.listdir(FACE_IMAGES_DIR):
        person_dir = os.path.join(FACE_IMAGES_DIR, person_name)
        if not os.path.isdir(person_dir):
            continue

        for filename in os.listdir(person_dir):
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue

            image_path = os.path.join(person_dir, filename)
            image = face_recognition.load_image_file(image_path)
            face_locations = face_recognition.face_locations(image)
            face_encs = face_recognition.face_encodings(image, face_locations)

            for enc in face_encs:
                all_encodings.append(enc)
                all_names.append(person_name)

        if face_encs:
            trained += 1

    if not all_encodings:
        return jsonify({'status': 'error', 'message': 'No faces found for training'}), 400

    with open(ENCODINGS_FILE, 'wb') as f:
        pickle.dump({'encodings': all_encodings, 'names': all_names}, f)
        print("Encodings saved to:", os.path.abspath(ENCODINGS_FILE))

    return jsonify({
        'status': 'success',
        'message': f'Trained {trained} person(s)'
    })

@app.route('/api/absent-today')
def get_absent_students():
    today_date = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Get all students
    cursor.execute('SELECT id, name FROM students')
    all_students = cursor.fetchall()

    # Get students present today
    cursor.execute('''
        SELECT DISTINCT name FROM attendance WHERE date = ?
    ''', (today_date,))
    present_students = set(row[0] for row in cursor.fetchall())

    absentees = [student for student in all_students if student[1] not in present_students]

    data = []
    for s in absentees:
        # Fetch full student info
        cursor.execute('''
            SELECT id, name, email, phone, course, level, section, date_registered
            FROM students WHERE id = ?
        ''', (s[0],))
        student = cursor.fetchone()
        data.append({
            'id': student[0],
            'fullname': student[1],
            'email': student[2],
            'phone': student[3],
            'course': student[4],
            'level': student[5],
            'section': student[6],
            'date_registered': student[7]
        })

    conn.close()
    return jsonify(data)

@app.route('/api/students-by-course/<course_name>')
def get_students_by_course(course_name):
    """Get unique students enrolled in a specific course.
    De-duplicates by email (preferred) or normalized full name, selecting the smallest student id as canonical.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get all students for the specified course via mapping table
    cursor.execute('''
        SELECT s.id, s.name, s.email, s.phone, s.level, s.section, s.date_registered
        FROM students s
        JOIN student_courses sc ON sc.student_id = s.id
        JOIN courses c ON c.id = sc.course_id
        WHERE c.name = ?
        ORDER BY s.name
    ''', (course_name,))
    rows = cursor.fetchall()
    
    # Check which students are already marked present today (by name for backward compat)
    today_date = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT DISTINCT name FROM attendance 
        WHERE course = ? AND date = ?
    ''', (course_name, today_date))
    present_today_names = set(row[0].strip().lower() for row in cursor.fetchall() if row[0])
    
    # De-duplicate by email or normalized name; keep smallest id as canonical
    merged = {}
    for sid, name, email, phone, level, section, date_registered in rows:
        key = (email or '').strip().lower() or (name or '').strip().lower()
        if not key:
            # Fallback: use id to avoid dropping anonymous rows
            key = f'id:{sid}'
        if key not in merged:
            merged[key] = {
                'id': sid,
                'name': name,
                'email': email,
                'phone': phone,
                'level': level,
                'section': section,
                'date_registered': date_registered,
                'is_present_today': (name or '').strip().lower() in present_today_names,
            }
        else:
            m = merged[key]
            # Use the smallest id as canonical and prefer non-empty fields
            if sid < m['id']:
                m['id'] = sid
                m['name'] = name or m['name']
                m['email'] = email or m['email']
                m['phone'] = phone or m['phone']
                m['level'] = level or m['level']
                m['section'] = section or m['section']
                m['date_registered'] = min(m['date_registered'], date_registered) if (m['date_registered'] and date_registered) else (m['date_registered'] or date_registered)
            else:
                # Fill missing fields from this duplicate row
                if not m['name'] and name: m['name'] = name
                if not m['email'] and email: m['email'] = email
                if not m['phone'] and phone: m['phone'] = phone
                if not m['level'] and level: m['level'] = level
                if not m['section'] and section: m['section'] = section
                if m['date_registered'] and date_registered:
                    m['date_registered'] = min(m['date_registered'], date_registered)
                elif date_registered:
                    m['date_registered'] = date_registered
            # If any duplicate is present today, mark present
            if (name or '').strip().lower() in present_today_names:
                m['is_present_today'] = True
    
    data = []
    for m in merged.values():
        data.append({
            'id': m['id'],
            'name': m['name'],
            'email': m['email'],
            'phone': m['phone'],
            'course': course_name,
            'level': m['level'],
            'section': m['section'],
            'date_registered': m['date_registered'],
            'is_present_today': m['is_present_today']
        })
    
    # Sort by name
    data.sort(key=lambda x: (x['name'] or '').lower())
    conn.close()
    return jsonify(data)

@app.route('/api/bulk-attendance', methods=['POST'])
def bulk_attendance():
    """Mark attendance for multiple students at once"""
    data = request.get_json()
    course_name = data.get('course_name')
    present_students = data.get('present_students', [])  # List of student IDs
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    time_str = datetime.now().strftime('%H:%M:%S')
    
    if not course_name:
        return jsonify({'status': 'error', 'message': 'Course name is required'}), 400
    
    if not present_students:
        return jsonify({'status': 'error', 'message': 'No students selected'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    success_count = 0
    error_count = 0
    updated_count = 0
    skipped_count = 0
    messages = []
    
    try:
        # Begin transaction for atomicity - this ensures all-or-nothing behavior
        cursor.execute('BEGIN IMMEDIATE')
        
        # Process each student ID exactly once
        processed_students = set()  # Track processed students to avoid double-processing
        
        for student_id in present_students:
            # Skip if we've already processed this student in this batch
            if student_id in processed_students:
                skipped_count += 1
                messages.append(f'Skipped duplicate student ID {student_id} in selection')
                continue
                
            processed_students.add(student_id)
            
            # Get student info
            cursor.execute('SELECT name FROM students WHERE id = ?', (student_id,))
            student = cursor.fetchone()
            if not student:
                error_count += 1
                messages.append(f'Student with ID {student_id} not found')
                continue
            
            student_name = student[0]
            
            # ULTRA-COMPREHENSIVE DUPLICATE CHECK
            # Check ALL possible combinations to prevent any duplicates
            
            cursor.execute('''
                SELECT id, time, name, student_id FROM attendance 
                WHERE (student_id = ? OR name = ?) 
                  AND course = ? 
                  AND date = ?
                ORDER BY id DESC
                LIMIT 1
            ''', (student_id, student_name, course_name, date_str))
            
            existing_record = cursor.fetchone()
            
            if existing_record:
                # Record exists - update it instead of creating duplicate
                existing_id, existing_time, existing_name, existing_student_id = existing_record
                
                cursor.execute('''
                    UPDATE attendance 
                    SET time = ?, status = 'Present', name = ?, student_id = ?
                    WHERE id = ?
                ''', (time_str, student_name, student_id, existing_id))
                
                updated_count += 1
                messages.append(f'Updated existing attendance for {student_name} (was at {existing_time}, now at {time_str})')
                
            else:
                # No existing record - use INSERT OR REPLACE to prevent any duplicates
                cursor.execute('''
                    INSERT OR REPLACE INTO attendance (name, course, student_id, date, time, status)
                    VALUES (?, ?, ?, ?, ?, 'Present')
                ''', (student_name, course_name, student_id, date_str, time_str))
                
                success_count += 1
                messages.append(f'Marked new attendance for {student_name} at {time_str}')
        
        # Double-check: Remove any duplicates that might have been created during this transaction
        cursor.execute('''
            WITH RankedAttendance AS (
                SELECT id, 
                       ROW_NUMBER() OVER (PARTITION BY name, course, date ORDER BY id DESC) as rn
                FROM attendance 
                WHERE course = ? AND date = ?
            )
            DELETE FROM attendance 
            WHERE id IN (
                SELECT id FROM RankedAttendance WHERE rn > 1
            )
        ''', (course_name, date_str))
        
        duplicates_removed = cursor.rowcount
        if duplicates_removed > 0:
            messages.append(f'Removed {duplicates_removed} duplicate records as safety measure')
        
        # Commit transaction
        cursor.execute('COMMIT')
        conn.close()
        
        total_processed = success_count + updated_count
        status_message = f'Successfully processed {total_processed} students ({success_count} new, {updated_count} updated)'
        
        if skipped_count > 0:
            status_message += f', {skipped_count} duplicates in selection skipped'
        
        return jsonify({
            'status': 'success',
            'message': status_message,
            'success_count': success_count,
            'updated_count': updated_count,
            'error_count': error_count,
            'skipped_count': skipped_count,
            'duplicates_removed': duplicates_removed if 'duplicates_removed' in locals() else 0,
            'total_processed': total_processed,
            'details': messages
        })
        
    except Exception as e:
        cursor.execute('ROLLBACK')
        conn.close()
        return jsonify({
            'status': 'error',
            'message': f'Database error: {str(e)}'
        }), 500


@app.route("/api/today_attendance")
def today_attendance():
    date_filter = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    course_filter = request.args.get("course")

    conn = sqlite3.connect("attendance.db")
    c = conn.cursor()

    if course_filter:
        c.execute("""
            SELECT a.name, a.course, s.level, s.section, a.date, a.time, a.status
            FROM attendance a
            LEFT JOIN students s ON a.name = s.name
            WHERE a.date = ? AND a.course = ?
        """, (date_filter, course_filter))
    else:
        c.execute("""
            SELECT a.name, a.course, s.level, s.section, a.date, a.time, a.status
            FROM attendance a
            LEFT JOIN students s ON a.name = s.name
            WHERE a.date = ?
        """, (date_filter,))

    rows = c.fetchall()
    conn.close()

    attendance_list = [
        {
            "name": r[0],
            "course": r[1],
            "level": r[2] if r[2] else "",
            "section": r[3] if r[3] else "",
            "date": r[4],
            "time": r[5],
            "status": r[6]
        }
        for r in rows
    ]
    return jsonify({"attendance": attendance_list})

@app.route('/download-today-pdf')
def download_today_pdf():
    date_str = request.args.get('date')
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    # Fetch data for the specified date
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, course, level, section, time, status
        FROM attendance
        WHERE date = ?
    ''', (date_str,))
    records = cursor.fetchall()
    conn.close()

    # Create PDF in memory
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, f"Attendance for {date_str}")

    # Table headers
    p.setFont("Helvetica-Bold", 12)
    y = height - 80
    headers = ['Name', 'Course', 'Level', 'Section', 'Time', 'Status']
    x_positions = [50, 150, 250, 330, 410, 470]

    for i, header in enumerate(headers):
        p.drawString(x_positions[i], y, header)

    # Table rows
    p.setFont("Helvetica", 10)
    y -= 20
    for rec in records:
        if y < 50:  # Avoid writing off the page
            p.showPage()
            y = height - 50
        for i, item in enumerate(rec):
            p.drawString(x_positions[i], y, str(item))
        y -= 20

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Attendance_{date_str}.pdf", mimetype='application/pdf')

@app.route('/download-today-csv')
def download_today_csv():
    date_str = request.args.get('date')
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, course, level, section, date, time, status
        FROM attendance
        WHERE date = ?
        ORDER BY time
    ''', (date_str,))
    data = cursor.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Course', 'Level', 'Section', 'Date', 'Time', 'Status'])
    writer.writerows(data)
    output.seek(0)

    return send_file(
        BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        download_name=f'Attendance_{date_str}.csv',
        as_attachment=True
    )

@app.route('/api/courses', methods=['GET'])
def get_courses():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM courses ORDER BY name')
    rows = cursor.fetchall()
    conn.close()

    courses = [{'id': row[0], 'name': row[1]} for row in rows]
    return jsonify({'courses': courses})

@app.route('/api/courses', methods=['POST'])
def create_course():
    if 'admin' not in session:
        return jsonify({'error': 'Admin access required'}), 401
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Course name is required'}), 400
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO courses (name) VALUES (?)', (name,))
        conn.commit()
        # Fetch the (possibly existing) id
        cursor.execute('SELECT id, name FROM courses WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()
        return jsonify({'course': {'id': row[0], 'name': row[1]}}), 201
    except Exception as e:
        return jsonify({'error': f'Failed to create course: {str(e)}'}), 500

@app.route('/download-course-pdf')
def download_course_pdf():
    course_name = request.args.get('course')
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if not course_name:
        return jsonify({'error': 'Course parameter is required'}), 400

    # Fetch data for the specified course and date
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.name, a.course, s.level, s.section, a.date, a.time, a.status
        FROM attendance a
        LEFT JOIN students s ON a.name = s.name
        WHERE a.course = ? AND a.date = ?
        ORDER BY a.time
    ''', (course_name, date_str))
    records = cursor.fetchall()
    conn.close()

    # Create PDF in memory
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Title
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, f"Attendance for {course_name} - {date_str}")

    # Table headers
    p.setFont("Helvetica-Bold", 12)
    y = height - 80
    headers = ['Name', 'Level', 'Section', 'Date', 'Time', 'Status']
    x_positions = [50, 200, 280, 360, 440, 510]

    for i, header in enumerate(headers):
        p.drawString(x_positions[i], y, header)

    # Table rows
    p.setFont("Helvetica", 10)
    y -= 20
    for rec in records:
        if y < 50:  # Avoid writing off the page
            p.showPage()
            y = height - 50
        # Skip the course column since it's the same for all records
        data = [rec[0], rec[2], rec[3], rec[4], rec[5], rec[6]]
        for i, item in enumerate(data):
            p.drawString(x_positions[i], y, str(item) if item else "")
        y -= 20

    p.showPage()
    p.save()

    buffer.seek(0)
    safe_course_name = course_name.replace(' ', '_').replace('/', '-')
    return send_file(buffer, as_attachment=True, 
                     download_name=f"{safe_course_name}_Attendance_{date_str}.pdf", 
                     mimetype='application/pdf')

@app.route('/download-course-csv')
def download_course_csv():
    course_name = request.args.get('course')
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if not course_name:
        return jsonify({'error': 'Course parameter is required'}), 400

    # Fetch data for the specified course and date
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.name, a.course, s.level, s.section, a.date, a.time, a.status
        FROM attendance a
        LEFT JOIN students s ON a.name = s.name
        WHERE a.course = ? AND a.date = ?
        ORDER BY a.time
    ''', (course_name, date_str))
    data = cursor.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Course', 'Level', 'Section', 'Date', 'Time', 'Status'])
    writer.writerows(data)
    output.seek(0)

    safe_course_name = course_name.replace(' ', '_').replace('/', '-')
    return send_file(
        BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        download_name=f'{safe_course_name}_Attendance_{date_str}.csv',
        as_attachment=True
    )

@app.route('/api/cleanup-duplicates', methods=['POST'])
def cleanup_duplicate_attendance():
    """Clean up duplicate attendance records, keeping the most recent one"""
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Admin access required'}), 401
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Find duplicate records (same student, course, date)
        cursor.execute('''
            SELECT name, course, date, COUNT(*) as count_records
            FROM attendance 
            GROUP BY name, course, date 
            HAVING COUNT(*) > 1
        ''')
        duplicates = cursor.fetchall()
        
        cleaned_count = 0
        
        for name, course, date, count in duplicates:
            # Get all records for this student, course, date
            cursor.execute('''
                SELECT id, time FROM attendance 
                WHERE name = ? AND course = ? AND date = ?
                ORDER BY time DESC
            ''', (name, course, date))
            records = cursor.fetchall()
            
            # Keep the most recent record, delete the rest
            if len(records) > 1:
                keep_id = records[0][0]  # Most recent record
                delete_ids = [str(r[0]) for r in records[1:]]  # Older records
                
                cursor.execute(f'''
                    DELETE FROM attendance 
                    WHERE id IN ({','.join(['?' for _ in delete_ids])})
                ''', delete_ids)
                
                cleaned_count += len(delete_ids)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': f'Cleaned up {cleaned_count} duplicate records from {len(duplicates)} student-course-date combinations',
            'duplicates_found': len(duplicates),
            'records_removed': cleaned_count
        })
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({
            'status': 'error',
            'message': f'Error during cleanup: {str(e)}'
        }), 500

@app.route('/submit_attendance', methods=['POST'])
def submit_attendance():
    data = request.get_json()
    student_id = data.get('student_id')
    course_name = data.get('course_name')  # Frontend should send course name

    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')

    if student_id and course_name:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Get student name for consistency with current schema
        cursor.execute("SELECT name FROM students WHERE id = ?", (student_id,))
        student_row = cursor.fetchone()
        if not student_row:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Student not found'}), 400
        student_name = student_row[0]

        # Validate enrollment in selected course
        cursor.execute("SELECT id FROM courses WHERE name = ?", (course_name,))
        rc = cursor.fetchone()
        if not rc:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Course not found'}), 400
        course_id = rc[0]
        cursor.execute("SELECT 1 FROM student_courses WHERE student_id = ? AND course_id = ?", (student_id, course_id))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'message': 'Student not registered for the selected course'}), 403

        # IMPROVED: Multiple duplicate checks for robustness
        # Check by student_id and course_name (primary)
        cursor.execute(
            "SELECT 1 FROM attendance WHERE student_id = ? AND course = ? AND date = ?",
            (student_id, course_name, date_str)
        )
        if cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'message': 'Attendance already marked for this student and course today'}), 400
        
        # Check by student_name and course_name (fallback)
        cursor.execute(
            "SELECT 1 FROM attendance WHERE name = ? AND course = ? AND date = ?",
            (student_name, course_name, date_str)
        )
        if cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'message': 'Attendance already marked for this student and course today'}), 400

        # Insert attendance record with both name and student_id for consistency
        cursor.execute(
            "INSERT INTO attendance (name, course, student_id, date, time, status) VALUES (?, ?, ?, ?, ?, 'Present')",
            (student_name, course_name, student_id, date_str, time_str)
        )
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Attendance marked successfully'})
    else:
        return jsonify({'status': 'error', 'message': 'Missing student ID or course name'}), 400
    
if __name__ == '__main__':
    initialize_db()
    app.run(debug=True)
