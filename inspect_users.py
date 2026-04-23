import sqlite3

conn = sqlite3.connect('marine.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Check all users
print("=== All Users ===")
c.execute('SELECT user_id, email, role, first_name FROM users ORDER BY created_at DESC LIMIT 10')
for row in c.fetchall():
    row_dict = dict(row)
    print(f"  User ID: {row_dict['user_id']}, Email: {row_dict['email']}, Role: {row_dict['role']}, Name: {row_dict['first_name']}")

print("\n=== Requests and who created them ===")
c.execute('''
    SELECT request_id, submitted_by, requested_by, status 
    FROM maintenance_requests 
    ORDER BY created_at DESC 
    LIMIT 10
''')

for row in c.fetchall():
    row_dict = dict(row)
    req_id = row_dict['request_id']
    sub_by = row_dict['submitted_by']
    req_by = row_dict['requested_by']
    status = row_dict['status']
    print(f"  {req_id}: submitted_by={sub_by}, requested_by={req_by}, status={status}")
    
    # Look up the user
    if sub_by:
        c.execute('SELECT user_id, email FROM users WHERE user_id = ?', (sub_by,))
        user_row = c.fetchone()
        if user_row:
            user = dict(user_row)
            print(f"    -> Submitted by user: {user['user_id']} ({user['email']})")

conn.close()
