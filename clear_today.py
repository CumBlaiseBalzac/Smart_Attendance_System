#!/usr/bin/env python3
"""
Simple script to delete today's attendance records.
"""

import sqlite3
from datetime import datetime

DB_NAME = 'attendance.db'

def clear_today():
    today = datetime.now().strftime('%Y-%m-%d')
    
    print(f"🗑️  Clearing attendance records for {today}")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Show current records first
    cursor.execute("SELECT id, name, course, time FROM attendance WHERE date = ? ORDER BY time", (today,))
    records = cursor.fetchall()
    
    if not records:
        print("✅ No records found for today. Nothing to delete!")
        conn.close()
        return
    
    print(f"📋 Found {len(records)} records for today:")
    for record_id, name, course, time in records:
        print(f"  - {name} in {course} at {time}")
    
    print(f"\n🗑️  Deleting all {len(records)} records...")
    
    # Delete all records for today
    cursor.execute("DELETE FROM attendance WHERE date = ?", (today,))
    deleted_count = cursor.rowcount
    conn.commit()
    
    print(f"✅ Successfully deleted {deleted_count} attendance records!")
    
    # Verify deletion
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today,))
    remaining = cursor.fetchone()[0]
    
    if remaining == 0:
        print("🎯 All today's records cleared! You can start fresh.")
    else:
        print(f"⚠️  Warning: {remaining} records still remain")
    
    conn.close()

if __name__ == "__main__":
    clear_today()
