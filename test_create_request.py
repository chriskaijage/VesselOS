#!/usr/bin/env python
"""Test creating a maintenance request as if a user submitted it"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app, get_db_connection
import sqlite3

# Test 1: Check if app can start
print("✓ App imported successfully")

# Test 2: Check database connection
conn = get_db_connection()
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Count existing requests
c.execute("SELECT COUNT(*) as count FROM maintenance_requests")
count_row = c.fetchone()
count = dict(count_row).get('count', 0) if count_row else 0
print(f"✓ Current maintenance requests in database: {count}")

# Test 3: Simulate a user submitting a request with the test client
with app.test_client() as client:
    # First, let's see if there's a login endpoint we can test with
    print("\n=== Testing Maintenance Request Creation ===")
    
    # Try creating a request as an unauthenticated user
    print("\n1. Testing as unauthenticated user:")
    response = client.post('/api/maintenance-requests', 
        json={
            'ship_name': 'Test Ship Unauthenticated',
            'imo_number': '1234567',
            'vessel_type': 'cargo',
            'location': 'Port',
            'request_type': 'repair',
            'criticality': 'high',
            'description': 'Test maintenance request',
            'requested_by_name': 'John Doe',
            'requested_by_email': 'john@example.com',
            'requested_by_phone': '555-1234'
        })
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.get_json()}")

conn.close()
print("\n✓ Tests completed")
