#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timedelta
import uuid

conn = sqlite3.connect('marine.db')
c = conn.cursor()

# First, check the messages table structure
c.execute("PRAGMA table_info(messages)")
columns = c.fetchall()
print("Messages table structure:")
for col in columns:
    print(f"  {col[1]}: {col[2]}")

print("\n" + "="*60)

# Create test messages between users
test_messages = [
    {
        'message_id': str(uuid.uuid4()),
        'sender_id': 'PE001',
        'recipient_id': 'HM001',
        'message_text': 'Hello Robert, how are you doing today?',
        'created_at': (datetime.now() - timedelta(hours=2)).isoformat()
    },
    {
        'message_id': str(uuid.uuid4()),
        'sender_id': 'HM001',
        'recipient_id': 'PE001',
        'message_text': 'Hi John! All good, just reviewing some reports. How about you?',
        'created_at': (datetime.now() - timedelta(hours=1, minutes=50)).isoformat()
    },
    {
        'message_id': str(uuid.uuid4()),
        'sender_id': 'PE001',
        'recipient_id': 'HM001',
        'message_text': 'Good to hear! Wanted to discuss the maintenance schedule for next week.',
        'created_at': (datetime.now() - timedelta(hours=1, minutes=30)).isoformat()
    },
    {
        'message_id': str(uuid.uuid4()),
        'sender_id': 'HM001',
        'recipient_id': 'PE001',
        'message_text': 'Sure, let\'s sync up this afternoon. I have a slot at 3 PM.',
        'created_at': (datetime.now() - timedelta(minutes=30)).isoformat()
    },
]

# Check column names from table info
col_names = [col[1] for col in c.execute("PRAGMA table_info(messages)").fetchall()]
print(f"\nAvailable columns: {col_names}\n")

# Try to insert messages
try:
    for msg in test_messages:
        # Adjust based on actual column names
        if 'message_text' in col_names:
            c.execute('''
                INSERT INTO messages 
                (message_id, sender_id, recipient_id, message_text, created_at, is_read)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (msg['message_id'], msg['sender_id'], msg['recipient_id'], 
                  msg['message_text'], msg['created_at']))
        else:
            c.execute('''
                INSERT INTO messages 
                (message_id, sender_id, recipient_id, message, created_at, is_read)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (msg['message_id'], msg['sender_id'], msg['recipient_id'], 
                  msg['message_text'], msg['created_at']))
        print(f"✓ Created message: {msg['sender_id']} -> {msg['recipient_id']}")
    
    conn.commit()
    
    # Verify
    c.execute('SELECT COUNT(*) FROM messages')
    count = c.fetchone()[0]
    print(f"\n✓ Total messages now: {count}")
    
except Exception as e:
    print(f"Error inserting messages: {e}")
    conn.rollback()

conn.close()
