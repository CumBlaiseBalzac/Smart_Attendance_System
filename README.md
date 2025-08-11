# 🎓 University Student's Attendance System with Face Recognition

This is a Flask-powered attendance management system for university students. It uses facial recognition to verify student's presence during scheduled classes. The system features an admin dashboard, attendance tracking, course and class scheduling, and real-time face authentication via webcam.

---

## 📌 Features

### ✅ Authentication & Authorization
- Custom user model with username-based login.
- With a single role: Admin.


### 🧠 Face Recognition
- Real-time face authentication via webcam.
- Face training per student using Face_Recognition.
- Admin control over training images and verification models.

### 📅 Attendance Management
- Schedules linked to specific programs, and courses.
- Automatically tracks attendance if students face is recognized.
- Records include timestamps and verification status.

### 📊 Admin Dashboard
- Overview statistics: total registered students, courses, schedules, attendance records.
- Detailed attendance table:



### 📁 File Upload & Storage
- Training images and face models stored securely.
- Media, models, and venv directories ignored via `.gitignore`.

---

## 🏗️ Tech Stack

- **Backend:** Python, Flask.
- **Frontend:** html5, css and javascript
- **Face Recognition:** OpenCV, Face_recognition
- **Database:** SQLite3 (default, can switch to PostgreSQL/MySQL)

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10
- pip
- virtualenv
- Git

### Installation

```bash
# Clone the repo
git clone https://github.com/CumBlaiseBalzac/Smart_Attendance_System

# Create virtual environment
python -m venv venv310
source venv310/bin/activate  # On Windows: venv310\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python server.py migrate

# Create superuser
python create_admin.py createsuperuser

# Run server
python server.py runserver
```

## 📂 Project Structure
```
├── account/ # Custom user model & authentication
├── attendance/ # Attendance logic & scheduling
├── face_auth/ # Face recognition, training & verification
├── templates/ # HTML templates (HTML, CSS and JAVASCRIPT)
├── static/ # Static files (models)
├── venv310/ # Virtual environment (ignored by Git)
├── .gitignore
├── server.py
└── README.md
```

# Virtual environment
venv310/

# Face recognition models & training images & encodings
captured_faces/
static/models/


# Face encodings
project/encodings




