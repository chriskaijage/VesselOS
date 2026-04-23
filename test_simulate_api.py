#!/usr/bin/env python
"""Test submitting a maintenance request through the Flask app directly"""

import sqlite3
from datetime import datetime

conn = sqlite3.connect('marine.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Simulate what the API does when an AUTHENTICATED chief engineer submits a request
print("=== Simulating API Request Creation (Authenticated User) ===\n")

current_user_id = "CE001"  # Simulating authenticated user
current_user_email = "chief@marine.com"
requested_by_email = current_user_email  # Form pre-filled
requested_by_name = "Chief Engineer"
requested_by_phone = "555-0001"

# This is what the API does
initial_status = 'submitted'
requester_id = current_user_id  # Set because user is authenticated
submitted_by_id = current_user_id  # Set because user is authenticated

print(f"Initial values:")
print(f"  current_user_id: {current_user_id}")
print(f"  requester_id: {requester_id}")
print(f"  submitted_by_id: {submitted_by_id}")
print(f"  initial_status: {initial_status}")
print()

request_id = "MRQ_SIMULATE_001"

# Do the insert
c.execute("""
    INSERT INTO maintenance_requests
    (request_id, ship_name, maintenance_type, request_type, priority, criticality, description,
     location, estimated_duration, resources_needed, requested_by,
     status, severity, assessment_details, workflow_status, created_at, updated_at,
     part_number, part_name, part_category, quantity, manufacturer,
     requested_by_name, requested_by_email, requested_by_phone, emergency_contact,
     imo_number, vessel_type, company, eta, submitted_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    request_id, "Simulated Ship", "repair", "repair", "high", "urgent", "Test description",
    "Test Location", "TBD", "To be assessed", requester_id or requested_by_email,
    initial_status, "HIGH", "Test assessment", "submitted", datetime.now(), datetime.now(),
    None, None, None, 1, None,
    requested_by_name, requested_by_email, requested_by_phone, None,
    "9999999", "cargo", None, None, submitted_by_id
))

conn.commit()
print(f"✓ Inserted request {request_id}\n")

# Now query it back
c.execute("""
    SELECT request_id, ship_name, submitted_by, requested_by, status
    FROM maintenance_requests
    WHERE request_id = ?
""", (request_id,))

row = c.fetchone()
if row:
    result = dict(row)
    print(f"✓ Retrieved from database:")
    print(f"  request_id: {result['request_id']}")
    print(f"  submitted_by: {result['submitted_by']}")
    print(f"  requested_by: {result['requested_by']}")
    print()

# Now test the query that the dashboard uses
print(f"=== Testing Dashboard Query (Chief Engineer CE001) ===\n")
c.execute("""
    SELECT request_id, ship_name, submitted_by, requested_by, status
    FROM maintenance_requests
    WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?)
    ORDER BY created_at DESC
    LIMIT 50
""", (current_user_id, current_user_id, current_user_email))

requests = [dict(row) for row in c.fetchall()]
print(f"Found {len(requests)} requests\n")

# Check if our simulated request is in the results
found = False
for req in requests:
    if req['request_id'] == request_id:
        found = True
        print(f"✓ FOUND our simulated request: {request_id}")
        break

if not found:
    print(f"✗ SIMULATED REQUEST NOT FOUND!")
    print(f"\nAll requests for this user:")
    for req in requests[:5]:
        print(f"  - {req['request_id']}: submitted_by={req['submitted_by']}, requested_by={req['requested_by']}")

conn.close()
print("\n✓ Test completed")
