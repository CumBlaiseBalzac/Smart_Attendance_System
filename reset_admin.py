import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# Choose your credentials
username = "admin"
password = "admin123"
hashed_pw = generate_password_hash(password)

# Delete user if already exists
cursor.execute("DELETE FROM users WHERE username = ?", (username,))

# Insert user with hashed password
cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
conn.commit()
conn.close()

print("Admin user reset successfully")