import sqlite3
from datetime import datetime

conn = sqlite3.connect('marine.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Simulate creating a new request like the API would
print("=== Simulating Request Creation ===")

request_id = "MRQ_TEST_001"
submitted_by_id = "CE001"  # Simulating a chief engineer submitting
requested_by_id = "CE001"
requested_by_email = "chief@marine.com"

# This is what the API insert looks like
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
    request_id, "New Test Ship", "test_type", "repair", "high", "urgent", "Test description",
    "Test Location", "TBD", "To be assessed", requested_by_email,
    "submitted", "HIGH", "Test assessment", "submitted", datetime.now(), datetime.now(),
    None, None, None, 1, None,
    "Test User", "test@example.com", "555-1234", None,
    "9999999", "cargo", None, None, submitted_by_id
))

conn.commit()
print(f"✓ Created request {request_id} with submitted_by={submitted_by_id}")

# Now query it back
c.execute("""
    SELECT request_id, ship_name, submitted_by, requested_by, status
    FROM maintenance_requests
    WHERE request_id = ?
""", (request_id,))

row = c.fetchone()
if row:
    result = dict(row)
    print(f"\n✓ Retrieved request:")
    print(f"  request_id: {result['request_id']}")
    print(f"  ship_name: {result['ship_name']}")
    print(f"  submitted_by: {result['submitted_by']}")
    print(f"  requested_by: {result['requested_by']}")
    print(f"  status: {result['status']}")

# Now test if CE001 can find this request with the same query used in the dashboard
print(f"\n=== Testing Query with CE001 ===")
c.execute("""
    SELECT request_id, ship_name, submitted_by, requested_by, status
    FROM maintenance_requests
    WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?)
    ORDER BY created_at DESC
    LIMIT 50
""", ("CE001", "CE001", "chief@marine.com"))

requests = [dict(row) for row in c.fetchall()]
print(f"Found {len(requests)} requests for CE001")
for req in requests[:5]:
    print(f"  - {req['request_id']}: {req['ship_name']}")

conn.close()
print("\n✓ Test completed successfully")
