import sqlite3
from werkzeug.security import generate_password_hash

# Connect to the SQLite database
conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# Ensure 'users' table exists
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
''')

# User details
username = "admin"
password = "admin123"
hashed_password = generate_password_hash(password)

# Insert admin user if not already in the table
try:
    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
    conn.commit()
    print("Admin user created successfully!")
except sqlite3.IntegrityError:
    print("⚠ Admin user already exists.")
finally: conn.close()