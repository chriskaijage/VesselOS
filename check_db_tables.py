#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('marine.db')
c = conn.cursor()

# Find all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in c.fetchall()]
print('All tables:')
for t in tables:
    print(f'  - {t}')
    
print("\nLooking for messaging_system table...")
if 'messaging_system' in tables:
    c.execute('PRAGMA table_info(messaging_system)')
    columns = c.fetchall()
    print('messaging_system columns:')
    for col in columns:
        print(f'  {col[1]}: {col[2]}')
else:
    print("messaging_system table NOT FOUND")

conn.close()
