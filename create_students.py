import sqlite3

# Connect to your database
conn = sqlite3.connect('attendance.db')
c = conn.cursor()

# Create the students table
c.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT,
    course TEXT,
    level TEXT,
    section TEXT,
    captures INTEGER,
    date_registered TEXT
)
''')

# Save and close
conn.commit()
conn.close()

print("students table created successfully.")
