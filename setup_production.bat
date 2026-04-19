@echo off
REM Quick Deployment Setup Script for Windows
REM Usage: setup_production.bat

echo.
echo 🚀 VesselOS - Production Setup
echo ===========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.11+
    exit /b 1
)

echo ✓ Python found
python --version

REM Create virtual environment
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo 📥 Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo 📥 Installing dependencies...
pip install -r requirements.txt

REM Check for .env
if not exist ".env" (
    echo ⚙️  Creating .env file from template...
    copy .env.example .env
    echo ⚠️  Please edit .env with your configuration
    echo    Run: notepad .env
)

REM Install gunicorn if needed
pip show gunicorn >nul 2>&1
if errorlevel 1 (
    echo 📥 Installing gunicorn...
    pip install gunicorn
)

echo.
echo ✅ Setup complete!
echo.
echo Next steps:
echo 1. Edit .env file with your settings
echo 2. Initialize database (if needed)
echo 3. Run locally: python app.py
echo 4. For production: gunicorn app:app
echo 5. Push to GitHub and deploy
echo.
pause
