import sqlite3

conn = sqlite3.connect('marine.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Check recent requests
c.execute('''
    SELECT request_id, ship_name, submitted_by, requested_by, status 
    FROM maintenance_requests 
    ORDER BY created_at DESC 
    LIMIT 10
''')

print("\n=== Recent Maintenance Requests ===")
for row in c.fetchall():
    row_dict = dict(row)
    print(f"ID: {row_dict['request_id']}")
    print(f"  Ship: {row_dict['ship_name']}")
    print(f"  Submitted By: {row_dict['submitted_by']}")
    print(f"  Requested By: {row_dict['requested_by']}")
    print(f"  Status: {row_dict['status']}")
    print()

conn.close()
