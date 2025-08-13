#!/usr/bin/env python3
"""
Script to safely delete today's attendance records.
Allows you to start fresh with today's attendance.
"""

import sqlite3
from datetime import datetime

DB_NAME = 'attendance.db'

def show_todays_records(date):
    """Show all attendance records for the specified date."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, course, time FROM attendance WHERE date = ? ORDER BY time", (date,))
    records = cursor.fetchall()
    
    if records:
        print(f"📋 Found {len(records)} attendance records for {date}:")
        print("-" * 60)
        for record_id, name, course, time in records:
            print(f"ID: {record_id:2} | {name:12} | {course:10} | {time}")
        print("-" * 60)
    else:
        print(f"✅ No attendance records found for {date}")
    
    conn.close()
    return len(records)

def delete_todays_records(date, confirm=True):
    """Delete all attendance records for the specified date."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if confirm:
        # Show what will be deleted
        count = show_todays_records(date)
        if count == 0:
            conn.close()
            return 0
        
        print(f"\n⚠️  WARNING: This will permanently delete {count} attendance records for {date}")
        response = input("Are you sure you want to proceed? Type 'YES' to confirm: ").strip()
        
        if response != 'YES':
            print("❌ Deletion cancelled. No records were deleted.")
            conn.close()
            return 0
    
    # Perform the deletion
    cursor.execute("DELETE FROM attendance WHERE date = ?", (date,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count

def backup_todays_records(date):
    """Create a backup of today's records before deleting."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM attendance WHERE date = ?", (date,))
    records = cursor.fetchall()
    
    if records:
        backup_filename = f"attendance_backup_{date.replace('-', '_')}.sql"
        
        with open(backup_filename, 'w') as f:
            f.write(f"-- Backup of attendance records for {date}\n")
            f.write(f"-- Created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for record in records:
                # record format: (id, name, course, status, date, time, student_id)
                f.write(f"INSERT INTO attendance (name, course, status, date, time, student_id) VALUES ")
                f.write(f"('{record[1]}', '{record[2]}', '{record[3]}', '{record[4]}', '{record[5]}', {record[6] if record[6] else 'NULL'});\n")
        
        print(f"💾 Backup created: {backup_filename}")
    
    conn.close()
    return len(records)

def main():
    """Main function to handle today's attendance deletion."""
    print("🗑️  Delete Today's Attendance Records")
    print("=" * 50)
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 Today's date: {today}")
    
    # Show current records
    record_count = show_todays_records(today)
    
    if record_count == 0:
        print("✅ No records to delete. You're all set!")
        return
    
    # Offer backup option
    print(f"\n💡 Would you like to create a backup before deleting?")
    backup_response = input("Create backup? (y/N): ").lower().strip()
    
    if backup_response in ['y', 'yes']:
        backup_count = backup_todays_records(today)
        print(f"✅ Backed up {backup_count} records")
    
    # Delete the records
    print(f"\n🗑️  Proceeding with deletion...")
    deleted_count = delete_todays_records(today, confirm=True)
    
    if deleted_count > 0:
        print(f"\n✅ Successfully deleted {deleted_count} attendance records for {today}")
        print("🎯 You can now start recording attendance fresh for today!")
        
        # Verify deletion
        remaining = show_todays_records(today)
        if remaining == 0:
            print("🔍 Verification: All today's records have been removed ✅")
        else:
            print(f"⚠️  Warning: {remaining} records still remain")
    else:
        print("\n❌ No records were deleted.")

if __name__ == "__main__":
    main()
