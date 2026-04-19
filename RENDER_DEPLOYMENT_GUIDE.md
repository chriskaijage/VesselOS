# Render Deployment Guide - VesselOS

## ✅ Pre-Deployment Steps Completed
- [x] Demo account login issue fixed
- [x] Code committed to git
- [x] Changes pushed to GitHub: https://github.com/chriskaijage/VesselOS

## 🚀 Deploy to Render

### Step 1: Visit Render Dashboard
Go to **https://dashboard.render.com**

### Step 2: Sign In / Sign Up
- If you don't have an account, sign up with email: **chriskaijage02@gmail.com**
- Or sign in if you already have an account

### Step 3: Connect GitHub
1. Click **"New +"** button
2. Select **"Web Service"**
3. Click **"Connect Repository"**
4. Search for **"VesselOS"** repository
5. Click **"Connect"** next to the VesselOS repo

### Step 4: Configure Deployment
The following settings should be auto-detected from `render.yaml`:

**Basic Settings:**
- **Name:** VesselOS
- **Runtime:** Python
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app`
- **Plan:** Free (Auto-scales, suitable for demo)

**Environment Variables (Auto-configured):**
- `PYTHON_VERSION`: 3.11.5
- `PERSISTENT_VOLUME`: /var/data

**Persistent Disk:**
- **Name:** data
- **Mount Path:** /var/data
- **Size:** 10 GB
- This preserves database and uploads across deployments ✓

### Step 5: Deploy
Click **"Create Web Service"** and Render will:
1. ✅ Clone your GitHub repository
2. ✅ Install dependencies from requirements.txt
3. ✅ Build the application
4. ✅ Start the service with gunicorn
5. ✅ Assign you a .onrender.com URL

---

## 📋 What Gets Deployed
- **Application:** Flask-based VesselOS system
- **Database:** SQLite (marine.db in persistent volume)
- **Static Files:** CSS, JS, images (served by Gunicorn)
- **Demo Accounts:** Pre-configured and ready to use

---

## 🔐 Demo Accounts Available After Deployment
After deployment, use these credentials to test the application:

| Account | Email | Password | Role |
|---------|-------|----------|------|
| Port Engineer | port_engineer@marine.com | Engineer@2026 | Full Access |
| DMPO HQ | dmpo@marine.com | Quality@2026 | Quality Officer |
| Harbour Master | harbour_master@marine.com | Harbour@2026 | Port Operations |

---

## 💡 Important Notes

1. **First Load:** May take 1-2 minutes as the application initializes on first request
2. **Database:** Automatically created and persisted in `/var/data`
3. **Logs:** Available in Render dashboard for debugging
4. **Auto-Deploy:** Enabled - any push to master branch triggers automatic redeploy
5. **Free Plan Limits:** Service spins down after 15 minutes of inactivity (normal for free tier)

---

## 📍 After Deployment
Once deployed, you'll receive:
- A unique URL: `https://vesselOS-xxxxx.onrender.com`
- Email confirmation to: chriskaijage02@gmail.com
- Dashboard access to manage your service

---

## 🆘 Troubleshooting
- **Build Failed?** Check Render logs for missing dependencies
- **Can't Login?** Database initializes on first request - wait 2-3 minutes
- **Service Won't Start?** Check that PORT environment variable is being used (Render sets this automatically)

---

## Next Steps
1. Visit https://dashboard.render.com
2. Complete deployment following the steps above
3. Test with demo accounts once deployment is live
4. Check application URL from Render dashboard

Questions? Check the Render documentation: https://render.com/docs
