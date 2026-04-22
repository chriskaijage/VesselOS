import sqlite3
from datetime import datetime
import hashlib

conn = sqlite3.connect('marine.db')
c = conn.cursor()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Create chief engineer user
c.execute("""
    INSERT OR IGNORE INTO users
    (user_id, email, password, role, first_name, last_name, is_active, is_approved, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('CE001', 'chief@marine.com', hash_password('password'), 
      'chief_engineer', 'Chief', 'Engineer', 1, 1, datetime.now()))
print("✓ Created chief_engineer user")

# Create captain user
c.execute("""
    INSERT OR IGNORE INTO users
    (user_id, email, password, role, first_name, last_name, is_active, is_approved, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('CAP001', 'captain@marine.com', hash_password('password'), 
      'captain', 'Captain', 'Smith', 1, 1, datetime.now()))
print("✓ Created captain user")

conn.commit()

# Now create test maintenance requests
c.execute("""
    INSERT INTO maintenance_requests
    (request_id, ship_name, maintenance_type, request_type, priority, criticality, description,
     location, estimated_duration, resources_needed, requested_by,
     status, severity, assessment_details, workflow_status, created_at, updated_at, submitted_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('MRQ001', 'Test Vessel', 'repair', 'engine repair', 'high', 'urgent', 
      'Engine failure test',
      'Port A', '4 hours', 'Tools needed', 'CE001',
      'submitted', 'MAJOR', 'Auto-assessed', 'submitted', datetime.now(), datetime.now(), 'CE001'))
print("✓ Created test request from chief engineer")

c.execute("""
    INSERT INTO maintenance_requests
    (request_id, ship_name, maintenance_type, request_type, priority, criticality, description,
     location, estimated_duration, resources_needed, requested_by,
     status, severity, assessment_details, workflow_status, created_at, updated_at, submitted_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('MRQ002', 'Test Vessel 2', 'inspection', 'hull inspection', 'medium', 'high', 
      'Hull integrity check test',
      'Port B', '2 hours', 'Equipment needed', 'CAP001',
      'submitted', 'MINOR', 'Auto-assessed', 'submitted', datetime.now(), datetime.now(), 'CAP001'))
print("✓ Created test request from captain")

c.execute("""
    INSERT INTO maintenance_requests
    (request_id, ship_name, maintenance_type, request_type, priority, criticality, description,
     location, estimated_duration, resources_needed, requested_by,
     status, severity, assessment_details, workflow_status, created_at, updated_at, submitted_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('MRQ003', 'Test Vessel 3', 'maintenance', 'pump maintenance', 'low', 'medium', 
      'Pump maintenance test',
      'Port C', '1 hour', 'Spare parts', 'CE001',
      'approved', 'MINOR', 'Auto-assessed', 'approved', datetime.now(), datetime.now(), 'CE001'))
print("✓ Created approved test request from chief engineer")

conn.commit()

# Verify the data
print("\nDatabase contents:")
c.execute('SELECT user_id, email, role FROM users WHERE role IN ("chief_engineer", "captain", "port_engineer")')
print("\nUsers:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]} ({row[2]})")

c.execute('SELECT request_id, ship_name, submitted_by, status FROM maintenance_requests ORDER BY created_at DESC')
print("\nMaintenance Requests:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]} (submitted_by: {row[2]}, status: {row[3]})")

conn.close()
