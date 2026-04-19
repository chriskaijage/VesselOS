#!/usr/bin/env python3
"""
Test script to verify all demo accounts can be created and logged in with correct credentials.
This script tests the demo account initialization without running the full Flask app.
"""

import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

# Database path
DB_PATH = 'marine.db'

def test_password_hashing():
    """Test that password hashing and verification works correctly"""
    print("\n" + "="*70)
    print("TEST 1: Password Hashing Verification")
    print("="*70)
    
    passwords_to_test = [
        ('Engineer@2026', 'Port Engineer'),
        ('Quality@2026', 'DMPO HQ'),
        ('Harbour@2026', 'Harbour Master'),
    ]
    
    for password, account_name in passwords_to_test:
        hashed = generate_password_hash(password)
        is_valid = check_password_hash(hashed, password)
        print(f"✓ {account_name}: {'PASS' if is_valid else 'FAIL'}")
        if not is_valid:
            print(f"  ERROR: Password verification failed for {account_name}")
            return False
    
    return True

def test_demo_account_creation():
    """Test that demo accounts are created with correct credentials in the database"""
    print("\n" + "="*70)
    print("TEST 2: Demo Account Creation and Verification")
    print("="*70)
    
    if os.path.exists(DB_PATH):
        print(f"[WARNING] Database {DB_PATH} already exists. Removing...")
        os.remove(DB_PATH)
    
    # Import app to initialize database
    from app import app, init_db
    
    # Initialize database
    print("[INFO] Initializing database with demo accounts...")
    try:
        with app.app_context():
            init_db()
        print("[OK] Database initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
        return False
    
    # Connect and verify accounts
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    demo_accounts = [
        ('port_engineer@marine.com', 'Engineer@2026', 'port_engineer', 'Port Engineer'),
        ('dmpo@marine.com', 'Quality@2026', 'quality_officer', 'DMPO HQ'),
        ('harbour_master@marine.com', 'Harbour@2026', 'harbour_master', 'Harbour Master'),
    ]
    
    all_passed = True
    for email, password, role, display_name in demo_accounts:
        print(f"\n[TEST] {display_name} ({email})")
        
        # Check account exists
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            print(f"  ✗ FAIL: Account not found in database")
            all_passed = False
            continue
        
        user_dict = dict(user)
        
        # Check account is active and approved
        if not user_dict['is_active']:
            print(f"  ✗ FAIL: Account is not active")
            all_passed = False
        else:
            print(f"  ✓ Account is active")
        
        if not user_dict['is_approved']:
            print(f"  ✗ FAIL: Account is not approved")
            all_passed = False
        else:
            print(f"  ✓ Account is approved")
        
        # Check role
        if user_dict['role'] != role:
            print(f"  ✗ FAIL: Role is {user_dict['role']}, expected {role}")
            all_passed = False
        else:
            print(f"  ✓ Role is correct: {role}")
        
        # Check password
        try:
            if check_password_hash(user_dict['password'], password):
                print(f"  ✓ Password hash is correct")
            else:
                print(f"  ✗ FAIL: Password verification failed")
                all_passed = False
        except Exception as e:
            print(f"  ✗ FAIL: Error verifying password: {e}")
            all_passed = False
    
    conn.close()
    return all_passed

if __name__ == '__main__':
    print("\n" + "="*70)
    print("DEMO ACCOUNT LOGIN TEST SUITE")
    print("="*70)
    
    test1_passed = test_password_hashing()
    test2_passed = test_demo_account_creation()
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Test 1 (Password Hashing):       {'PASS ✓' if test1_passed else 'FAIL ✗'}")
    print(f"Test 2 (Account Creation):       {'PASS ✓' if test2_passed else 'FAIL ✗'}")
    print("="*70)
    
    if test1_passed and test2_passed:
        print("\n✓ ALL TESTS PASSED - Demo accounts are ready for login!")
        print("\nYou can now log in with:")
        print("  1. port_engineer@marine.com / Engineer@2026")
        print("  2. dmpo@marine.com / Quality@2026")
        print("  3. harbour_master@marine.com / Harbour@2026")
    else:
        print("\n✗ SOME TESTS FAILED - See details above")
        exit(1)
