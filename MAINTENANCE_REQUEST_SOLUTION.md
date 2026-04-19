# Maintenance Request Workflow - Complete Solution

## Overview
This document summarizes the complete fix for the maintenance request workflow issue where chief engineers and captains can now track the maintenance requests they've submitted, and port engineers can view and approve/reject them.

## Problem Statement
**Original Issue:** When a chief engineer or captain submitted a maintenance request, they couldn't view it in their dashboard, and port engineers couldn't view pending requests.

**Root Cause:** The system added a new `submitted_by` column to track who submitted maintenance requests, but the API queries only checked this new column. All existing requests had `submitted_by = NULL`, causing dashboards to show zero data.

## Solution Implemented

### 1. Database Schema Update
- Added `submitted_by TEXT` column to `maintenance_requests` table
- This column stores the user ID of who submitted the request
- Maintains backward compatibility with existing `requested_by` field

### 2. Query Backward Compatibility
Updated all relevant API queries to use OR conditions that check BOTH fields:
```sql
WHERE (submitted_by = ? OR requested_by = ? OR requested_by = ?)
```
Parameters: (current_user.id, current_user.id, current_user.email)

**Updated Endpoints:**
- `api_chief_engineer_dashboard_data()` - Show chief engineer's sent requests and status counts
- `api_chief_engineer_my_requests()` - Retrieve chief engineer's submitted requests  
- `api_captain_dashboard_data()` - Show captain's sent requests and status counts
- `api_maintenance_requests_create()` - Properly track submitted_by when creating requests

### 3. Frontend Updates
**chief_engineer_dashboard.html:**
- Added "Approved" count card
- Added "Rejected" count card
- Updated JavaScript to fetch and display new status metrics

**captain_dashboard.html:**
- Added "Total Requests" count card
- Added "Rejected" count card
- Updated JavaScript to fetch and display new status metrics

### 4. API Response Structure
Dashboard APIs now return:
```json
{
  "total_requests": 5,
  "pending_approval": 2,
  "in_progress": 1,
  "completed": 1,
  "approved": 1,
  "rejected": 0
}
```

## Workflow Verification

### Chief Engineer / Captain Flow
1. Create maintenance request → Stored with `submitted_by = current_user.id`
2. Dashboard displays count and status of submitted requests
3. Can review approval/rejection status

### Port Engineer Flow
1. Views all pending maintenance requests via `/api/maintenance-requests/pending-approval`
2. Can approve requests (updates status to 'approved')
3. Can reject requests (updates status to 'rejected')

### Test Results
✓ Database schema correctly updated
✓ Dashboard queries work for both roles
✓ Backward compatibility maintained with existing requests
✓ Port engineer can view all pending requests
✓ Status counts display correctly

## Files Modified
1. `app.py` - API endpoints and database queries
2. `chief_engineer_dashboard.html` - Dashboard UI and fetch logic
3. `captain_dashboard.html` - Dashboard UI and fetch logic

## Commits
1. Initial implementation: "CRITICAL FIX: Add backward compatibility to maintenance request queries"
2. Schema update: "Add submitted_by column and test data for maintenance request workflow verification"

## Testing
Run `python verify_workflow.py` to validate the complete workflow setup.

## Deployment Notes
- No breaking changes
- Backward compatible with existing data
- Database migration: ALTER TABLE maintenance_requests ADD COLUMN submitted_by TEXT
- Test data included for validation
