# 🚢 Marine Service Center - Production Ready

> **International Marine Service Management System**  
> Production-ready Flask application with authentication, inventory management, reporting, and more.

## ✨ Features

- 🔐 **Role-Based Authentication** - Captain, Chief Engineer, Port Engineer, Harbour Master, Quality Officer
- 📦 **Inventory Management** - Track marine equipment, parts, and supplies
- 📋 **International Reports** - Bilge, Fuel, Sewage, Logbook, Emission reports
- 🆘 **Emergency Request System** - Critical incident management
- 🛠️ **Maintenance Tracking** - Ship maintenance requests
- 📚 **Machinery Manuals** - Document and file management
- 💬 **Messaging System** - Internal communication
- 🎨 **Theme System** - 7 color themes with real-time switching
- 📊 **Analytics & Reports** - Comprehensive reporting
- 📱 **Responsive Design** - Mobile, tablet, desktop support

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Python 3.11+
- Git
- Free hosting account (Render, Railway, or Heroku)

### Local Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/marine-service-center.git
cd marine-service-center

# Setup (Windows)
setup_production.bat

# Setup (Linux/Mac)
bash setup_production.sh

# Edit configuration
# Windows: notepad .env
# Linux/Mac: nano .env

# Initialize database
python -c "from app import init_db; init_db()"

# Run locally
python app.py
```

Visit: http://localhost:5000

### Deploy to Production (Free)

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions.

**Quick Deploy to Render (2 minutes):**

1. Push code to GitHub
2. Go to [render.com](https://render.com)
3. Create New → Web Service
4. Connect GitHub repo
5. Deploy!

## 📖 Documentation

- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Complete deployment instructions
- [THEME_SYSTEM.md](THEME_SYSTEM.md) - Theme system documentation
- [THEME_IMPLEMENTATION.md](THEME_IMPLEMENTATION.md) - Theme implementation guide
- [BUTTON_INSPECTION_COMPLETE.md](BUTTON_INSPECTION_COMPLETE.md) - Button functionality verification

## 🔧 Configuration

Edit `.env` file:

```env
FLASK_ENV=production
SECRET_KEY=your-random-secret-key
DEBUG=False
DATABASE_URL=sqlite:///marine.db
```

For production, generate a secure key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 📁 Project Structure

```
├── app.py                    # Main application
├── requirements.txt          # Python dependencies
├── Procfile                  # Production server config
├── runtime.txt              # Python version
├── .env.example             # Environment template
├── .gitignore               # Git ignore file
├── static/                  # CSS, JS, images
│   ├── css/style.css       # Main styles
│   ├── js/main.js          # Main JavaScript
│   ├── js/theme-system.js  # Theme system
│   └── images/
├── templates/               # HTML templates
│   ├── base.html           # Base template
│   ├── inventory.html      # Inventory management
│   ├── evaluate.html       # Evaluation forms
│   ├── bilge_report.html   # Reports
│   └── ... (20+ templates)
├── uploads/                # User uploads
│   ├── documents/
│   ├── signatures/
│   ├── profile_pics/
│   └── reports/
└── marine.db               # SQLite database
```

## 🔐 Security

- Passwords hashed with Werkzeug
- CSRF protection enabled
- SQL injection protection
- Rate limiting on APIs
- Secure session cookies
- HTTPS in production
- Input validation

## 👥 User Roles

| Role | Access |
|------|--------|
| **Captain** | Create reports, view vessel data |
| **Chief Engineer** | Maintenance requests, equipment |
| **Port Engineer** | Inventory, maintenance approval |
| **Harbour Master** | All features, administration |
| **Quality Officer** | Evaluate crew, generate reports |

## 📊 Database

- **Type:** SQLite (development) / PostgreSQL (production)
- **Tables:** Users, Inventory, Reports, Requests, Messages
- **Backup:** Automatic on Render/Railway

## 🌐 Deployment Platforms

- ⭐ **Render** - Recommended (750 free hours/month)
- **Railway** - Good alternative ($5 free credit)
- **Heroku** - Paid only
- **Fly.io** - Advanced option

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for each platform.

## 📱 Responsive Design

- Mobile: < 576px
- Tablet: 768-992px
- Desktop: > 1200px

All features work seamlessly on all devices.

## 🎨 Theme System

7 built-in themes:
- Purple (Default)
- Blue Ocean
- Teal Marine
- Emerald
- Indigo
- Rose
- Amber

Switch themes in navbar → Settings → Color Themes

## 💬 Support

- Check [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for deployment issues
- Review documentation files
- Check application logs via Render/Railway dashboard

## 📝 License

Private use. Contact for commercial licensing.

## 🎯 Roadmap

- [ ] Mobile app (React Native)
- [ ] Advanced analytics
- [ ] Machine learning predictions
- [ ] API v2 for integrations
- [ ] Multi-vessel support
- [ ] Blockchain audit trail

## 👨‍💻 Development

### Local Development
```bash
# Activate virtual environment
source venv/bin/activate

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with debug
export FLASK_ENV=development
python app.py
```

### Making Changes
```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes
# Test locally
# Commit and push
git push origin feature/your-feature

# Create pull request on GitHub
# After review, merge to main
# Auto-deploys to production!
```

## ✅ Status

- **Version:** 2.0
- **Status:** Production Ready ✅
- **Last Updated:** January 19, 2026
- **Python:** 3.11.5
- **Flask:** 3.0.0

---

**Ready to deploy? Start with [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** 🚀
