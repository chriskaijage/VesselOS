#!/usr/bin/env python3
import sqlite3
import os

conn = sqlite3.connect('marine.db')
c = conn.cursor()

# Check what profile pictures exist
pics_dir = 'uploads/profile_pics'
if os.path.exists(pics_dir):
    files = os.listdir(pics_dir)
    print(f"Available profile pictures: {files}")
    
    if files:
        # Assign first pic to PE001
        pic_name = files[0]
        c.execute('UPDATE users SET profile_pic = ? WHERE user_id = ?', (pic_name, 'PE001'))
        print(f"✓ Assigned {pic_name} to PE001 (John)")
        
        # Assign second pic to HM001 if available
        if len(files) > 1:
            pic_name2 = files[1]
            c.execute('UPDATE users SET profile_pic = ? WHERE user_id = ?', (pic_name2, 'HM001'))
            print(f"✓ Assigned {pic_name2} to HM001 (Robert)")
        
        conn.commit()
        
        # Show results
        c.execute('SELECT user_id, first_name, profile_pic FROM users WHERE profile_pic IS NOT NULL')
        print("\nUsers with profile pictures:")
        for row in c.fetchall():
            print(f"  {row[0]} ({row[1]}): {row[2]}")
else:
    print(f"Directory {pics_dir} not found")

conn.close()
