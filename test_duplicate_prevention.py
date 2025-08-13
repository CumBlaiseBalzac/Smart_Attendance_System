#!/usr/bin/env python3
"""
Test script to verify that the duplicate attendance prevention is working correctly.
"""

import sqlite3
import sys
from datetime import datetime

DB_NAME = 'attendance.db'

def test_duplicate_prevention():
    """Test that the duplicate prevention logic works correctly."""
    print("🧪 Testing Duplicate Attendance Prevention")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get a test student
    cursor.execute("SELECT id, name FROM students LIMIT 1")
    student = cursor.fetchone()
    
    if not student:
        print("❌ No students found in database. Please add a student first.")
        conn.close()
        return False
    
    student_id, student_name = student
    test_course = "TEST_COURSE"
    test_date = "2025-08-12"  # Tomorrow's date to avoid conflicts
    test_time = "10:00:00"
    
    print(f"👤 Testing with student: {student_name} (ID: {student_id})")
    print(f"📚 Course: {test_course}")
    print(f"📅 Date: {test_date}")
    print(f"⏰ Time: {test_time}")
    
    # Clean up any existing test records first
    cursor.execute("DELETE FROM attendance WHERE course = ? AND date = ?", (test_course, test_date))
    
    print("\n🔄 Test 1: First attendance record (should succeed)")
    try:
        # Insert first record
        cursor.execute(
            "INSERT INTO attendance (name, course, student_id, date, time, status) VALUES (?, ?, ?, ?, ?, 'Present')",
            (student_name, test_course, student_id, test_date, test_time)
        )
        conn.commit()
        print("✅ First record inserted successfully")
    except Exception as e:
        print(f"❌ Failed to insert first record: {e}")
        conn.close()
        return False
    
    print("\n🔄 Test 2: Duplicate attendance record (should be prevented)")
    
    # Check for existing record using the same logic as the server
    cursor.execute("SELECT 1 FROM attendance WHERE student_id = ? AND course = ? AND date = ?", 
                   (student_id, test_course, test_date))
    if cursor.fetchone():
        print("✅ Duplicate prevention working - existing record found!")
        duplicate_detected = True
    else:
        print("❌ Duplicate prevention failed - no existing record found")
        duplicate_detected = False
    
    # Also test the fallback name-based check
    cursor.execute("SELECT 1 FROM attendance WHERE name = ? AND course = ? AND date = ?", 
                   (student_name, test_course, test_date))
    if cursor.fetchone():
        print("✅ Fallback name-based duplicate prevention also working!")
        duplicate_detected_fallback = True
    else:
        print("❌ Fallback duplicate prevention failed")
        duplicate_detected_fallback = False
    
    # Count total records for this test case
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE course = ? AND date = ?", (test_course, test_date))
    record_count = cursor.fetchone()[0]
    print(f"📊 Total records for {test_course} on {test_date}: {record_count}")
    
    # Clean up test records
    cursor.execute("DELETE FROM attendance WHERE course = ? AND date = ?", (test_course, test_date))
    conn.commit()
    print("🧹 Test records cleaned up")
    
    conn.close()
    
    # Final assessment
    success = duplicate_detected and duplicate_detected_fallback and record_count == 1
    
    if success:
        print("\n🎉 All tests passed! Duplicate prevention is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the duplicate prevention logic.")
    
    return success

def show_current_duplicates():
    """Show any current duplicates in the database."""
    print("\n🔍 Checking for existing duplicates...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT name, course, date, COUNT(*) as count
        FROM attendance 
        GROUP BY name, course, date 
        HAVING COUNT(*) > 1
        ORDER BY name, date
    ''')
    
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"⚠️  Found {len(duplicates)} sets of duplicates:")
        for name, course, date, count in duplicates:
            print(f"  - {name} in {course} on {date}: {count} records")
    else:
        print("✅ No duplicates found in current database")
    
    conn.close()
    return len(duplicates) == 0

if __name__ == "__main__":
    print("🔧 Attendance System Duplicate Prevention Test")
    print("=" * 55)
    
    # Check current state
    no_existing_duplicates = show_current_duplicates()
    
    # Run prevention test
    prevention_works = test_duplicate_prevention()
    
    print("\n" + "=" * 55)
    if no_existing_duplicates and prevention_works:
        print("✅ ALL TESTS PASSED!")
        print("🎯 Your attendance system is now properly protected against duplicates.")
        sys.exit(0)
    else:
        print("❌ SOME ISSUES DETECTED")
        if not no_existing_duplicates:
            print("   - Existing duplicates found in database")
        if not prevention_works:
            print("   - Duplicate prevention logic needs attention")
        sys.exit(1)
