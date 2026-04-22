import sqlite3

conn = sqlite3.connect('marine.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Check if maintenance_requests table exists and has data
c.execute('SELECT COUNT(*) as count FROM maintenance_requests')
total = c.fetchone()['count']
print(f'Total maintenance requests in DB: {total}')

# Show some sample requests
c.execute('SELECT request_id, ship_name, submitted_by, requested_by, status FROM maintenance_requests LIMIT 10')
for row in c.fetchall():
    print(f'Request: {row["request_id"]}, Ship: {row["ship_name"]}, submitted_by: {row["submitted_by"]}, requested_by: {row["requested_by"]}, status: {row["status"]}')

# Check users
c.execute('SELECT user_id, email, role FROM users LIMIT 5')
print('\nUsers:')
for row in c.fetchall():
    print(f'ID: {row["user_id"]}, Email: {row["email"]}, Role: {row["role"]}')

conn.close()
