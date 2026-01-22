# 📸 How to Test Image/File Attachments in Messages

## Quick Test Steps

### Step 1: Send a Message with Image
1. Open the floating messaging panel
2. Click **"New Message"** or compose in a thread
3. Click **"📎 Attach File"** button
4. Select an image (JPG, PNG, GIF)
5. Type a message: "Test image"
6. Click **"Send"**

### Step 2: View in Thread (FIXED ✅)
1. Go to **"Threads"** tab
2. Click the conversation
3. You should NOW see:
   - ✅ Image **displaying** (not just a download link)
   - ✅ Image preview visible
   - ✅ "Save" button below the image
   - ✅ Image name showing

### Step 3: Save the Image
1. Click **"Save"** button below the image
2. Image downloads to your Downloads folder
3. ✅ File should download successfully

### Step 4: View Fullscreen
1. Click on the image preview itself
2. Modal pops up with full-size image
3. Click **"Download"** in modal to save
4. Click **"Close"** to close modal

### Step 5: Test with Multiple Files
1. Send message with 2+ attachments
2. All should display in thread
3. Each should be saveable independently

---

## Expected Behavior (After Fix)

### Before Fix ❌
- Images in threads: Not visible
- Only download link shown
- Error: "file wasn't available on site"
- No image preview

### After Fix ✅
- Images display inline with preview
- Download button clearly visible
- No errors when saving
- Can view full-size in modal
- Multiple attachments handled properly

---

## Browser Console Check

If images still don't show:

1. **Open Browser DevTools** (F12)
2. Go to **"Console"** tab
3. Check for errors
4. Common errors and fixes:

| Error | Cause | Fix |
|-------|-------|-----|
| 404 on `/api/messaging/download-attachment/` | File path wrong in database | Check `uploads/messages/` folder exists |
| "File not found on server" | Database path mismatch | Run initialization: `python -c "from app import init_db; init_db()"` |
| 403 Forbidden | Permission issue | Ensure user logged in with correct role |
| CORS error | Cross-origin issue | Check headers in browser > Network tab |

---

## File Attachment Storage

**Where files are stored:**
- Local: `uploads/messages/` folder
- Files named: `MSG_TIMESTAMP_originalname.ext`
- Database stores: paths and filenames in JSON format

**To verify files exist:**
```bash
# List all message attachments
dir uploads\messages\
```

---

## Testing Checklist

- [ ] Send message with single image
- [ ] Image displays in conversation thread
- [ ] Image has "Save" button
- [ ] "Save" button downloads file correctly
- [ ] Click image to open fullscreen view
- [ ] Send message with 2 images
- [ ] Both images display
- [ ] Each has own Save button
- [ ] Send message with mixed files (PDF + image)
- [ ] All types display properly
- [ ] Switch to different conversation and back
- [ ] Images still display
- [ ] Reload page - images still show
- [ ] Test on mobile/tablet - displays responsive

---

## Advanced Testing (Backend)

### Check Conversation Endpoint Response

```bash
# Local testing with curl:
curl -X GET http://localhost:5000/api/messaging/conversation/USER_ID \
  -H "Cookie: session=YOUR_SESSION" \
  -H "Content-Type: application/json"
```

**Should return JSON with `attachments` array:**
```json
{
  "success": true,
  "messages": [
    {
      "message_id": "MSG123",
      "message": "Here's an image",
      "sender_name": "John Doe",
      "attachments": [
        {
          "index": 0,
          "filename": "photo.jpg"
        }
      ],
      "created_at": "2026-01-22T10:30:00"
    }
  ]
}
```

### Verify Files Exist

```bash
# PowerShell - check file exists
Test-Path "uploads\messages\MSG_20260122103000_photo.jpg"

# List files
Get-ChildItem "uploads\messages\" | Select-Object Name, Length
```

---

## Production Testing (Render)

### 1. Deploy to Render
- Changes already pushed to GitHub
- Render auto-deploys (check dashboard)

### 2. Test on Live App
- Visit your Render URL: `https://marine-service-center-xxxxx.onrender.com`
- Login with test account
- Send message with image
- Verify displays in thread

### 3. Check Render Logs
- Render Dashboard → Your Service
- Click **"Logs"** tab
- Look for any errors
- Should see: successful GET `/api/messaging/conversation/`

### 4. Monitor Performance
- Render Dashboard → **"Metrics"** tab
- Check CPU, Memory usage
- Should be normal (no spikes)

---

## Troubleshooting

### Images Still Not Showing?

1. **Clear browser cache:**
   - Ctrl+Shift+Delete (Windows)
   - Cmd+Shift+Delete (Mac)
   - Select "All time"
   - Click "Clear"

2. **Refresh page:**
   - Ctrl+R (Windows) or Cmd+R (Mac)
   - Or hard refresh: Ctrl+F5

3. **Check database:**
   - Attachments stored in `messaging_system` table
   - Check `attachment_path` column has JSON

4. **Verify file exists on disk:**
   ```bash
   ls -la uploads/messages/
   ```

5. **Check server logs:**
   - If local: Terminal output
   - If Render: Dashboard → Logs

### "File not found" Error?

- Files moved or deleted from `uploads/messages/`
- Re-upload the image
- Use fresh test image

### Download Button Not Working?

- Check browser's download settings
- Try right-click → "Save image as..."
- Check Downloads folder for popup notifications

---

## Support

If issues persist after applying this fix:

1. Check `MESSAGE_ATTACHMENTS_FIX.md` for technical details
2. Verify Git commit: `d58ee6f` is in your history
3. Confirm Render has auto-deployed latest code
4. Check server logs for any error messages
5. Test with smaller image file (< 5MB)

**Commit Reference:** d58ee6f (Fix: Include attachments in conversation messages endpoint)
