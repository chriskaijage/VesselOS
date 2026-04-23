import sqlite3

conn = sqlite3.connect('marine.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Check the maintenance_requests schema
print("=== maintenance_requests table schema ===")
c.execute("PRAGMA table_info(maintenance_requests)")
columns = [dict(row) for row in c.fetchall()]

for col in columns:
    print(f"  {col['name']}: {col['type']}")

print("\n=== Looking for submitted_by column ===")
has_submitted_by = any(col['name'] == 'submitted_by' for col in columns)
print(f"  submitted_by exists: {has_submitted_by}")

conn.close()
