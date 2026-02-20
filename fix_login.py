#!/usr/bin/env python3
"""Quick script to fix the login database with correct passwords."""

import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

os.chdir(os.path.dirname(__file__))

# Remove old database
if os.path.exists('marine.db'):
    os.remove('marine.db')
    print("[OK] Old database removed")

# Create connection
conn = sqlite3.connect('marine.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Create minimal users table
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        first_name TEXT,
        last_name TEXT,
        rank TEXT,
        role TEXT NOT NULL,
        phone TEXT,
        department TEXT,
        location TEXT,
        profile_pic TEXT,
        signature_path TEXT,
        is_active INTEGER DEFAULT 1,
        is_approved INTEGER DEFAULT 1,
        survey_end_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        last_activity TIMESTAMP,
        is_online INTEGER DEFAULT 0,
        two_factor_enabled INTEGER DEFAULT 0,
        two_factor_secret TEXT,
        access_expiry TIMESTAMP
    )
''')

# Add demo accounts with CORRECT passwords
accounts = [
    ('PE001', 'port_engineer@marine.com', 'Engineer@2026', 'John', 'Smith', 'Port Engineer', 'port_engineer'),
    ('QO001', 'dmpo@marine.com', 'Quality@2026', 'DMPO', 'HQ', 'DMPO HQ', 'quality_officer'),
    ('HM001', 'harbour_master@marine.com', 'Harbour@2026', 'Robert', 'Wilson', 'Harbour Master', 'harbour_master'),
]

for user_id, email, password, first_name, last_name, rank, role in accounts:
    hashed_pwd = generate_password_hash(password)
    c.execute('''
        INSERT INTO users (user_id, email, password, first_name, last_name, rank, role, is_approved, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)
    ''', (user_id, email, hashed_pwd, first_name, last_name, rank, role))

# For QO add survey end date
survey_end = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
c.execute("UPDATE users SET survey_end_date = ? WHERE role = 'quality_officer'", (survey_end,))

conn.commit()
conn.close()

print("[OK] Demo accounts created with correct passwords:")
print("   1. Email: port_engineer@marine.com")
print("      Password: Engineer@2026")
print("      Role: Port Engineer (Admin)")
print()
print("   2. Email: dmpo@marine.com")
print("      Password: Quality@2026")
print("      Role: DMPO HQ (Quality Officer)")
print()
print("   3. Email: harbour_master@marine.com")
print("      Password: Harbour@2026")
print("      Role: Harbour Master")
