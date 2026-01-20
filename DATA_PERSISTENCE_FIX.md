# Data Persistence Issue - Diagnosis & Fix

## Problem
User reported that messages, uploads, and maintenance requests disappear when they log out and back in.

## Root Cause Analysis

The issue appears to be caused by one or more of the following:

1. **Database Commit Failures**: Exception being thrown after INSERT but before COMMIT
2. **Transaction Rollback**: Silent rollback on exceptions  
3. **SQLite Locking**: Race conditions or WAL mode not enabled
4. **FK Constraints**: Foreign key violations causing cascading rollbacks

## Solutions Implemented

### 1. Enable SQLite WAL Mode (Write-Ahead Logging)
**File**: `app.py` line ~135
```python
def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'], timeout=20)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency and durability
    conn.execute('PRAGMA journal_mode=WAL')
    # Ensure foreign keys are enforced
    conn.execute('PRAGMA foreign_keys=ON')
    return conn
```

**Benefits**:
- Improved concurrency - readers don't block writers
- Better crash recovery
- Better durability guarantees
- More efficient for concurrent access patterns

### 2. Enhanced Error Logging
**Files**: `app.py` maintenance requests & messaging endpoints
- Added full stack traces to error logging
- Added print statements for immediate console feedback
- Better visibility into where data loss occurs

### 3. Improved Exception Handling
All data-modifying endpoints now have:
- Proper try-except blocks
- Connection rollback on failure
- Detailed error messages
- Stack trace capture

## Testing the Fix

### 1. Check if WAL mode is enabled:
```sql
PRAGMA journal_mode;
-- Should return: wal
```

### 2. Test maintenance request creation:
```bash
# Check console for "✅ REQUEST CREATED..." message
# Check database with:
python -c "import sqlite3; conn = sqlite3.connect('marine.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM maintenance_requests'); print(f'Requests: {c.fetchone()[0]}'); conn.close()"
```

### 3. Test message sending:
```bash
# Check console for "✅ MESSAGE SENT..." message
# Check database with:
python -c "import sqlite3; conn = sqlite3.connect('marine.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM messaging_system'); print(f'Messages: {c.fetchone()[0]}'); conn.close()"
```

## Additional Recommendations

If data still disappears after implementing these fixes:

### Option 1: Add Pre-Commit Verification
```python
# After all INSERT/UPDATE statements, before commit:
c.execute("SELECT CHANGES()")
affected_rows = c.fetchone()[0]
if affected_rows == 0:
    raise Exception("No rows were modified - check for constraint violations")
```

### Option 2: Add Transaction Logging
```python
# Log all transactions
c.execute(f"INSERT INTO transaction_log (timestamp, action, rows_affected) VALUES (?, ?, ?)",
          (datetime.now(), 'message_insert', affected_rows))
```

### Option 3: Use Database Connection Pooling
Replace direct sqlite3 with connection pooling for better concurrency.

## Long-term Solutions

1. **Upgrade to PostgreSQL** for better ACID guarantees and concurrency
2. **Implement Event Sourcing** - store all changes as events
3. **Add Message Queue** (Redis/RabbitMQ) for reliable data ingestion
4. **Implement Audit Logging** - track all data changes

## Monitoring

Check these regularly:

```bash
# Monitor database file size and modification time
Get-Item marine.db | Select-Object Length, LastWriteTime

# Check application logs for errors
tail -f app.log | grep -i error

# Monitor disk space
diskutil info /
```

## Next Steps

1. Restart the application
2. Test creating maintenance requests and sending messages
3. Verify data persists after logout/login
4. Monitor console logs for any error messages
5. If issues persist, review full stack traces in the logs
