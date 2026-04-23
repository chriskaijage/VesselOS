#!/usr/bin/env python3
"""
Script to verify and clean test maintenance requests from the database.
"""

import sqlite3
import sys
from datetime import datetime

db_path = 'marine.db'

def cleanup_test_maintenance_requests():
    """Delete test/demo maintenance requests from database."""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Check if maintenance_requests table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_requests'")
        if not c.fetchone():
            print("❌ maintenance_requests table not found")
            return False
        
        # Find test requests
        test_keywords = ['test', 'demo', 'sample', 'example', 'debug', 'temporary']
        
        c.execute("""
            SELECT request_id, ship_name, maintenance_type, description, created_at, status
            FROM maintenance_requests
            ORDER BY created_at DESC
        """)
        
        all_requests = c.fetchall()
        print(f"Total maintenance requests: {len(all_requests)}\n")
        
        test_requests = []
        for req in all_requests:
            request_id, ship_name, maintenance_type, description, created_at, status = req
            combined_text = f"{ship_name} {description}".lower()
            
            # Check if request is a test record
            if any(keyword in combined_text for keyword in test_keywords):
                test_requests.append(request_id)
                print(f"🔴 TEST: {request_id}")
                print(f"   Type: {maintenance_type}")
                print(f"   Ship: {ship_name}")
                print(f"   Status: {status}")
                print(f"   Created: {created_at}\n")
        
        if test_requests:
            print(f"\n⚠️  Found {len(test_requests)} test/demo requests\n")
            
            # Delete test requests
            print("🗑️  Deleting test requests...\n")
            for req_id in test_requests:
                try:
                    # Delete workflow logs first
                    c.execute("DELETE FROM maintenance_workflow_log WHERE request_id = ?", (req_id,))
                    
                    # Delete attachments
                    c.execute("DELETE FROM maintenance_request_attachments WHERE request_id = ?", (req_id,))
                    
                    # Delete the request
                    c.execute("DELETE FROM maintenance_requests WHERE request_id = ?", (req_id,))
                    
                    print(f"✅ Deleted: {req_id}")
                except Exception as e:
                    print(f"❌ Error deleting {req_id}: {e}")
            
            conn.commit()
            print(f"\n✅ Cleanup complete! Deleted {len(test_requests)} test maintenance requests")
            
        else:
            print("\n✅ No test requests found - database is clean!")
        
        # Show remaining requests
        c.execute("SELECT COUNT(*) FROM maintenance_requests")
        remaining = c.fetchone()[0]
        print(f"\n📊 Remaining maintenance requests: {remaining}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = cleanup_test_maintenance_requests()
    sys.exit(0 if success else 1)
