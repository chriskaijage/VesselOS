#!/usr/bin/env python
import sys
sys.path.insert(0, '.')
from app import get_db_connection
from werkzeug.security import check_password_hash

conn = get_db_connection()
c = conn.cursor()

# Get all demo users
c.execute("SELECT user_id, email, password, role FROM users WHERE email IN ('port_engineer@marine.com', 'dmpo@marine.com', 'harbour_master@marine.com')")
users = c.fetchall()

print('Demo Accounts in Database:')
print('=' * 100)

for user in users:
    user_id, email, password_hash, role = user
    print(f'\nEmail: {email}')
    print(f'Role: {role}')
    print(f'Password Hash: {password_hash[:50]}...')
    
    # Test various passwords
    test_passwords = [
        'Admin@2025',
        'Engineer@2026',
        'Harbour@2026',
        'Quality@2026'
    ]
    
    print('Testing passwords:')
    for pwd in test_passwords:
        try:
            if check_password_hash(password_hash, pwd):
                print(f'  ✓ {pwd} - MATCHES')
            else:
                print(f'  ✗ {pwd} - no match')
        except Exception as e:
            print(f'  ✗ {pwd} - error: {e}')

conn.close()
