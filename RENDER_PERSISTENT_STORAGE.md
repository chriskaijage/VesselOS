# Render Persistent Storage Setup

## Issue
The SQLite database was being deleted on every deployment because Render uses ephemeral storage by default. This caused all thread conversations and other data to be lost.

## Solution
The application now supports Render's persistent disk storage. Follow these steps to enable it:

### Steps to Enable Persistent Storage on Render:

1. **Go to your Render Dashboard**
   - Visit: https://dashboard.render.com

2. **Select your Marine Service Center service**
   - Name: `marine-service-center` (or similar)

3. **Navigate to Disks section**
   - In the left sidebar, find and click "Disks"

4. **Create a new persistent disk**
   - Click "Create Disk"
   - Name: `data` (important - must match render.yaml)
   - Mount Path: `/var/data` (important - must match render.yaml)
   - Size: `1 GB` (or more if needed for future growth)

5. **Save and redeploy**
   - Click "Create"
   - The service will automatically redeploy with the disk attached

6. **Verify it worked**
   - Check the deploy logs - you should see: `[OK] Using database file: /var/data/marine.db`
   - Add data/conversations and deploy again
   - After redeployment, your data should still be there

## How It Works

- **Before**: Database file (`marine.db`) was stored in the ephemeral root directory
  - Every deployment = new dyno = file deleted

- **After**: Database file is now stored in `/var/data` (persistent disk)
  - Persistent disk survives dyno restarts and redeployments
  - Database grows as needed (up to disk size limit)

## What Was Changed

1. **app.py**: 
   - Added support for `PERSISTENT_VOLUME` environment variable
   - Database path now uses `/var/data/marine.db` if available
   - Automatically creates directory if needed

2. **render.yaml**: 
   - New configuration file for Render
   - Defines persistent disk: 1GB at `/var/data`
   - Sets up proper environment variables

## After Setup

- Deploy with `git push` as usual
- Your thread conversations and all data will persist
- The disk will grow as you add more data (up to 1GB limit)
- If you need more space, you can expand the disk in Render dashboard

## Troubleshooting

If data is still being lost:
1. Check your Render dashboard - is the disk showing as "Attached"?
2. Check deploy logs for: `[OK] Using database file: /var/data/marine.db`
3. Make sure the mount path is `/var/data` (not `/data` or something else)
4. If not configured, create the disk in Render dashboard as described above
