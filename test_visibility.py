import sqlite3
from datetime import datetime

conn = sqlite3.connect('marine.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 70)
print("MAINTENANCE REQUEST VISIBILITY TEST")
print("=" * 70)

# Test 1: Chief Engineer viewing their requests
print("\n1. CHIEF ENGINEER (CE001) - Viewing Their Requests")
print("-" * 70)
c.execute("""
    SELECT request_id, ship_name, status, severity, submitted_by, requested_by
    FROM maintenance_requests
    WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?)
    ORDER BY created_at DESC
""", ('CE001', 'CE001', 'chief@marine.com'))
requests = c.fetchall()
print(f"Found {len(requests)} request(s):")
for req in requests:
    print(f"  • {req['request_id']}: {req['ship_name']} (Status: {req['status']}, Severity: {req['severity']})")
    print(f"    submitted_by: {req['submitted_by']}, requested_by: {req['requested_by']}")

# Test 2: Captain viewing their requests
print("\n2. CAPTAIN (CAP001) - Viewing Their Requests")
print("-" * 70)
c.execute("""
    SELECT request_id, ship_name, status, severity, submitted_by, requested_by
    FROM maintenance_requests
    WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?)
    ORDER BY created_at DESC
""", ('CAP001', 'CAP001', 'captain@marine.com'))
requests = c.fetchall()
print(f"Found {len(requests)} request(s):")
for req in requests:
    print(f"  • {req['request_id']}: {req['ship_name']} (Status: {req['status']}, Severity: {req['severity']})")
    print(f"    submitted_by: {req['submitted_by']}, requested_by: {req['requested_by']}")

# Test 3: Port Engineer viewing pending requests
print("\n3. PORT ENGINEER (PE001) - Viewing Pending Approval Requests")
print("-" * 70)
c.execute("""
    SELECT 
        mr.request_id, mr.ship_name, mr.status, mr.severity, mr.priority,
        mr.submitted_by, mr.requested_by,
        u.first_name || ' ' || u.last_name as submitter_name,
        u.email as submitter_email
    FROM maintenance_requests mr
    LEFT JOIN users u ON mr.submitted_by = u.user_id
    WHERE mr.status IN ('submitted', 'pending')
    AND (mr.approved IS NULL OR mr.approved = 0)
    AND mr.rejection_reason IS NULL
    ORDER BY mr.priority DESC, mr.created_at DESC
""")
requests = c.fetchall()
print(f"Found {len(requests)} request(s) pending approval:")
for req in requests:
    print(f"  • {req['request_id']}: {req['ship_name']}")
    print(f"    Status: {req['status']}, Priority: {req['priority']}, Severity: {req['severity']}")
    print(f"    Submitted by: {req['submitter_name']} ({req['submitter_email']})")
    print(f"    submitted_by: {req['submitted_by']}, requested_by: {req['requested_by']}")

# Test 4: Dashboard statistics for Chief Engineer
print("\n4. CHIEF ENGINEER DASHBOARD STATISTICS")
print("-" * 70)
c.execute("""
    SELECT COUNT(*) as count
    FROM maintenance_requests
    WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?)
""", ('CE001', 'CE001', 'chief@marine.com'))
total = c.fetchone()['count']
print(f"Total requests: {total}")

c.execute("""
    SELECT COUNT(*) as count
    FROM maintenance_requests
    WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?) AND status IN ('submitted', 'pending')
""", ('CE001', 'CE001', 'chief@marine.com'))
pending = c.fetchone()['count']
print(f"Pending approval: {pending}")

c.execute("""
    SELECT COUNT(*) as count
    FROM maintenance_requests
    WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?) AND status = 'approved'
""", ('CE001', 'CE001', 'chief@marine.com'))
approved = c.fetchone()['count']
print(f"Approved: {approved}")

# Test 5: Database column verification
print("\n5. DATABASE SCHEMA VERIFICATION")
print("-" * 70)
c.execute("PRAGMA table_info(maintenance_requests)")
columns = [col[1] for col in c.fetchall()]
if 'submitted_by' in columns:
    print("✓ submitted_by column EXISTS in maintenance_requests table")
else:
    print("✗ submitted_by column MISSING from maintenance_requests table")

print(f"\nTotal columns: {len(columns)}")
print(f"Key columns: requested_by, submitted_by, status, severity, priority")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)

conn.close()
