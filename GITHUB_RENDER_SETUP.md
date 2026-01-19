# 🚀 Complete GitHub + Render Deployment Guide

**Email:** chriskaijage02@gmail.com  
**Application:** Marine Service Center System  
**Status:** Ready for Production

---

## ⚠️ IMPORTANT: Install Git First

### Step 0: Download and Install Git

1. **Download Git for Windows**
   - Go to: https://git-scm.com/download/win
   - Click "Click here to download" (64-bit recommended)
   - Run the installer
   - Use all default options
   - Click "Install"
   - Click "Finish"

2. **Verify Git Installation**
   - Open Command Prompt (Win + R, type `cmd`, press Enter)
   - Type: `git --version`
   - You should see: `git version 2.x.x...`

⚠️ **STOP HERE AND INSTALL GIT BEFORE PROCEEDING** ⚠️

---

## Step 1: Initialize GitHub Repository Locally

Once Git is installed, open Command Prompt in your project folder and run:

```bash
cd C:\Users\USER\Downloads\marine_service_system-20260117T120137Z-1-001\marine_service_system

git config user.name "Marine Service Center"
git config user.email "chriskaijage02@gmail.com"

git init
git add .
git commit -m "Initial commit: Marine Service Center System - Production Ready"
```

**Expected Output:**
```
Initialized empty Git repository in C:\Users\USER\...\marine_service_system\.git/
[main (root-commit) xxxxx] Initial commit: Marine Service Center System
 XX files changed, XXXXX insertions(+)
```

---

## Step 2: Create GitHub Account & Repository

### 2.1 Create GitHub Account

1. **Go to GitHub**
   - Website: https://github.com
   - Click "Sign up" (top right)

2. **Fill Registration Form**
   - Email: `chriskaijage02@gmail.com`
   - Password: Choose a strong password (12+ characters, mixed case, numbers, symbols)
   - Username: `marine-service-center` (or your preferred name)
   - Verify email when prompted

3. **Complete Registration**
   - Check your email (chriskaijage02@gmail.com)
   - Click verification link
   - Set up profile (optional)

### 2.2 Create Repository on GitHub

1. **After Login, Click "+" (top right) → "New repository"**

2. **Configure Repository**
   - **Repository Name:** `marine-service-center`
   - **Description:** International Marine Service Management System
   - **Public/Private:** Public (required for free Render deployment)
   - **Initialize:** Leave unchecked (we already have files)
   - Click **"Create repository"**

3. **You'll see commands like:**
   ```
   …or push an existing repository from the command line
   git remote add origin https://github.com/YOUR_USERNAME/marine-service-center.git
   git branch -m main
   git push -u origin main
   ```

---

## Step 3: Upload Code to GitHub

Run these commands in Command Prompt (in your project folder):

```bash
git remote add origin https://github.com/YOUR_USERNAME/marine-service-center.git

git branch -m main

git push -u origin main
```

**Replace `YOUR_USERNAME` with your actual GitHub username**

**Expected Output:**
```
Enumerating objects: XX, done.
Counting objects: 100% (XX/XX), done.
Delta compression using up to X threads
Compressing objects: 100% (XX/XX), done.
Writing objects: 100% (XX/XX), XXX KB | XXX.XX MB/s, done.
Total XX (delta X), reused 0 (delta 0), pack-reused 0
To https://github.com/YOUR_USERNAME/marine-service-center.git
 * [new branch]      main -> main
Branch 'main' is set up to track remote branch 'main' from 'origin'.
```

✅ **Code is now on GitHub!**

---

## Step 4: Create Render Account

### 4.1 Sign Up on Render

1. **Go to Render.com**
   - Website: https://render.com
   - Click "Get Started" or "Sign Up"

2. **Create Account**
   - **GitHub Option:** Click "Continue with GitHub"
   - This automatically links your account!
   - Or use email: `chriskaijage02@gmail.com`
   - Choose a strong password
   - Verify email

3. **Complete Setup**
   - Set your name
   - Authorize GitHub access (if using GitHub sign-up)

---

## Step 5: Deploy to Render

### 5.1 Create Web Service

1. **In Render Dashboard**
   - Click **"New +"** (top right)
   - Select **"Web Service"**

2. **Connect GitHub Repository**
   - Click **"Connect your GitHub repo"**
   - Find `marine-service-center`
   - Click **"Connect"**
   - Authorize Render to access GitHub

3. **Configure Web Service**

   **Basic Settings:**
   - **Name:** `marine-service-center`
   - **Region:** Choose closest to you (e.g., US East, EU)
   - **Runtime:** Python 3.11

   **Build Command:**
   ```
   pip install -r requirements.txt
   ```

   **Start Command:**
   ```
   gunicorn app:app
   ```

   **Environment Variables** (Click "Add Environment Variables"):
   ```
   FLASK_ENV=production
   SECRET_KEY=your-secret-key-123456789
   DEBUG=False
   DATABASE_URL=sqlite:///marine.db
   ```

   To generate SECRET_KEY, you can use: `secret-key-production-2026`

4. **Configure Persistent Disk** (IMPORTANT!)
   - Scroll down to "Disk"
   - Click "Add Disk"
   - **Mount Path:** `/var/data`
   - **Size:** 1 GB (free tier)

5. **Deploy!**
   - Click **"Create Web Service"**
   - Render starts deploying (takes 2-3 minutes)
   - You'll see deployment logs

### 5.2 Monitor Deployment

**In the Render Dashboard:**
- Watch logs scroll by
- You should see:
  ```
  ✓ Build successful
  ✓ Service deployed
  ```

- Your app URL appears: `https://marine-service-center-xxxxx.onrender.com`

---

## Step 6: Initialize Database on Render

After deployment succeeds:

1. **SSH into Render Server**
   - In Render Dashboard, go to your service
   - Click **"Shell"** (top right)
   - You get a terminal on the server

2. **Initialize Database**
   - In the shell, run:
   ```bash
   python -c "from app import init_db; init_db()"
   ```

   - You should see:
   ```
   ✅ Database tables initialized successfully
   ```

3. **Test Default User**
   - In shell, verify a user exists:
   ```bash
   python -c "from app import db, User; print(User.query.first())"
   ```

---

## Step 7: Test Live Deployment

1. **Visit Your Live App**
   - Copy your Render URL: `https://marine-service-center-xxxxx.onrender.com`
   - Visit it in your browser
   - You should see the login page

2. **Login with Test Account**
   - Email: `port_engineer@marine.com`
   - Password: `Admin@2025`
   - You're logged in! ✅

3. **Test Key Features**
   - ✅ Inventory Management
   - ✅ Create Report
   - ✅ Messaging
   - ✅ Theme Switching (Settings → Color Theme)
   - ✅ Upload Files

---

## Step 8: Continuous Development

### Keep Developing Locally

```bash
# Local development
python app.py

# Make changes to files
# Test locally
```

### Push Changes to Production

```bash
# When ready to deploy
git add .
git commit -m "Feature: description of changes"
git push origin main
```

**Render automatically redeploys!** ✅

---

## 📊 Render Dashboard Features

**Monitor your app:**
- **Logs:** See application errors and activity
- **Metrics:** CPU, memory, requests per minute
- **Environment:** View and edit environment variables
- **Disk:** Check database file size
- **Deployments:** See deployment history

**To access:**
1. Go to render.com
2. Click your service name
3. Explore the tabs

---

## 🆘 Troubleshooting

### App Shows Error 502 / 500
1. Go to Render Dashboard
2. Click "Logs" tab
3. Look for error message
4. Common fixes:
   ```
   # SSH to Render shell
   pip install -r requirements.txt
   python -c "from app import init_db; init_db()"
   ```

### Database Error
```bash
# SSH to Render shell
python -c "from app import init_db; init_db()"
```

### Changes Not Updating
```bash
# Make sure you pushed to GitHub
git push origin main

# Check Render dashboard - should auto-redeploy
# If not, manually trigger:
# Go to Render Dashboard → Service → Redeploy
```

### Can't Login
- Check email/password spelling
- Try: `port_engineer@marine.com` / `Admin@2025`
- If database is empty, SSH and run init script

---

## ✅ Checklist

- [ ] Git installed on computer
- [ ] Git repository initialized locally
- [ ] Code committed to Git
- [ ] GitHub account created (chriskaijage02@gmail.com)
- [ ] Repository created on GitHub
- [ ] Code pushed to GitHub
- [ ] Render account created
- [ ] Web service created on Render
- [ ] Build command: `pip install -r requirements.txt`
- [ ] Start command: `gunicorn app:app`
- [ ] Environment variables added
- [ ] Persistent disk configured
- [ ] Deployment successful
- [ ] Database initialized
- [ ] Can login to live app
- [ ] All features tested

---

## 🎯 URLs

**Your Resources:**
- GitHub Repository: `https://github.com/YOUR_USERNAME/marine-service-center`
- Live App: `https://marine-service-center-xxxxx.onrender.com`
- Render Dashboard: `https://dashboard.render.com`
- GitHub Account: `https://github.com/login`

---

## 📞 Support

If you get stuck:
1. Check DEPLOYMENT_GUIDE.md in your project
2. See "Troubleshooting" section above
3. Check Render logs for error messages
4. Visit render.com support (free tier has community chat)

---

## ⚡ Quick Reference Commands

```bash
# Initial setup
git config user.name "Marine Service Center"
git config user.email "chriskaijage02@gmail.com"
git init
git add .
git commit -m "Initial commit"

# Push to GitHub (AFTER creating repo on GitHub)
git remote add origin https://github.com/YOUR_USERNAME/marine-service-center.git
git branch -m main
git push -u origin main

# After pushing, Render auto-detects and deploys!
```

---

**Once all steps are complete, you have:**
- ✅ Code on GitHub (versioned, backed up)
- ✅ App running on Render (free server, always online)
- ✅ Database persists (won't lose data)
- ✅ Auto-deployment (push code → instant update)
- ✅ Development continues locally (keep building features)

🚀 **You're live in production!**
