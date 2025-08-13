#!/usr/bin/env python3
"""
Utility script to identify and clean up duplicate attendance records.
This script should be run once to clean existing data.
"""

import sqlite3
from datetime import datetime

DB_NAME = 'attendance.db'

def find_duplicates():
    """Find duplicate attendance records in the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("=== Finding Duplicate Attendance Records ===")
    
    # Find duplicates by student name, course, and date
    cursor.execute('''
        SELECT name, course, date, COUNT(*) as count, 
               GROUP_CONCAT(id) as record_ids,
               GROUP_CONCAT(time) as times
        FROM attendance 
        GROUP BY name, course, date 
        HAVING COUNT(*) > 1
        ORDER BY name, date
    ''')
    
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✅ No duplicate records found!")
        conn.close()
        return []
    
    print(f"⚠️  Found {len(duplicates)} sets of duplicate records:")
    print("-" * 80)
    
    for dup in duplicates:
        name, course, date, count, record_ids, times = dup
        ids = record_ids.split(',')
        time_list = times.split(',')
        
        print(f"Student: {name}")
        print(f"Course: {course}")  
        print(f"Date: {date}")
        print(f"Duplicate count: {count}")
        print(f"Record IDs: {record_ids}")
        print(f"Times: {times}")
        print("-" * 40)
    
    conn.close()
    return duplicates

def clean_duplicates(dry_run=True):
    """Clean duplicate attendance records, keeping only the earliest time entry."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Find duplicates
    cursor.execute('''
        SELECT name, course, date, 
               GROUP_CONCAT(id || ':' || time) as id_times
        FROM attendance 
        GROUP BY name, course, date 
        HAVING COUNT(*) > 1
        ORDER BY name, date
    ''')
    
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✅ No duplicates to clean!")
        conn.close()
        return
    
    deleted_count = 0
    
    print(f"\n=== {'DRY RUN: ' if dry_run else ''}Cleaning Duplicate Records ===")
    
    for name, course, date, id_times in duplicates:
        # Parse id:time pairs
        entries = []
        for entry in id_times.split(','):
            record_id, time = entry.split(':', 1)
            entries.append((int(record_id), time))
        
        # Sort by time to find the earliest
        entries.sort(key=lambda x: x[1])  # Sort by time
        earliest_id = entries[0][0]
        earliest_time = entries[0][1]
        
        # IDs to delete (all except the earliest)
        ids_to_delete = [str(entry[0]) for entry in entries[1:]]
        
        print(f"👤 {name} - {course} - {date}")
        print(f"   Keeping: ID {earliest_id} (Time: {earliest_time})")
        print(f"   {'Would delete' if dry_run else 'Deleting'}: IDs {', '.join(ids_to_delete)}")
        
        if not dry_run and ids_to_delete:
            # Delete duplicate records
            placeholders = ','.join(['?' for _ in ids_to_delete])
            delete_query = f"DELETE FROM attendance WHERE id IN ({placeholders})"
            cursor.execute(delete_query, ids_to_delete)
            deleted_count += len(ids_to_delete)
    
    if not dry_run:
        conn.commit()
        print(f"\n✅ Successfully deleted {deleted_count} duplicate records!")
    else:
        print(f"\n🔍 DRY RUN: Would delete {sum(len(id_times.split(','))-1 for _, _, _, id_times in duplicates)} duplicate records")
        print("   Run with dry_run=False to actually perform the cleanup")
    
    conn.close()

def verify_no_duplicates():
    """Verify that no duplicate records exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) as duplicate_sets
        FROM (
            SELECT name, course, date, COUNT(*) as count
            FROM attendance 
            GROUP BY name, course, date 
            HAVING COUNT(*) > 1
        )
    ''')
    
    duplicate_count = cursor.fetchone()[0]
    conn.close()
    
    if duplicate_count == 0:
        print("✅ Verification passed: No duplicate records found!")
    else:
        print(f"❌ Verification failed: {duplicate_count} sets of duplicates still exist!")
    
    return duplicate_count == 0

def main():
    """Main function to run the cleanup process."""
    print("🔧 Attendance Duplicate Cleanup Tool")
    print("=" * 50)
    
    # Step 1: Find and display duplicates
    duplicates = find_duplicates()
    
    if not duplicates:
        return
    
    # Step 2: Show what would be cleaned (dry run)
    clean_duplicates(dry_run=True)
    
    # Step 3: Ask for confirmation
    print("\n" + "="*50)
    response = input("Do you want to proceed with cleaning duplicates? (y/N): ").lower().strip()
    
    if response in ['y', 'yes']:
        print("\n🧹 Proceeding with cleanup...")
        clean_duplicates(dry_run=False)
        
        # Step 4: Verify cleanup
        print("\n🔍 Verifying cleanup...")
        verify_no_duplicates()
        
        print("\n✨ Cleanup completed! Your attendance system should now prevent duplicates.")
    else:
        print("\n❌ Cleanup cancelled. No changes were made.")
        print("💡 The updated server.py code will prevent future duplicates.")

if __name__ == "__main__":
    main()
