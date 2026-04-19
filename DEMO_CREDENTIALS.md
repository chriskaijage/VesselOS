# VesselOS Demo Account Credentials - VERIFIED

## Issue Fixed
The system was displaying conflicting password information for demo accounts. The source code was creating accounts with `Engineer@2026` but printing `Admin@2025` in the initialization output, causing login failures.

## ✅ Correct Login Credentials

### Account 1 - Port Engineer (Admin - Full Access)
```
Email:    port_engineer@marine.com
Password: Engineer@2026
Role:     Port Engineer
Access:   Full system access
```

### Account 2 - DMPO HQ (Quality Officer)
```
Email:    dmpo@marine.com
Password: Quality@2026
Role:     Quality Officer
Access:   Inspection and compliance
```

### Account 3 - Harbour Master
```
Email:    harbour_master@marine.com
Password: Harbour@2026
Role:     Harbour Master
Access:   Port operations management
```

## What Was Fixed
- **File:** `app.py` line 13839
- **Change:** Corrected Port Engineer password from `Admin@2025` to `Engineer@2026` in console output
- **Reason:** The actual password created in the database is `Engineer@2026` (line 12496), so the console output now correctly reflects what's in the database
- **Git Commit:** `507f25e` - "Fix demo account password display"

## To Login
1. Run the application: `python app.py`
2. Navigate to the login page
3. Use any of the credentials above
4. The system will initialize with these demo accounts

## Testing
All demo accounts have been verified to work with the passwords listed above.
