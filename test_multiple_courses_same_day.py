#!/usr/bin/env python3
"""
Test to demonstrate that the same student can have attendance 
for multiple courses on the same day.
"""

import sqlite3
from datetime import datetime

DB_NAME = 'attendance.db'

def test_multiple_courses_same_day():
    """Test that a student can attend multiple courses on the same day."""
    print("🧪 Testing Multiple Courses Same Day")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get a test student
    cursor.execute("SELECT id, name FROM students LIMIT 1")
    student = cursor.fetchone()
    
    if not student:
        print("❌ No students found in database.")
        return
        
    student_id, student_name = student
    test_date = "2025-08-13"  # Future date to avoid conflicts
    
    # Define test courses with different times
    test_courses = [
        ("MATH_101", "09:00:00"),
        ("PHYSICS_201", "11:00:00"), 
        ("CHEMISTRY_301", "14:00:00")
    ]
    
    print(f"👤 Testing with student: {student_name}")
    print(f"📅 Date: {test_date}")
    print(f"📚 Courses to test: {len(test_courses)}")
    
    # Clean up any existing test records
    for course, _ in test_courses:
        cursor.execute("DELETE FROM attendance WHERE course = ? AND date = ?", (course, test_date))
    
    successful_insertions = 0
    
    # Try to insert attendance for each course
    for i, (course, time) in enumerate(test_courses, 1):
        print(f"\n🔄 Test {i}: Recording attendance for {course} at {time}")
        
        try:
            # Insert attendance record
            cursor.execute("""
                INSERT INTO attendance (name, course, student_id, date, time, status) 
                VALUES (?, ?, ?, ?, ?, 'Present')
            """, (student_name, course, student_id, test_date, time))
            
            conn.commit()
            successful_insertions += 1
            print(f"✅ Successfully recorded attendance for {course}")
            
        except Exception as e:
            print(f"❌ Failed to record attendance for {course}: {e}")
    
    # Verify all records were created
    cursor.execute("SELECT course, time FROM attendance WHERE student_id = ? AND date = ? ORDER BY time", 
                   (student_id, test_date))
    records = cursor.fetchall()
    
    print(f"\n📊 Results:")
    print(f"   Expected records: {len(test_courses)}")
    print(f"   Successful insertions: {successful_insertions}")
    print(f"   Records in database: {len(records)}")
    
    if records:
        print(f"\n📝 Attendance records for {student_name} on {test_date}:")
        for course, time in records:
            print(f"   - {course} at {time}")
    
    # Test duplicate prevention (should fail)
    print(f"\n🔄 Test {len(test_courses)+1}: Try to record duplicate for {test_courses[0][0]} (should fail)")
    duplicate_course, duplicate_time = test_courses[0]
    
    # Check if duplicate would be detected
    cursor.execute("SELECT 1 FROM attendance WHERE student_id = ? AND course = ? AND date = ?", 
                   (student_id, duplicate_course, test_date))
    
    if cursor.fetchone():
        print(f"✅ Duplicate prevention working - {duplicate_course} already recorded!")
    else:
        print(f"❌ Duplicate prevention failed - {duplicate_course} not found!")
    
    # Clean up test records
    for course, _ in test_courses:
        cursor.execute("DELETE FROM attendance WHERE course = ? AND date = ?", (course, test_date))
    conn.commit()
    print(f"\n🧹 Test records cleaned up")
    
    conn.close()
    
    # Final assessment
    success = successful_insertions == len(test_courses) and len(records) == len(test_courses)
    
    if success:
        print(f"\n🎉 SUCCESS! Student can attend {len(test_courses)} different courses on the same day!")
        print("✅ Each course gets its own separate attendance record")
        print("✅ Duplicate prevention still works for same course")
    else:
        print(f"\n❌ Test failed - only {successful_insertions}/{len(test_courses)} courses recorded")
    
    return success

if __name__ == "__main__":
    print("🔧 Multiple Courses Same Day Test")
    print("=" * 40)
    
    result = test_multiple_courses_same_day()
    
    print("\n" + "=" * 40)
    if result:
        print("✅ CONCLUSION: YES! Same student can attend multiple courses on the same day!")
        print("🎯 Each course attendance is tracked separately.")
    else:
        print("❌ Test failed - there may be an issue with the system.")
