# Data Persistence Guide

## Overview

This application uses SQLite with a persistent disk on Render to ensure user data (accounts, conversations, reports) survives deployments.

## Architecture

### Development Environment
- **Database Location**: `./marine.db` (local directory)
- **Persistence**: **Ephemeral** (data lost when server restarts)
- **Use Case**: Local testing and development only

### Production Environment (Render)
- **Database Location**: `/var/data/marine.db` (persistent disk)
- **Persistence**: **Permanent** (data survives all deployments)
- **Disk Size**: 10GB (configured in `render.yaml`)
- **Uploads Location**: `/var/data/uploads/` (also persistent)

## How It Works

### Configuration
The app automatically detects the environment:

```python
PERSISTENT_VOLUME = os.environ.get('PERSISTENT_VOLUME', '')
if PERSISTENT_VOLUME and os.path.isdir(PERSISTENT_VOLUME):
    DB_PATH = os.path.join(PERSISTENT_VOLUME, 'marine.db')
    USING_PERSISTENT_STORAGE = True
else:
    DB_PATH = 'marine.db'
    USING_PERSISTENT_STORAGE = False
```

**On Render**, the `PERSISTENT_VOLUME=/var/data` environment variable is set in `render.yaml`.

### Database Safety

#### Schema Creation
All tables use `CREATE TABLE IF NOT EXISTS` pattern:
```sql
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    ...
)
```

This ensures:
- ✅ Tables created only if they don't exist
- ✅ Existing data NEVER deleted
- ✅ Safe to call `init_db()` multiple times
- ✅ Safe for deployments

#### Demo Account Handling
- **Demo accounts** (port_engineer, dmpo, harbour_master) are **reset** on deployment
- **All user accounts** you create are **preserved**
- **All conversations, reports, requests** you create are **preserved**

#### Data Preservation During Deployments

When the app starts (`init_db()` is called):

1. **Check database existence** - Verify if tables already exist
2. **Preserve all data** - User accounts, messages, reports, etc. remain untouched
3. **Create missing tables** - Any new tables created (backward compatibility)
4. **Reset demo accounts** - Demo credentials reset to factory defaults for testing
5. **Verify persistence** - Log counts of preserved data

Output will show:
```
[DATA PRESERVATION] Deployment Verification:
   Tables preserved before init: 15
   Total users (including demo): 45
   Messages retained: 523
   Maintenance requests retained: 87
   Logbook entries retained: 156
   ✓ ALL DATA PERSISTED ACROSS DEPLOYMENT
```

## Troubleshooting

### Problem: Data disappears after deployment

**Possible Causes:**
1. **Render persistent disk not properly mounted**
   - Check: `PERSISTENT_VOLUME` environment variable set in `render.yaml`?
   - Check: Disk configured with 10GB size?

2. **Database file on wrong location**
   - Check: Database should be at `/var/data/marine.db` on Render
   - Check: Should be at `./marine.db` locally

3. **New deployment = fresh instance**
   - First deploy creates new `/var/data` disk automatically
   - Subsequent deploys reuse same disk (data persists)

### Verification

Check your app logs for these messages:

```
[OK] Data persistence: ENABLED (Render persistent disk)
[OK] Database file verified at: /var/data/marine.db
[OK] Database size: 15.42 MB
[OK] Last modified: 2026-02-03 08:10:15.342102
```

If you see:
```
[WARNING] PERSISTENT_VOLUME not configured. Database will be in current directory.
[WARNING] Set PERSISTENT_VOLUME environment variable for data persistence on deployments.
```

Then data will NOT persist - contact your DevOps team to configure the persistent disk.

## Files Not Persisted

The following are intentionally NOT persisted (use `uploads/` for user files):
- Python cache files (`__pycache__/`)
- Virtual environment (`myenv/`, `venv/`)
- IDE files (`.vscode/`, `.idea/`)
- Log files (outside `/var/data/`)

## Database Schema

The database includes these main tables:
- `users` - User accounts (persisted)
- `messages` - Conversations between users (persisted)
- `maintenance_requests` - Service requests (persisted)
- `drill_reports` - Emergency drills (persisted)
- `emergency_requests` - Emergency situations (persisted)
- `bilge_reports`, `fuel_reports`, `sewage_reports` - International reports (persisted)
- `activity_logs` - User activity audit trail (persisted)

All user-created data is preserved.

## Security Note

The SQLite database file (`marine.db`) contains:
- Hashed passwords (bcrypt)
- Personal user information
- Business-critical reports

**Never commit the database file to Git** - it's in `.gitignore` for security.

## Backup Strategy

Render persistent disks:
- ✅ Automatically backed up by Render
- ✅ Accessible via Render dashboard
- ✅ Can be restored if needed

For manual backups, download the database file from Render:
1. SSH into your Render service
2. Navigate to `/var/data/`
3. Download `marine.db` to safe storage

## Environment Variables

### Development
```bash
# No PERSISTENT_VOLUME set - uses local ephemeral storage
python app.py
```

### Production (Render)
```yaml
# Automatically configured in render.yaml
envVars:
  - key: PERSISTENT_VOLUME
    value: /var/data
```

## Next Steps

If data is still disappearing:
1. Check `render.yaml` has the persistent disk configured
2. Check Render logs for database errors
3. Verify `/var/data/` has write permissions
4. Contact Render support if disk isn't mounting properly
