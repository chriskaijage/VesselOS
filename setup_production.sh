#!/bin/bash
# Quick Deployment Setup Script for VesselOS
# Usage: bash setup_production.sh

set -e

echo "🚀 VesselOS - Production Setup"
echo "==========================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade pip
echo "📥 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your configuration"
    echo "   Run: nano .env"
fi

# Check if gunicorn is installed
if ! pip show gunicorn > /dev/null; then
    echo "📥 Installing gunicorn for production..."
    pip install gunicorn
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your settings:"
echo "   nano .env"
echo ""
echo "2. Initialize database (if needed):"
echo "   python -c \"from app import init_db; init_db()\""
echo ""
echo "3. Run locally to test:"
echo "   python app.py"
echo ""
echo "4. For production with gunicorn:"
echo "   gunicorn app:app"
echo ""
echo "5. Initialize git and push to GitHub:"
echo "   git init"
echo "   git add ."
echo "   git commit -m 'Initial commit'"
echo "   git push origin main"
echo ""
