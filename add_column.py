import sqlite3

conn = sqlite3.connect('marine.db')
c = conn.cursor()

# Add submitted_by column if it doesn't exist
try:
    c.execute("ALTER TABLE maintenance_requests ADD COLUMN submitted_by TEXT")
    print("✓ Added submitted_by column")
except sqlite3.OperationalError as e:
    print(f"Column may already exist: {e}")

conn.commit()

# Verify the column exists
c.execute("PRAGMA table_info(maintenance_requests)")
columns = c.fetchall()
print("\nMaintenance Requests columns:")
for col in columns:
    print(f"  {col[1]}: {col[2]}")

# Check if there are any records
c.execute('SELECT COUNT(*) as count FROM maintenance_requests')
total = c.fetchone()[0]
print(f'\nTotal maintenance requests: {total}')

conn.close()
