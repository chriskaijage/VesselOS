#!/usr/bin/env python3
"""
Debug script to test the login functionality directly.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import Flask app
from app import app, get_db_connection, init_db
from werkzeug.security import check_password_hash

# Initialize database with demo accounts
print("Initializing database...")
init_db()
print("Database initialized!\n")

print("=" * 70)
print("LOGIN SYSTEM DEBUG TEST")
print("=" * 70)

# Test 1: Check database connection
print("\n[TEST 1] Database Connection")
try:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    conn.close()
    print(f"[OK] Database connected, {user_count} users found")
except Exception as e:
    print(f"[ERROR] Database connection failed: {e}")
    sys.exit(1)

# Test 2: Test login with test client
print("\n[TEST 2] Flask Test Client Login")
try:
    app.config['TESTING'] = True
    with app.test_client() as client:
        # Try login
        response = client.post('/login', data={
            'email': 'port_engineer@marine.com',
            'password': 'Admin@2025'
        }, follow_redirects=True)
        
        print(f"[INFO] Response status code: {response.status_code}")
        print(f"[INFO] Response URL: {response.request.path}")
        
        # Check if login was successful
        if response.status_code == 200 and 'dashboard' in response.request.path:
            print("[OK] Login successful - redirected to dashboard")
        else:
            print("[ERROR] Login failed or unexpected redirect")
            # Print response content
            if b"Invalid email or password" in response.data:
                print("[ERROR] Error message: Invalid email or password")
            if b"deactivated" in response.data:
                print("[ERROR] Error message: Account deactivated")
            if b"pending approval" in response.data:
                print("[ERROR] Error message: Account pending approval")
            print("[DEBUG] Response content (first 500 chars):")
            print(response.data[:500].decode('utf-8', errors='ignore'))
            
except Exception as e:
    print(f"[ERROR] Login test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("DEBUG TEST COMPLETE")
print("=" * 70)
