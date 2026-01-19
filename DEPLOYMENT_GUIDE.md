# 🚀 PRODUCTION DEPLOYMENT GUIDE
## Marine Service Center - Deploy & Maintain

**Date:** January 19, 2026  
**Framework:** Flask + SQLite  
**Target:** Free Production Server (Render, Heroku, or Railway)

---

## 📋 TABLE OF CONTENTS

1. [Quick Start](#quick-start)
2. [Free Server Options](#free-server-options)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Deployment Steps](#deployment-steps)
5. [Post-Deployment](#post-deployment)
6. [Development & Maintenance](#development--maintenance)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 QUICK START

### **Recommended Platform: Render.com** (Best free tier)

**Why Render?**
- ✅ Free tier: 750 hours/month
- ✅ Always-on option available
- ✅ Git integration (auto-deploy)
- ✅ Persistent disk for database
- ✅ Easy environment variables
- ✅ Good for development + production

---

## 🔍 FREE SERVER OPTIONS COMPARISON

| Platform | Free Tier | Database | Deploy | Best For |
|----------|-----------|----------|--------|----------|
| **Render** | 750h/month | PostgreSQL free | Git push | ⭐ RECOMMENDED |
| **Railway** | $5/month credit | PostgreSQL | Git push | Production-ready |
| **Heroku** | Paid only | PostgreSQL | Git push | Was free, not anymore |
| **Replit** | With limits | SQLite | Direct edit | Quick testing |
| **Fly.io** | 3 shared CPU | PostgreSQL | Git + CLI | Advanced |

---

## ✅ PRE-DEPLOYMENT CHECKLIST

- [ ] Git repository created and initialized
- [ ] `.gitignore` file configured
- [ ] `requirements.txt` up-to-date
- [ ] `Procfile` created
- [ ] Database migrations prepared
- [ ] Environment variables documented
- [ ] `SECRET_KEY` configured
- [ ] HTTPS enabled
- [ ] Static files configured
- [ ] Database backup strategy planned

---

## 📦 DEPLOYMENT STEPS

### **Step 1: Prepare Your Project**

#### 1.1 Create/Update `.gitignore`

```
# Virtual environments
venv/
myenv/
env/
*.egg-info/
__pycache__/
*.pyc
.Python

# Database
*.db
*.sqlite
*.sqlite3
database/

# Environment variables
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Uploads (optional - use cloud storage in production)
uploads/
*.log

# Dependencies
node_modules/
```

#### 1.2 Update `requirements.txt`

```
# Core
flask==3.0.0
werkzeug==3.0.1
flask-login==0.6.3
gunicorn==21.2.0

# Database
flask-sqlalchemy==3.1.1

# Utilities
python-dotenv==1.0.0
pillow==10.1.0
reportlab==4.0.4
pandas==2.1.4
openpyxl==3.1.2
flask-limiter==3.5.1
```

#### 1.3 Create `Procfile`

```
web: gunicorn app:app
```

#### 1.4 Create `runtime.txt` (Specify Python version)

```
python-3.11.5
```

#### 1.5 Create `.env.example`

```
# Application
FLASK_ENV=production
FLASK_APP=app.py
SECRET_KEY=your-secret-key-here
DEBUG=False

# Database
DATABASE_URL=sqlite:///marine.db
# Or for production use PostgreSQL:
# DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Server
HOST=0.0.0.0
PORT=5000

# Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Strict

# Optional: Cloud Storage
# AWS_S3_BUCKET=your-bucket
# AWS_ACCESS_KEY_ID=your-key
# AWS_SECRET_ACCESS_KEY=your-secret
```

---

### **Step 2: Update app.py for Production**

**Key changes needed in app.py:**

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-me')
app.config['DATABASE'] = os.environ.get('DATABASE_URL', 'marine.db')
app.config['DEBUG'] = os.environ.get('FLASK_ENV') == 'development'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'True') == 'True'
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')

# Production Server Port
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
```

---

### **Step 3: Initialize Git Repository**

```bash
# Initialize git
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Marine Service Center System"

# Add remote (for your platform)
git remote add origin https://github.com/YOUR_USERNAME/marine-service-center.git

# Push to repository
git push -u origin main
```

---

### **Step 4: Deploy on Render.com** ⭐ RECOMMENDED

#### 4.1 Create Render Account
- Go to [render.com](https://render.com)
- Sign up with GitHub

#### 4.2 Create New Web Service
1. Dashboard → New → Web Service
2. Connect GitHub repository
3. Configure:
   - **Name:** marine-service-center
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Plan:** Free
4. Click "Create Web Service"

#### 4.3 Add Environment Variables
In Render Dashboard:
1. Service → Environment
2. Add Variables:
   ```
   FLASK_ENV=production
   SECRET_KEY=<generate-random-key>
   DATABASE_URL=sqlite:///marine.db
   DEBUG=False
   ```

#### 4.4 Enable Persistent Disk (for SQLite)
1. Service → Disk
2. Mount Path: `/var/data`
3. Size: 1 GB (free tier)
4. Update `app.py`:
   ```python
   app.config['DATABASE'] = '/var/data/marine.db'
   ```

#### 4.5 Access Your App
- URL: `https://marine-service-center-xxxxx.onrender.com`
- Your app is now live!

---

### **Step 5: Deploy on Railway.app** (Alternative)

#### 5.1 Create Railway Account
- Go to [railway.app](https://railway.app)
- Login with GitHub

#### 5.2 Create Project
1. Dashboard → New Project
2. Deploy from GitHub repo
3. Select your repository

#### 5.3 Configure Variables
1. Project Settings → Variables
2. Add same variables as Render

#### 5.4 Deploy
- Push to GitHub → Auto-deploys on Railway
- Access via Railway dashboard URL

---

## 🔧 POST-DEPLOYMENT

### **1. Initialize Database on Server**

SSH into server and run:
```bash
cd /app
python -c "from app import init_db; init_db()"
```

Or create `init_db.py`:
```python
from app import app, init_db
with app.app_context():
    init_db()
```

Then SSH:
```bash
python init_db.py
```

### **2. Test Live Application**

- Visit: `https://your-domain.onrender.com`
- Login with test credentials
- Test each major feature:
  - ✅ User authentication
  - ✅ Inventory management
  - ✅ Report creation
  - ✅ File uploads
  - ✅ Theme switching
  - ✅ Messaging system

### **3. Setup Monitoring**

On Render:
1. Service → Metrics → Enable
2. Monitor: CPU, RAM, requests
3. Set up alerts for errors

### **4. Backup Database**

Render provides automatic backups, but also:
```bash
# Download backup
curl https://your-app.onrender.com/api/backup -o backup.db
```

---

## 👨‍💻 DEVELOPMENT & MAINTENANCE

### **While in Production, Develop Locally**

```bash
# Local development setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env for local development
cp .env.example .env

# Edit .env with local settings
# FLASK_ENV=development
# DEBUG=True
# DATABASE_URL=sqlite:///marine.db

# Run locally
python app.py
```

### **Git Workflow for Updates**

```bash
# 1. Make changes locally
git add .
git commit -m "Feature: Add new button to inventory"

# 2. Test locally
python app.py
# Test the feature...

# 3. Push to production
git push origin main

# 4. Render auto-deploys!
# Watch deployment in Render dashboard
```

### **Database Migrations in Production**

If you modify database schema:

```python
# Create migration script: migrate.py
from app import app, db

def migrate():
    with app.app_context():
        # Add your migration code
        db.session.commit()

if __name__ == '__main__':
    migrate()
```

Deploy the script, then:
```bash
# Run migration on production server
python migrate.py
```

### **Rollback to Previous Version**

```bash
# View commits
git log --oneline

# Rollback to specific commit
git revert <commit-hash>

# Or reset (careful!)
git reset --hard <commit-hash>

# Push to production
git push origin main
```

---

## 🔐 SECURITY CHECKLIST

### **Before Going Live**

- [ ] Change SECRET_KEY to random 32+ character string
- [ ] Set DEBUG=False
- [ ] Enable SESSION_COOKIE_SECURE=True
- [ ] Use HTTPS only
- [ ] Update CORS settings
- [ ] Rate limiting enabled
- [ ] Input validation on all forms
- [ ] SQL injection protection (use parameterized queries)
- [ ] CSRF protection enabled
- [ ] Regular security updates

### **Generate Secure SECRET_KEY**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy output and set in `.env`:
```
SECRET_KEY=your-generated-key-here
```

---

## 📊 MONITORING & LOGS

### **Render Dashboard**

1. **Logs**: Service → Logs
   - View real-time logs
   - Search for errors
   - Helpful for debugging

2. **Metrics**: Service → Metrics
   - CPU usage
   - Memory usage
   - Request count
   - Response time

3. **Alerts**: Setting → Alerts
   - Email notifications
   - Critical errors
   - Deployment failures

### **Local Log Analysis**

```bash
# Download logs from production
# Via Render dashboard → Logs → Download

# Analyze locally
grep "ERROR" logs.txt
grep "WARNING" logs.txt
```

---

## 🆘 TROUBLESHOOTING

### **Issue: App crashes on deploy**

**Solution:**
1. Check logs: Render Dashboard → Logs
2. Look for missing dependencies
3. Update `requirements.txt`
4. Test locally: `pip install -r requirements.txt`
5. Commit and push: `git push origin main`

### **Issue: Database not persisting**

**Solution:**
- Render/Railway automatically handle SQLite persistence
- For added safety, add persistent disk
- Or migrate to PostgreSQL (free on Railway)

### **Issue: Uploads disappear after deploy**

**Solution:**
- Uploads folder is temporary on ephemeral filesystems
- Use Render Persistent Disk:
  1. Settings → Disk
  2. Mount `/app/uploads`
  3. Size: 1 GB
- Or use cloud storage (S3, etc.)

### **Issue: Slow performance**

**Solution:**
- Check Metrics for CPU/RAM spikes
- Optimize database queries
- Enable caching
- Upgrade to paid tier if needed

### **Issue: Can't login on production**

**Solution:**
1. Check database was initialized
2. Verify users table exists
3. Test with simple SQL:
   ```bash
   sqlite3 /var/data/marine.db "SELECT * FROM users LIMIT 1;"
   ```

---

## 📱 ACCESSING FROM MOBILE

Your app is accessible from anywhere:
- **URL:** `https://marine-service-center-xxxxx.onrender.com`
- **Mobile:** Open in browser or add to home screen
- **Progressive Web App:** Already configured in base.html

---

## 🔄 CONTINUOUS DEPLOYMENT WORKFLOW

```
Local Dev
   ↓
git commit
   ↓
git push origin main
   ↓
GitHub receives update
   ↓
Render/Railway auto-deploys
   ↓
Build & test
   ↓
Live on production
   ↓
Monitor metrics & logs
   ↓
If error: git revert & push
```

---

## 💡 PRO TIPS

1. **Use environment variables for everything**
   - No secrets in code
   - Easy to change per environment

2. **Keep main branch production-ready**
   - Always test locally first
   - Use feature branches for development

3. **Monitor first week closely**
   - Check logs daily
   - Watch for errors/exceptions
   - Test all user scenarios

4. **Backup regularly**
   - Download database weekly
   - Store in safe location
   - Test restore procedures

5. **Update dependencies**
   - Run `pip install --upgrade -r requirements.txt`
   - Test updates locally
   - Deploy when ready

---

## 📞 SUPPORT RESOURCES

- **Render Docs:** [render.com/docs](https://render.com/docs)
- **Flask Docs:** [flask.palletsprojects.com](https://flask.palletsprojects.com)
- **Gunicorn Docs:** [gunicorn.org](https://gunicorn.org)
- **Git Guide:** [git-scm.com](https://git-scm.com)

---

## ✅ DEPLOYMENT COMPLETE CHECKLIST

- [ ] GitHub repository created and pushed
- [ ] Render/Railway account created
- [ ] Web service deployed
- [ ] Environment variables configured
- [ ] Database initialized on server
- [ ] Application tested on live URL
- [ ] HTTPS working
- [ ] Monitoring enabled
- [ ] Backups configured
- [ ] Team members have access

---

**Your Marine Service Center is now in production! 🎉**

Continue developing locally and push updates to GitHub for instant deployment.

