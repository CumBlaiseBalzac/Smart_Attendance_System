import sqlite3
from werkzeug.security import generate_password_hash

# Connect (this will create the database if it doesn't exist)
conn = sqlite3.connect('app.db')
cursor = conn.cursor()

# Create admins table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )
''')

# Add default admin user (only if doesn't exist)
cursor.execute('SELECT * FROM admins WHERE username = ?', ('admin',))
if not cursor.fetchone():
    password_hash = generate_password_hash('admin123')
    cursor.execute('INSERT INTO admins (username, password_hash) VALUES (?, ?)', ('admin', password_hash))

# Create users table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        image TEXT
    )
''')


cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        course TEXT,
        level TEXT,
        section TEXT,
        email TEXT,
        phone TEXT,
        status TEXT,  -- IN or OUT
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Commit and close
conn.commit()
conn.close()

print('Database initialized successfully with all required tables.')
