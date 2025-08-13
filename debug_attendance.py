#!/usr/bin/env python3
"""
Diagnostic script to help identify and analyze duplicate attendance records.
Run this script to get detailed information about the attendance database.
"""

import sqlite3
from datetime import datetime

def analyze_attendance_database():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    print("🔍 ATTENDANCE DATABASE ANALYSIS")
    print("=" * 50)
    
    # 1. Check table schema
    print("\n1. ATTENDANCE TABLE SCHEMA:")
    cursor.execute("PRAGMA table_info(attendance)")
    schema = cursor.fetchall()
    for row in schema:
        print(f"   {row[1]} ({row[2]}) - Primary Key: {bool(row[5])}")
    
    # 2. Check total records
    cursor.execute("SELECT COUNT(*) FROM attendance")
    total_records = cursor.fetchone()[0]
    print(f"\n2. TOTAL ATTENDANCE RECORDS: {total_records}")
    
    # 3. Check for duplicates by name, course, date
    print("\n3. DUPLICATES BY NAME + COURSE + DATE:")
    cursor.execute("""
        SELECT name, course, date, COUNT(*) as count_records, 
               GROUP_CONCAT(id) as record_ids,
               GROUP_CONCAT(time) as times
        FROM attendance 
        GROUP BY name, course, date 
        HAVING COUNT(*) > 1
        ORDER BY date DESC, count_records DESC
    """)
    name_duplicates = cursor.fetchall()
    
    if name_duplicates:
        print("   ❌ DUPLICATES FOUND:")
        for row in name_duplicates:
            print(f"   • {row[0]} | {row[1]} | {row[2]} | {row[3]} records")
            print(f"     IDs: {row[4]}")
            print(f"     Times: {row[5]}")
            print()
    else:
        print("   ✅ No duplicates found by name + course + date")
    
    # 4. Check for duplicates by student_id, course, date (if student_id exists)
    print("\n4. DUPLICATES BY STUDENT_ID + COURSE + DATE:")
    cursor.execute("""
        SELECT student_id, course, date, COUNT(*) as count_records,
               GROUP_CONCAT(id) as record_ids,
               GROUP_CONCAT(name) as names,
               GROUP_CONCAT(time) as times
        FROM attendance 
        WHERE student_id IS NOT NULL
        GROUP BY student_id, course, date 
        HAVING COUNT(*) > 1
        ORDER BY date DESC, count_records DESC
    """)
    id_duplicates = cursor.fetchall()
    
    if id_duplicates:
        print("   ❌ DUPLICATES FOUND:")
        for row in id_duplicates:
            print(f"   • Student ID {row[0]} | {row[1]} | {row[2]} | {row[3]} records")
            print(f"     Record IDs: {row[4]}")
            print(f"     Names: {row[5]}")
            print(f"     Times: {row[6]}")
            print()
    else:
        print("   ✅ No duplicates found by student_id + course + date")
    
    # 5. Check recent attendance (today and yesterday)
    print("\n5. RECENT ATTENDANCE RECORDS:")
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT id, name, course, student_id, date, time, status
        FROM attendance 
        WHERE date >= date('now', '-1 day')
        ORDER BY date DESC, time DESC
        LIMIT 10
    """)
    recent_records = cursor.fetchall()
    
    for row in recent_records:
        print(f"   ID:{row[0]} | {row[1]} | {row[2]} | SID:{row[3]} | {row[4]} {row[5]} | {row[6]}")
    
    # 6. Check unique constraints
    print("\n6. DATABASE INDEXES:")
    cursor.execute("PRAGMA index_list(attendance)")
    indexes = cursor.fetchall()
    
    if indexes:
        for index in indexes:
            print(f"   • {index[1]} (Unique: {bool(index[2])})")
            cursor.execute(f"PRAGMA index_info({index[1]})")
            index_info = cursor.fetchall()
            for col in index_info:
                print(f"     - Column: {col[2]}")
    else:
        print("   ⚠️  No indexes found on attendance table")
    
    # 7. Check for records with same name but different student_id
    print("\n7. NAME CONSISTENCY CHECK:")
    cursor.execute("""
        SELECT name, COUNT(DISTINCT student_id) as unique_student_ids,
               GROUP_CONCAT(DISTINCT student_id) as student_ids
        FROM attendance 
        WHERE student_id IS NOT NULL
        GROUP BY name 
        HAVING COUNT(DISTINCT student_id) > 1
    """)
    name_inconsistencies = cursor.fetchall()
    
    if name_inconsistencies:
        print("   ❌ NAME/STUDENT_ID INCONSISTENCIES:")
        for row in name_inconsistencies:
            print(f"   • {row[0]} has {row[1]} different student IDs: {row[2]}")
    else:
        print("   ✅ Names are consistent with student IDs")
    
    # 8. Summary statistics
    print("\n8. SUMMARY STATISTICS:")
    cursor.execute("SELECT COUNT(DISTINCT name) FROM attendance")
    unique_names = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT course) FROM attendance")  
    unique_courses = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT date) FROM attendance")
    unique_dates = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id IS NULL")
    missing_student_ids = cursor.fetchone()[0]
    
    print(f"   • Unique student names: {unique_names}")
    print(f"   • Unique courses: {unique_courses}")
    print(f"   • Unique dates: {unique_dates}")
    print(f"   • Records missing student_id: {missing_student_ids}")
    
    conn.close()
    
    # 9. Recommendations
    print("\n9. RECOMMENDATIONS:")
    if name_duplicates or id_duplicates:
        print("   🔧 Run the cleanup duplicates function to remove duplicate records")
    if missing_student_ids > 0:
        print("   🔧 Consider updating old records to include student_id for consistency")
    if not indexes:
        print("   🔧 Add unique constraint to prevent future duplicates")
    
    print("\n" + "=" * 50)
    print("Analysis complete! ✨")

if __name__ == "__main__":
    analyze_attendance_database()
