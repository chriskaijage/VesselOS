#!/usr/bin/env python3
import sqlite3
from datetime import datetime
import uuid

conn = sqlite3.connect('marine.db')
c = conn.cursor()

# Create test messages using messaging_system table
test_messages = [
    {
        'sender_id': 'PE001',
        'recipient_id': 'HM001',
        'title': 'Hello',
        'message': 'Hi Robert! Just checking in. How are the vessel reports coming along?'
    },
    {
        'sender_id': 'HM001',
        'recipient_id': 'PE001',
        'title': 'Re: Hello',
        'message': 'Hey John! All good, almost done with the inspection reports. Should be ready tomorrow.'
    },
    {
        'sender_id': 'PE001',
        'recipient_id': 'HM001',
        'title': 'Maintenance Schedule',
        'message': 'Robert, can we discuss the maintenance schedule for next week? I have some concerns about the timing.'
    },
    {
        'sender_id': 'HM001',
        'recipient_id': 'PE001',
        'title': 'Re: Maintenance Schedule',
        'message': 'Sure, let\'s set up a meeting. How about 3 PM this afternoon in the conference room?'
    },
]

for msg in test_messages:
    msg_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    c.execute('''
        INSERT INTO messaging_system 
        (message_id, sender_id, recipient_type, recipient_id, title, message, 
         message_type, priority, is_read, allow_replies, created_at)
        VALUES (?, ?, 'specific_user', ?, ?, ?, 'message', 'normal', 0, 1, ?)
    ''', (msg_id, msg['sender_id'], msg['recipient_id'], msg['title'], msg['message'], created_at))
    print(f"✓ {msg['sender_id']} -> {msg['recipient_id']}: {msg['title']}")

conn.commit()

# Verify
c.execute('SELECT COUNT(*) FROM messaging_system')
count = c.fetchone()[0]
print(f'\n✓ Total messages in messaging_system: {count}')

conn.close()
