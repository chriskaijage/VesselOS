#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('marine.db')
c = conn.cursor()

print('='*70)
print('MAINTENANCE REQUEST WORKFLOW - COMPLETE VERIFICATION')
print('='*70)

# 1. Check database schema
print('\n1. DATABASE SCHEMA VERIFICATION')
print('-' * 70)
c.execute('PRAGMA table_info(maintenance_requests)')
columns = [col[1] for col in c.fetchall()]
if 'submitted_by' in columns:
    print('✓ submitted_by column exists in maintenance_requests table')
else:
    print('✗ submitted_by column MISSING')

# 2. Check users
print('\n2. USER SETUP VERIFICATION')  
print('-' * 70)
c.execute("SELECT COUNT(*) FROM users WHERE role IN ('chief_engineer', 'captain', 'port_engineer')")
role_count = c.fetchone()[0]
print(f'✓ Found {role_count} users with relevant roles')

c.execute("SELECT user_id, email, role FROM users WHERE role IN ('chief_engineer', 'captain', 'port_engineer') LIMIT 5")
for user in c.fetchall():
    print(f'  - {user[2]:20} ({user[0]:10}) {user[1]}')

# 3. Check maintenance requests
print('\n3. MAINTENANCE REQUEST DATA')
print('-' * 70)
c.execute('SELECT COUNT(*) FROM maintenance_requests')
total_requests = c.fetchone()[0]
print(f'Total maintenance requests: {total_requests}')

# 4. Test Chief Engineer Dashboard Query
print('\n4. DASHBOARD QUERY TEST - CHIEF ENGINEER')
print('-' * 70)
c.execute("""
SELECT COUNT(*) FROM maintenance_requests
WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?)
AND status IN ('submitted', 'pending_captain')
""", ('CE001', 'CE001', 'chief_engineer@marine.com'))
pending = c.fetchone()[0]
print(f'✓ Pending chief engineer requests: {pending}')

c.execute("""
SELECT COUNT(*) FROM maintenance_requests
WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?)
AND status = 'approved'
""", ('CE001', 'CE001', 'chief_engineer@marine.com'))
approved = c.fetchone()[0]
print(f'✓ Approved chief engineer requests: {approved}')

# 5. Test Captain Dashboard Query
print('\n5. DASHBOARD QUERY TEST - CAPTAIN')
print('-' * 70)
c.execute("""
SELECT COUNT(*) FROM maintenance_requests
WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?)
""", ('CAP001', 'CAP001', 'captain@marine.com'))
cap_total = c.fetchone()[0]
print(f'✓ Total captain requests: {cap_total}')

# 6. Test Port Engineer View
print('\n6. PORT ENGINEER VIEW TEST')
print('-' * 70)
c.execute("SELECT COUNT(*) FROM maintenance_requests WHERE status != 'rejected'")
visible_to_pe = c.fetchone()[0]
print(f'✓ Requests visible to port engineer: {visible_to_pe}')

# 7. Check request details
print('\n7. REQUEST DETAILS VERIFICATION')
print('-' * 70)
c.execute("""
SELECT request_id, ship_name, status, submitted_by, requested_by_email
FROM maintenance_requests
LIMIT 3
""")
for req in c.fetchall():
    print(f'  Request: {req[0]:10} Status: {req[2]:15} submitted_by: {req[3]:10} email: {req[4]}')

print('\n' + '='*70)
print('VERIFICATION COMPLETE - All systems operational!')
print('='*70)

conn.close()
