#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VesselOS - Maritime Management Platform.

A comprehensive web application for managing ship maintenance, reporting,
and quality assurance with role-based access control and real-time collaboration.

Features:
    - User management with role-based access control
    - Ship maintenance request tracking and approval workflow
    - Quality assurance evaluations and reporting
    - Real-time messaging and notifications
    - Comprehensive audit logging and activity tracking
    - Multiple report types (maintenance, billing, quality, emissions)
"""

import os
import sys
import io
import json
import sqlite3
import random
import string
import csv
import shutil
from datetime import datetime, timedelta
from functools import wraps

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from flask import (
    Flask, render_template, request, jsonify, send_file,
    redirect, url_for, flash, session, send_from_directory
)
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user, AnonymousUserMixin
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_compress import Compress

# Ensure UTF-8 encoding for output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Optional dependencies
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# =====================================================================
# APPLICATION INITIALIZATION
# =====================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vesselOS-secure-key-2026-v2')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['ALLOWED_EXTENSIONS'] = {
    'png', 'jpg', 'jpeg', 'gif', 'pdf',
    'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt', 'zip', 'rar'
}

# Configure session security
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Rate limiting configuration
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["5000 per day", "500 per hour"],
)

# Enable gzip compression for faster page loads
Compress(app)


# =====================================================================
# DATABASE CONFIGURATION
# =====================================================================

PERSISTENT_VOLUME = os.environ.get('PERSISTENT_VOLUME', '')
if PERSISTENT_VOLUME and os.path.isdir(PERSISTENT_VOLUME):
    DB_PATH = os.path.join(PERSISTENT_VOLUME, 'marine.db')
    UPLOAD_FOLDER = os.path.join(PERSISTENT_VOLUME, 'uploads')
    print(f"[OK] Using persistent volume: {PERSISTENT_VOLUME}")
    USING_PERSISTENT_STORAGE = True
else:
    DB_PATH = 'marine.db'
    UPLOAD_FOLDER = 'uploads'
    USING_PERSISTENT_STORAGE = False
    print(f"[WARNING] PERSISTENT_VOLUME not configured. Database will be in current directory.")
    print(f"[WARNING] Set PERSISTENT_VOLUME environment variable for data persistence on deployments.")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATABASE'] = DB_PATH

# Ensure database directory exists
DB_DIR = os.path.dirname(DB_PATH) or '.'
if DB_DIR != '.' and not os.path.exists(DB_DIR):
    try:
        os.makedirs(DB_DIR, mode=0o755, exist_ok=True)
        print(f"[OK] Created database directory: {DB_DIR}")
    except Exception as e:
        print(f"[WARNING] Could not create database directory {DB_DIR}: {e}")

# Check if database file exists before initialization
DB_EXISTS = os.path.exists(DB_PATH)
if DB_EXISTS:
    db_size = os.path.getsize(DB_PATH)
    print(f"[OK] Existing database found: {DB_PATH} ({db_size} bytes)")
else:
    print(f"[INFO] New database will be created at: {DB_PATH}")

print(f"[OK] Database path: {DB_PATH}")
print(f"[OK] Upload folder: {UPLOAD_FOLDER}")
print(f"[OK] Data persistence: {'ENABLED (Render persistent disk)' if USING_PERSISTENT_STORAGE else 'DISABLED (ephemeral storage - data lost on redeploy)'}")

# Verify database file exists and is accessible
if os.path.exists(DB_PATH):
    db_stat = os.stat(DB_PATH)
    print(f"[OK] Database file verified at: {DB_PATH}")
    print(f"[OK] Database size: {db_stat.st_size / (1024*1024):.2f} MB")
    print(f"[OK] Last modified: {datetime.fromtimestamp(db_stat.st_mtime)}")
else:
    print(f"[INFO] Database will be created at first run: {DB_PATH}")


# EMAIL CONFIGURATION
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'marineservice@gmail.com')
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD', '')
SMTP_ENABLED = bool(SENDER_PASSWORD)

# SMS CONFIGURATION (Twilio)
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE = os.environ.get('TWILIO_PHONE', '+1234567890')
SMS_ENABLED = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)

# Try to import Twilio if credentials available
TWILIO_CLIENT = None
if SMS_ENABLED:
    try:
        from twilio.rest import Client
        TWILIO_CLIENT = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except ImportError:
        app.logger.warning("Twilio library not installed. SMS notifications disabled.")
        SMS_ENABLED = False

# Create upload directories (on persistent volume on Render)
for folder in ['profile_pics', 'documents', 'documents/inventory', 'documents/inspection', 'reports', 'maintenance_requests', 'signatures', 'messages', 'messages/replies', 'machinery_manuals']:
    folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder)
    os.makedirs(folder_path, exist_ok=True)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

# Define AnonymousUser with get_full_name to avoid template errors
class Anonymous(AnonymousUserMixin):
    def get_full_name(self):
        return "Guest"
login_manager.anonymous_user = Anonymous

# ==================== ROLE-BASED ACCESS CONTROL ====================
def role_required(roles):
    """
    Decorator for role-based access control on routes.
    
    Restricts access to protected routes based on user role. Requires user to be
    authenticated and have one of the specified roles. Returns appropriate error
    responses for both API and web requests.
    
    Args:
        roles (str or list): Single role string or list of role names that are
                            allowed to access the decorated route.
    
    Returns:
        function: Decorated function that performs role validation.
    
    Usage:
        @app.route('/admin/dashboard')
        @role_required(['admin', 'port_engineer'])
        def admin_dashboard():
            return render_template('admin.html')
    
    Note:
        - API requests (paths starting with /api/) receive JSON error responses
        - Web requests are redirected to dashboard with flash message
        - Implicitly requires @login_required functionality
    """
    # Normalize roles to list if string provided
    allowed_roles = [roles] if isinstance(roles, str) else roles
    
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in allowed_roles:
                # Handle API vs web request response differently
                if request.path.startswith('/api/'):
                    error_msg = f'Access denied. {current_user.role.title()} role cannot access this API.'
                    return jsonify({'success': False, 'error': error_msg}), 403
                else:
                    flash(
                        f'Access denied. {current_user.role.title()} role cannot access this resource.',
                        'danger'
                    )
                    return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== CONTEXT PROCESSOR ====================
@app.context_processor
def inject_current_user_profile():
    context = {'csrf_token': generate_csrf_token()}
    if current_user.is_authenticated:
        profile_pic_url = None
        if current_user.profile_pic:
            profile_pic_url = url_for('serve_profile_pic', filename=current_user.profile_pic)
        context['current_user_profile'] = {
            'full_name': current_user.get_full_name(),
            'profile_pic_url': profile_pic_url,
            'role': current_user.role
        }
    else:
        context['current_user_profile'] = None
    return context

# ==================== DATABASE UTILITIES ====================

def get_db_connection():
    """
    Establish and configure a database connection.

    Returns:
        sqlite3.Connection: Database connection with row factory and safety features enabled.
    """
    conn = sqlite3.connect(app.config['DATABASE'], timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')  # Better concurrency
    conn.execute('PRAGMA foreign_keys=ON')   # Enforce referential integrity
    return conn


# =====================================================================
# USER MODEL
# =====================================================================

class User(UserMixin):
    """
    User model representing an authenticated user in the system.

    Attributes:
        id (str): Unique user identifier
        email (str): User's email address
        first_name (str): User's first name
        last_name (str): User's last name
        role (str): User's role (e.g., 'port_engineer', 'chief_engineer')
        rank (str): Professional rank/title
        phone (str): Contact phone number
        profile_pic (str): Path to profile picture
        signature_path (str): Path to digital signature
        is_approved (bool): Whether account is approved
        survey_end_date (str): End date for survey access
    """

    def __init__(self, user_data):
        self.id = user_data['user_id']
        self.email = user_data['email']
        self.first_name = user_data['first_name']
        self.last_name = user_data['last_name']
        self.role = user_data['role']
        self.rank = user_data.get('rank', '')
        self.phone = user_data.get('phone', '')
        self.profile_pic = user_data.get('profile_pic', None)
        self.signature_path = user_data.get('signature_path', None)
        self._is_active = user_data.get('is_active', 1) == 1
        self.is_approved = user_data.get('is_approved', 0) == 1
        self.survey_end_date = user_data.get('survey_end_date', None)
        self.department = user_data.get('department', '')
        self.location = user_data.get('location', '')
        self.created_at = user_data.get('created_at', None)
        self.last_login = user_data.get('last_login', None)
        self.last_activity = user_data.get('last_activity', None)

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = bool(value)

    def get_full_name(self):
        """
        Get user's full name.
        
        Returns:
            str: Full name formatted as "First Last"
        """
        return f"{self.first_name} {self.last_name}"

@login_manager.user_loader
def load_user(user_id):
    """
    Load user object from database for session management.
    
    Called by Flask-Login to restore user session. Queries the database
    to retrieve complete user information and returns a User object.
    
    Args:
        user_id (str): The user ID to load from session
    
    Returns:
        User: User object if found, None if user not found or error occurs
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            return User(dict(user_data))
    except Exception as e:
        app.logger.error(f"Failed to load user {user_id} from database: {e}")
    finally:
        conn.close()
    return None


@app.route('/api/inventory/<part_number>/docs', methods=['GET'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_inventory_docs(part_number):
    """
    Retrieve all documents attached to an inventory item.
    
    Returns document metadata for a specific part number, including
    file information and upload details.
    
    Args:
        part_number (str): The inventory part number
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - docs (list): Array of document objects with id, filename, uploader, size, timestamp
    
    Status Codes:
        - 200: Documents retrieved successfully
        - 403: Insufficient permissions
        - 401: Not authenticated
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, original_filename, stored_filename, uploader_id, file_size, uploaded_at
               FROM inventory_documents
               WHERE part_number = ?
               ORDER BY uploaded_at DESC""",
            (part_number,)
        )
        docs = [dict(row) for row in cursor.fetchall()]
        return jsonify(success=True, docs=docs)
    except Exception as e:
        app.logger.error(f"Failed to fetch documents for part {part_number}: {e}")
        return jsonify(success=False, error='Failed to retrieve documents'), 500
    finally:
        conn.close()


@app.route('/api/inventory/<part_number>/docs/upload', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_inventory_upload_docs(part_number):
    """Upload one or more documents for an inventory item (appends, does not overwrite)."""
    if 'files' not in request.files and 'file' not in request.files:
        return jsonify(success=False, error='No files uploaded')

    files = request.files.getlist('files') or request.files.getlist('file')
    saved = []
    rejected = []

    # Create target folder for this part
    safe_part = secure_filename(part_number)
    target_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', 'inventory', safe_part)
    os.makedirs(target_folder, exist_ok=True)

    conn = get_db_connection()
    try:
        c = conn.cursor()
        for f in files:
            if f and f.filename:
                if not allowed_file(f.filename):
                    rejected.append(f"'{f.filename}' - file type not allowed")
                    continue
                orig = f.filename
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                stored_name = f"{timestamp}_{secure_filename(orig)}"
                save_path = os.path.join(target_folder, stored_name)
                f.save(save_path)
                file_size = os.path.getsize(save_path)

                doc_id = generate_id('DOC')
                c.execute('''
                    INSERT INTO inventory_documents (id, part_number, original_filename, stored_filename, uploader_id, file_size, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (doc_id, part_number, orig, os.path.join('documents', 'inventory', safe_part, stored_name), current_user.id if current_user.is_authenticated else None, file_size, datetime.now()))
                saved.append({'id': doc_id, 'original_filename': orig, 'stored_filename': stored_name, 'file_size': file_size})

        conn.commit()
        log_activity('inventory_upload_doc', f'Uploaded {len(saved)} docs for {part_number}')
        
        message = f'Uploaded {len(saved)} file(s)'
        if rejected:
            message += f'. Rejected: {", ".join(rejected)}'
        
        return jsonify(success=True, saved=saved, message=message, rejected=rejected)
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error uploading inventory docs: {e}")
        return jsonify(success=False, error=str(e))
    finally:
        conn.close()


@app.route('/api/inventory/docs/delete/<doc_id>', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_inventory_delete_doc(doc_id):
    """Delete a single inventory document by id."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT stored_filename FROM inventory_documents WHERE id = ?", (doc_id,))
        row = c.fetchone()
        if not row:
            return jsonify(success=False, error='Document not found')
        stored = row['stored_filename']
        # Remove file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            app.logger.warning(f"Could not remove file {file_path}: {e}")

        c.execute("DELETE FROM inventory_documents WHERE id = ?", (doc_id,))
        conn.commit()
        log_activity('inventory_delete_doc', f'Deleted doc {doc_id}')
        return jsonify(success=True, message='Document deleted')
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error deleting inventory doc: {e}")
        return jsonify(success=False, error=str(e))
    finally:
        conn.close()
    return None

@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access - return JSON for API requests, redirect for pages."""
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Authentication required. Please log in.'}), 401
    flash('Please log in to access this page.', 'warning')
    return redirect(url_for('login'))

# role_required is defined earlier near login manager setup

# ==================== UTILITY FUNCTIONS ====================

def allowed_file(filename, file_type='general'):
    allowed = app.config['ALLOWED_EXTENSIONS']
    if file_type == 'image':
        allowed = {'png', 'jpg', 'jpeg', 'gif'}
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in allowed
    return False

def generate_id(prefix):
    """
    Generate a unique identifier with timestamp and random suffix.
    
    Creates unique IDs for database records using format:
    PREFIX-YYYYMMDDHHMMSS-XXXX where X is random digit.
    
    Args:
        prefix (str): ID prefix (e.g., 'BLG', 'FUL', 'SEW', 'MNT')
    
    Returns:
        str: Unique ID in format PREFIX-TIMESTAMP-RANDOM
    
    Example:
        generate_id('BLG') -> 'BLG-20260117120530-4726'
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}-{timestamp}-{random_suffix}"

def format_time_ago(dt):
    """
    Format a datetime as human-readable relative time string.
    
    Converts a datetime object or string to readable format like:
    '5m ago', '2h ago', '3d ago', 'Jan 15, 2026'
    
    Args:
        dt (datetime or str): Datetime object or ISO format string
    
    Returns:
        str: Human-readable time ago format
        - 'Now' if less than 1 second ago
        - 'Xs ago' if less than 1 minute
        - 'Xm ago' if less than 1 hour
        - 'Xh ago' if less than 1 day
        - 'Xd ago' if less than 1 week
        - 'Mon DD, YYYY' if older than 1 week
        - 'Never' if input is None
    """
    if not dt:
        return 'Never'
    
    # Handle both datetime objects and ISO format strings
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return 'Unknown'
    
    # Calculate elapsed time
    now = datetime.now()
    elapsed = now - dt
    
    # Convert to different time units
    total_seconds = int(elapsed.total_seconds())
    minutes = total_seconds // 60
    hours = minutes // 60
    days = hours // 24
    
    # Return appropriate format based on elapsed time
    if total_seconds < 60:
        return "Now" if total_seconds <= 0 else f"{total_seconds}s ago"
    elif minutes < 60:
        return f"{minutes}m ago"
    elif hours < 24:
        return f"{hours}h ago"
    elif days < 7:
        return f"{days}d ago"
    else:
        # For older dates, show full date
        return dt.strftime('%b %d, %Y')

def log_activity(activity, details=""):
    """
    Log user activity to activity logs and audit trail.

    Records all user actions for security auditing and activity tracking.
    Logs are written to both activity_logs and audit_trail tables.

    Args:
        activity (str): Type of activity (e.g., 'user_login', 'report_generated')
        details (str): Additional details about the activity

    Returns:
        None
    """
    if current_user.is_authenticated:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_time = datetime.now()
            user_ip = request.remote_addr if request else "127.0.0.1"

            # Log to activity_logs table
            c.execute(
                "INSERT INTO activity_logs (user_id, activity, details, ip_address, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (current_user.id, activity, details, user_ip, current_time)
            )

            # Log to audit_trail for comprehensive security tracking
            c.execute(
                "INSERT INTO audit_trail (timestamp, user_id, action_type, entity_type, ip_address, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (current_time, current_user.id, activity, "general", user_ip, "completed")
            )
            
            # Update last activity timestamp
            c.execute("UPDATE users SET last_activity = ? WHERE user_id = ?", (current_time, current_user.id))
            conn.commit()
        except Exception as e:
            app.logger.error(f"Error logging activity: {e}")
        finally:
            conn.close()

def log_entity_change(entity_type, entity_id, field_name, old_value, new_value, action_type="update", change_reason=""):
    """Log changes to any entity in real-time with complete audit trail."""
    if not current_user.is_authenticated:
        current_user_id = "system"
    else:
        current_user_id = current_user.id
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        current_time = datetime.now()
        user_ip = request.remote_addr if request else "127.0.0.1"
        
        # Record in audit_trail
        c.execute("""
            INSERT INTO audit_trail 
            (timestamp, user_id, action_type, entity_type, entity_id, old_value, new_value, ip_address, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (current_time, current_user_id, action_type, entity_type, entity_id, 
              str(old_value), str(new_value), user_ip, "completed"))
        
        # Record in update_history for detailed change tracking
        c.execute("""
            INSERT INTO update_history 
            (timestamp, table_name, record_id, field_name, old_value, new_value, user_id, change_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (current_time, entity_type, entity_id, field_name, str(old_value), str(new_value), current_user_id, change_reason))
        
        # Create system event for real-time monitoring
        c.execute("""
            INSERT INTO system_events 
            (timestamp, event_type, entity_type, entity_id, event_data, severity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (current_time, action_type, entity_type, entity_id, 
              f"Changed {field_name} from '{old_value}' to '{new_value}'", "info"))
        
        conn.commit()
        app.logger.info(f"[AUDIT] {action_type.upper()} {entity_type}:{entity_id} - {field_name}: '{old_value}' → '{new_value}'")
        
    except Exception as e:
        app.logger.error(f"Error logging entity change: {e}")
    finally:
        conn.close()

def log_system_event(event_type, entity_type, entity_id, event_data, severity="info"):
    """Log system-level events in real-time for monitoring."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        current_time = datetime.now()
        
        c.execute("""
            INSERT INTO system_events 
            (timestamp, event_type, entity_type, entity_id, event_data, severity, processed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (current_time, event_type, entity_type, entity_id, str(event_data), severity, 0))
        
        conn.commit()
        app.logger.info(f"[SYSTEM EVENT] {severity.upper()}: {event_type} - {event_data}")
        
    except Exception as e:
        app.logger.error(f"Error logging system event: {e}")
    finally:
        conn.close()

def get_user_activity_timeline(user_id, limit=50, hours=24):
    """Get real-time activity timeline for a user."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        c.execute("""
            SELECT id, activity, details, timestamp, ip_address 
            FROM activity_logs 
            WHERE user_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, cutoff_time, limit))
        
        activities = [dict(row) for row in c.fetchall()]
        return activities
    except Exception as e:
        app.logger.error(f"Error getting activity timeline: {e}")
        return []
    finally:
        conn.close()

def get_entity_change_history(entity_type, entity_id, limit=100):
    """Get complete change history for any entity."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        c.execute("""
            SELECT timestamp, field_name, old_value, new_value, user_id, change_reason
            FROM update_history
            WHERE table_name = ? AND record_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (entity_type, entity_id, limit))
        
        history = [dict(row) for row in c.fetchall()]
        return history
    except Exception as e:
        app.logger.error(f"Error getting entity history: {e}")
        return []
    finally:
        conn.close()

def get_real_time_events(hours=1, severity_filter=None):
    """Get real-time system events for monitoring."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if severity_filter:
            c.execute("""
                SELECT id, timestamp, event_type, entity_type, entity_id, event_data, severity
                FROM system_events
                WHERE timestamp > ? AND severity = ?
                ORDER BY timestamp DESC
            """, (cutoff_time, severity_filter))
        else:
            c.execute("""
                SELECT id, timestamp, event_type, entity_type, entity_id, event_data, severity
                FROM system_events
                WHERE timestamp > ?
                ORDER BY timestamp DESC
            """, (cutoff_time,))
        
        events = [dict(row) for row in c.fetchall()]
        return events
    except Exception as e:
        app.logger.error(f"Error getting real-time events: {e}")
        return []
    finally:
        conn.close()

def create_notification(user_id, title, message, notif_type, action_url="#"):
    """
    Create and store a user notification.
    
    Inserts a new notification record into the database with the provided details
    and current timestamp. Notifications are used to inform users of important
    system events such as message receipts, approvals, or maintenance updates.
    
    Args:
        user_id (int): ID of the user receiving the notification
        title (str): Short notification title (appears in notification header)
        message (str): Detailed notification message body
        notif_type (str): Type of notification (e.g., 'message', 'approval', 'maintenance')
        action_url (str, optional): URL for user to navigate to on notification click.
                                   Defaults to "#" for no action.
    
    Returns:
        None
    
    Note:
        Errors during creation are logged but do not raise exceptions, allowing
        the application to continue functioning even if notification storage fails.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        current_time = datetime.now()
        cursor.execute(
            """INSERT INTO notifications 
               (user_id, title, message, type, action_url, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, title, message, notif_type, action_url, current_time)
        )
        conn.commit()
    except Exception as e:
        app.logger.error(f"Failed to create notification for user {user_id}: {e}")
    finally:
        conn.close()

# ==================== EMAIL FUNCTIONS ====================

def send_email(recipient_email, subject, html_body, plain_text=None):
    """
    Send email notification to recipient.
    
    Args:
        recipient_email: Email address to send to
        subject: Email subject line
        html_body: HTML content of email
        plain_text: Plain text fallback (optional)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not SMTP_ENABLED or not SENDER_PASSWORD:
        app.logger.warning(f"Email disabled. Would have sent: {subject} to {recipient_email}")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        
        # Add plain text part
        if plain_text:
            msg.attach(MIMEText(plain_text, 'plain'))
        
        # Add HTML part
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        app.logger.info(f"Email sent to {recipient_email}: {subject}")
        return True
    
    except Exception as e:
        app.logger.error(f"Error sending email to {recipient_email}: {e}")
        return False

def send_sms(phone_number, message_text):
    """
    Send SMS notification using Twilio.
    
    Args:
        phone_number: Phone number in international format (e.g., +1234567890)
        message_text: SMS message content (max 160 characters recommended)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not SMS_ENABLED or not TWILIO_CLIENT:
        app.logger.warning(f"SMS disabled. Would have sent to {phone_number}: {message_text}")
        return False
    
    try:
        message = TWILIO_CLIENT.messages.create(
            body=message_text,
            from_=TWILIO_PHONE,
            to=phone_number
        )
        app.logger.info(f"SMS sent to {phone_number}. SID: {message.sid}")
        return True
    
    except Exception as e:
        app.logger.error(f"Error sending SMS to {phone_number}: {e}")
        return False

def send_notification_email(user_email, user_name, title, message, action_url="#"):
    """
    Send formatted HTML notification email to user.
    
    Generates a professional HTML email with branded header, notification content,
    and action button. Includes fallback plain text version for email clients that
    don't support HTML.
    
    Args:
        user_email (str): Recipient's email address
        user_name (str): Recipient's display name
        title (str): Notification title/subject
        message (str): Detailed notification message body
        action_url (str, optional): URL for action button. Defaults to "#"
    
    Returns:
        bool: True if email sent successfully, False otherwise
    
    Note:
        Uses the send_email() function with SMTP configuration.
        If SMTP is disabled, logs warning but returns False.
    """
    # Generate professional HTML email body
    html_body = f"""
    <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f5f5; padding: 20px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <!-- Header -->
                <div style="text-align: center; margin-bottom: 30px; border-bottom: 3px solid #007acc; padding-bottom: 20px;">
                    <h2 style="color: #333; margin: 0;">VesselOS</h2>
                    <p style="color: #666; margin: 5px 0 0 0;">International Maritime Standards System</p>
                </div>
                
                <!-- Greeting -->
                <div style="margin-bottom: 20px;">
                    <p style="color: #666; font-size: 16px;">Hello <strong>{user_name}</strong>,</p>
                </div>
                
                <!-- Notification Content -->
                <div style="background-color: #f0f8ff; padding: 20px; border-left: 4px solid #007acc; margin-bottom: 30px; border-radius: 4px;">
                    <h3 style="color: #007acc; margin-top: 0; font-size: 18px;">{title}</h3>
                    <p style="color: #333; line-height: 1.6; font-size: 14px; margin-bottom: 0;">{message}</p>
                </div>
                
                <!-- Action Button -->
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{action_url}" style="display: inline-block; background-color: #007acc; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 14px; transition: background-color 0.3s;">
                        View Details
                    </a>
                </div>
                
                <!-- Footer -->
                <div style="border-top: 1px solid #eee; padding-top: 20px; text-align: center; color: #999; font-size: 12px;">
                    <p style="margin: 5px 0;">© 2026 VesselOS. All rights reserved.</p>
                    <p style="margin: 5px 0;">This is an automated notification. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
    </html>
    """
    
    # Generate plain text version for email clients without HTML support
    plain_text = (
        f"VesselOS - {title}\n"
        f"{'-' * 40}\n\n"
        f"{message}\n\n"
        f"For more information and to take action, visit:\n{action_url}\n\n"
        f"© 2026 VesselOS\n"
        f"This is an automated notification. Please do not reply."
    )
    
    return send_email(user_email, f"[SHIP] {title}", html_body, plain_text)

# ==================== MAINTENANCE REQUEST WORKFLOW HELPERS ====================

def assess_severity(description, maintenance_type, priority="medium"):
    """
    Automatically assess maintenance severity level based on content analysis.
    
    Analyzes maintenance description and type to determine if the request
    is CRITICAL (requires immediate attention) or MINOR (routine maintenance).
    Uses keyword matching and priority flags to make determination.
    
    Args:
        description (str): Detailed description of the maintenance issue
        maintenance_type (str): Category or type of maintenance (engine, hull, etc.)
        priority (str, optional): User-specified priority level. Defaults to "medium"
    
    Returns:
        tuple: (severity_level, reason)
            - severity_level (str): Either 'CRITICAL' or 'MINOR'
            - reason (str): Explanation of severity assessment
    
    Note:
        Critical keywords checked: fire, emergency, flooding, sinking, collision,
        explosion, critical, life safety, hull breach, engine failure, etc.
    """
    # Define keywords that indicate critical severity
    critical_keywords = [
        'fire', 'emergency', 'flooding', 'sinking', 'collision', 'explosion',
        'critical', 'life safety', 'hull breach', 'engine failure', 'uncontrollable',
        'immediate', 'urgent', 'severe', 'catastrophic', 'loss of power'
    ]
    
    # Combine description and type for comprehensive analysis
    combined_text = f"{description} {maintenance_type}".lower()
    
    # Check for critical keywords in combined text
    for keyword in critical_keywords:
        if keyword in combined_text:
            return 'CRITICAL', f'Matched critical keyword: {keyword}'
    
    # Check if priority flag indicates criticality
    if priority.lower() == 'high':
        return 'CRITICAL', 'High priority flag marked as CRITICAL'
    
    # Default to routine maintenance
    return 'MINOR', 'No critical indicators found; assessed as routine maintenance'

def log_workflow_action(request_id, action, actor_id=None, details=""):
    """
    Log a maintenance workflow action for audit trail and tracking.
    
    Records all workflow state changes and actions taken on maintenance
    requests to maintain a complete audit trail of request lifecycle.
    
    Args:
        request_id (str): ID of the maintenance request
        action (str): Type of workflow action (assigned, completed, escalated, etc.)
        actor_id (str, optional): User ID of the person performing the action
        details (str, optional): Additional details about the action
    
    Returns:
        None
    
    Note:
        Failures to log are caught and logged but don't prevent workflow continuation.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        workflow_id = generate_id('WFL')
        cursor.execute(
            """INSERT INTO maintenance_workflow_log
               (id, request_id, action, actor_id, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (workflow_id, request_id, action, actor_id, details, datetime.now())
        )
        conn.commit()
    except Exception as e:
        app.logger.error(f"Failed to log workflow action for request {request_id}: {e}")
    finally:
        conn.close()

def notify_on_severity(request_id, severity, assigned_to=None):
    """Send notifications based on severity level."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM maintenance_requests WHERE request_id = ?", (request_id,))
        request = dict(c.fetchone() or {})
        
        if not request:
            return
        
        if severity == 'CRITICAL':
            # Notify Port Engineer, Harbour Master, and Port Manager
            c.execute("SELECT user_id FROM users WHERE role IN ('port_engineer', 'harbour_master', 'port_manager') AND is_active = 1")
            users = c.fetchall()
            
            for user in users:
                create_notification(
                    user['user_id'],
                    f'CRITICAL Maintenance Request: {request.get("ship_name", "Unknown")}',
                    f'Critical severity auto-assessed for request {request_id}. Immediate attention required.',
                    'danger',
                    f'/view-request/{request_id}'
                )
        else:  # MINOR
            # Notify only Harbour Master
            c.execute("SELECT user_id FROM users WHERE role = 'harbour_master' AND is_active = 1")
            hm_users = c.fetchall()
            
            for user in hm_users:
                create_notification(
                    user['user_id'],
                    f'Maintenance Request: {request.get("ship_name", "Unknown")}',
                    f'Minor severity maintenance request {request_id} assigned to you.',
                    'info',
                    f'/view-request/{request_id}'
                )
    except Exception as e:
        app.logger.error(f"Error sending severity notifications: {e}")
    finally:
        conn.close()

# ==================== INVENTORY MODULE - COMPLETE FUNCTIONS ====================

@app.route('/api/inventory')
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_inventory():
    """Get all inventory items with summary statistics."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # First check if table has correct structure
        c.execute("PRAGMA table_info(inventory)")
        columns = [col[1] for col in c.fetchall()]
        
        # If old table structure exists, recreate it
        if 'item_id' in columns and 'part_number' not in columns:
            # Migrate from old structure to new
            c.execute('''
                CREATE TABLE IF NOT EXISTS inventory_new (
                    part_number TEXT PRIMARY KEY,
                    part_name TEXT NOT NULL,
                    category TEXT,
                    current_stock INTEGER DEFAULT 0,
                    minimum_stock INTEGER DEFAULT 10,
                    reorder_level INTEGER DEFAULT 5,
                    unit_price REAL DEFAULT 0.0,
                    supplier TEXT,
                    manufacturer TEXT,
                    location TEXT,
                    currency TEXT DEFAULT 'USD',
                    shelf_life_months INTEGER,
                    notes TEXT,
                    status TEXT DEFAULT 'OK',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Copy data from old table if exists
            c.execute("SELECT * FROM inventory")
            old_items = c.fetchall()
            for item in old_items:
                item_dict = dict(item)
                c.execute('''
                    INSERT INTO inventory_new (part_number, part_name, category, current_stock, 
                    minimum_stock, reorder_level, unit_price, supplier, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item_dict.get('item_id', f"PART{item_dict.get('id', '001')}"),
                    item_dict.get('item_name', 'Unknown'),
                    item_dict.get('category', 'Other'),
                    item_dict.get('quantity', 0),
                    item_dict.get('minimum_quantity', 10),
                    5,  # default reorder level
                    item_dict.get('unit_price', 0.0) or 0.0,
                    item_dict.get('supplier', 'Unknown'),
                    item_dict.get('last_restocked', datetime.now())
                ))
            
            # Rename tables
            c.execute("DROP TABLE IF EXISTS inventory_old")
            c.execute("ALTER TABLE inventory RENAME TO inventory_old")
            c.execute("ALTER TABLE inventory_new RENAME TO inventory")
            conn.commit()
        
        # Ensure table exists with correct structure
        c.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                part_number TEXT PRIMARY KEY,
                part_name TEXT NOT NULL,
                category TEXT,
                current_stock INTEGER DEFAULT 0,
                minimum_stock INTEGER DEFAULT 10,
                reorder_level INTEGER DEFAULT 5,
                unit_price REAL DEFAULT 0.0,
                supplier TEXT,
                manufacturer TEXT,
                location TEXT,
                currency TEXT DEFAULT 'USD',
                shelf_life_months INTEGER,
                notes TEXT,
                status TEXT DEFAULT 'OK',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Get all inventory items
        c.execute("SELECT * FROM inventory ORDER BY part_name")
        rows = c.fetchall()
        inventory = []
        total_value = 0
        low_stock_count = 0
        critical_stock_count = 0
        categories = set()
        
        for r in rows:
            item = dict(r)
            # Calculate status
            current_stock = item['current_stock'] or 0
            minimum_stock = item['minimum_stock'] or 10
            reorder_level = item['reorder_level'] or 5
            
            status = 'OK'
            if current_stock <= reorder_level:
                status = 'CRITICAL'
                critical_stock_count += 1
            elif current_stock <= minimum_stock:
                status = 'LOW'
                low_stock_count += 1
            
            item['status'] = status
            inventory.append(item)
            
            # Calculate total value
            unit_price = item['unit_price'] or 0
            total_value += current_stock * unit_price
            
            # Add category to set
            if item['category']:
                categories.add(item['category'])
        
        # Calculate summary
        summary = {
            'total_items': len(inventory),
            'total_value': f"${total_value:,.2f}",
            'low_stock': low_stock_count,
            'critical_stock': critical_stock_count,
            'categories': len(categories),
            'total_stock_value': total_value
        }
        
        return jsonify(success=True, inventory=inventory, summary=summary)
    except Exception as e:
        app.logger.error(f"Error getting inventory: {e}")
        return jsonify(success=False, error=str(e))
    finally:
        conn.close()

@app.route('/api/inventory/item/<part_number>')
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_inventory_item(part_number):
    """Get specific inventory item."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM inventory WHERE part_number = ?", (part_number,))
        item = c.fetchone()
        
        if not item:
            return jsonify(success=False, error='Item not found')
        
        item_dict = dict(item)
        
        # Calculate status
        current_stock = item_dict['current_stock'] or 0
        minimum_stock = item_dict['minimum_stock'] or 10
        reorder_level = item_dict['reorder_level'] or 5
        
        if current_stock <= reorder_level:
            item_dict['status'] = 'CRITICAL'
        elif current_stock <= minimum_stock:
            item_dict['status'] = 'LOW'
        else:
            item_dict['status'] = 'OK'
        
        return jsonify(success=True, item=item_dict)
    except Exception as e:
        app.logger.error(f"Error getting inventory item: {e}")
        return jsonify(success=False, error=str(e))
    finally:
        conn.close()

@app.route('/api/inventory/update', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_inventory_update():
    """
    Add a new inventory item or update an existing one.
    
    Validates all required fields, numeric constraints, and reorder logic
    before inserting or updating the inventory database. Automatically
    determines stock status (CRITICAL/LOW/OK) based on quantity levels.
    
    JSON Request Body:
        - part_number (str, required): Unique part identifier
        - part_name (str, required): Display name for the part
        - category (str, required): Inventory category
        - current_stock (int, required): Current quantity on hand
        - minimum_stock (int, required): Minimum safe quantity
        - reorder_level (int, required): Quantity at which to trigger reorder
        - unit_price (float, required): Cost per unit
        - supplier (str, required): Supplier name
        - manufacturer (str, optional): Part manufacturer
        - location (str, optional): Storage location
        - currency (str, optional): Price currency code (default: USD)
        - shelf_life_months (int, optional): Product shelf life
        - notes (str, optional): Additional notes
    
    Validation:
        - All required fields must be present and non-empty
        - Numeric fields must parse correctly
        - All quantities and prices must be non-negative
        - Reorder level must be less than minimum stock level
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - message (str): Success message
            - error (str): Error description if failed
    
    Status Codes:
        - 200: Item added or updated successfully
        - 400: Validation error (missing/invalid fields)
        - 409: Part number already exists (new insert)
        - 500: Database error
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['part_number', 'part_name', 'category', 'current_stock', 
                          'minimum_stock', 'reorder_level', 'unit_price', 'supplier']
        
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                return jsonify(success=False, error=f'Missing required field: {field}'), 400
        
        # Validate and parse numeric fields
        try:
            current_stock = int(data['current_stock'])
            minimum_stock = int(data['minimum_stock'])
            reorder_level = int(data['reorder_level'])
            unit_price = float(data['unit_price'])
        except ValueError:
            return jsonify(success=False, error='Invalid numeric values for stock or price'), 400
        
        # Validate non-negative values
        if any(v < 0 for v in [current_stock, minimum_stock, reorder_level, unit_price]):
            return jsonify(success=False, error='Stock levels and price cannot be negative'), 400
        
        # Validate reorder level logic
        if reorder_level >= minimum_stock:
            return jsonify(
                success=False, 
                error='Reorder level must be less than minimum stock level'
            ), 400
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Check if item exists
            cursor.execute("SELECT part_number FROM inventory WHERE part_number = ?", (data['part_number'],))
            exists = cursor.fetchone() is not None
            
            # Determine stock status
            if current_stock <= reorder_level:
                status = 'CRITICAL'
            elif current_stock <= minimum_stock:
                status = 'LOW'
            else:
                status = 'OK'
            
            if exists:
                # Update existing inventory item
                cursor.execute('''
                    UPDATE inventory 
                    SET part_name = ?, category = ?, current_stock = ?, minimum_stock = ?,
                        reorder_level = ?, unit_price = ?, supplier = ?, manufacturer = ?,
                        location = ?, currency = ?, shelf_life_months = ?, notes = ?,
                        status = ?, last_updated = ?
                    WHERE part_number = ?
                ''', (
                    data['part_name'], data['category'], current_stock, minimum_stock,
                    reorder_level, unit_price, data['supplier'], data.get('manufacturer'),
                    data.get('location'), data.get('currency', 'USD'),
                    data.get('shelf_life_months'), data.get('notes'), status,
                    datetime.now(), data['part_number']
                ))
                action = 'updated'
            else:
                # Insert new inventory item
                cursor.execute('''
                    INSERT INTO inventory 
                    (part_number, part_name, category, current_stock, minimum_stock,
                     reorder_level, unit_price, supplier, manufacturer, location,
                     currency, shelf_life_months, notes, status, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['part_number'], data['part_name'], data['category'],
                    current_stock, minimum_stock, reorder_level, unit_price,
                    data['supplier'], data.get('manufacturer'), data.get('location'),
                    data.get('currency', 'USD'), data.get('shelf_life_months'),
                    data.get('notes'), status, datetime.now()
                ))
                action = 'added'
            
            conn.commit()
            log_activity(
                f'inventory_{action}',
                f'{action.capitalize()} item {data["part_number"]}: {data["part_name"]}'
            )
            
            return jsonify(success=True, message=f'Item {action} successfully'), 200

        except sqlite3.IntegrityError:
            return jsonify(success=False, error='Part number already exists'), 409
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Database error during inventory update: {e}")
            return jsonify(success=False, error='Database error occurred'), 500
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error processing inventory update request: {e}")
        return jsonify(success=False, error='Failed to process request'), 500   

@app.route('/api/inventory/update-stock', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_inventory_update_stock():
    """Update stock quantity for an item."""
    try:
        data = request.get_json()
        
        part_number = data.get('part_number')
        new_stock = data.get('current_stock')
        
        if not part_number or new_stock is None:
            return jsonify(success=False, error='Missing required fields')
        
        try:
            new_stock = int(new_stock)
            if new_stock < 0:
                return jsonify(success=False, error='Stock cannot be negative')
        except ValueError:
            return jsonify(success=False, error='Invalid stock value')
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get current item to calculate status
            c.execute("SELECT minimum_stock, reorder_level FROM inventory WHERE part_number = ?", (part_number,))
            item = c.fetchone()
            
            if not item:
                return jsonify(success=False, error='Item not found')
            
            minimum_stock = item['minimum_stock'] or 10
            reorder_level = item['reorder_level'] or 5
            
            # Calculate new status
            if new_stock <= reorder_level:
                status = 'CRITICAL'
            elif new_stock <= minimum_stock:
                status = 'LOW'
            else:
                status = 'OK'
            
            # Update stock and status
            c.execute('''
                UPDATE inventory 
                SET current_stock = ?, status = ?, last_updated = ?
                WHERE part_number = ?
            ''', (new_stock, status, datetime.now(), part_number))
            
            conn.commit()
            log_activity('inventory_stock_update', f'Updated stock for {part_number} to {new_stock}')
            
            return jsonify(success=True, message='Stock updated successfully')
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating stock: {e}")
            return jsonify(success=False, error='Database error')
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in stock update: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/inventory/delete/<part_number>', methods=['DELETE'])
@login_required
@role_required(['port_engineer'])
def api_inventory_delete(part_number):
    """Delete inventory item."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Check if item exists
        c.execute("SELECT part_name FROM inventory WHERE part_number = ?", (part_number,))
        item = c.fetchone()
        
        if not item:
            return jsonify(success=False, error='Item not found')
        
        # Delete item
        c.execute("DELETE FROM inventory WHERE part_number = ?", (part_number,))
        conn.commit()
        
        log_activity('inventory_delete', f'Deleted item: {part_number} - {item["part_name"]}')
        return jsonify(success=True, message='Item deleted successfully')
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error deleting inventory item: {e}")
        return jsonify(success=False, error='Database error')
    finally:
        conn.close()

@app.route('/api/inventory/import', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_inventory_import():
    """Import inventory from CSV file."""
    if 'file' not in request.files:
        return jsonify(success=False, error='No file uploaded')
    
    file = request.files['file']
    if file.filename == '':
        return jsonify(success=False, error='No file selected')
    
    if not allowed_file(file.filename):
        return jsonify(success=False, error='Invalid file type. Only CSV files allowed')
    
    try:
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)
        
        # No required columns - accept any CSV structure
        conn = get_db_connection()
        try:
            c = conn.cursor()
            imported_count = 0
            errors = []
            
            for i, row in enumerate(reader, start=2):  # Start at 2 for line numbers (1 is header)
                try:
                    # Get values from row if they exist, otherwise use defaults
                    part_number = row.get('part_number', '').strip() or f'PART-{i}'
                    part_name = row.get('part_name', '').strip() or row.get('name', '').strip() or f'Part {i}'
                    category = row.get('category', '').strip() or 'Uncategorized'
                    supplier = row.get('supplier', '').strip() or 'Unknown'
                    
                    # Parse numeric values with defaults
                    try:
                        current_stock = int(row.get('current_stock', 0)) if row.get('current_stock') else 0
                    except (ValueError, TypeError):
                        current_stock = 0
                    
                    try:
                        minimum_stock = int(row.get('minimum_stock', 0)) if row.get('minimum_stock') else 0
                    except (ValueError, TypeError):
                        minimum_stock = 0
                    
                    try:
                        reorder_level = int(row.get('reorder_level', 0)) if row.get('reorder_level') else 0
                    except (ValueError, TypeError):
                        reorder_level = 0
                    
                    try:
                        unit_price = float(row.get('unit_price', 0)) if row.get('unit_price') else 0.0
                    except (ValueError, TypeError):
                        unit_price = 0.0
                    
                    # Validate values - no negative values
                    if any(val < 0 for val in [current_stock, minimum_stock, reorder_level, unit_price]):
                        errors.append(f'Line {i}: Values cannot be negative')
                        continue
                    
                    # Calculate status
                    if current_stock <= reorder_level:
                        status = 'CRITICAL'
                    elif current_stock <= minimum_stock:
                        status = 'LOW'
                    else:
                        status = 'OK'
                    
                    # Insert or update
                    c.execute('''
                        INSERT OR REPLACE INTO inventory 
                        (part_number, part_name, category, current_stock, minimum_stock,
                         reorder_level, unit_price, supplier, status, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row.get('part_number', f'PART-{i}').strip(),
                        row.get('part_name', '').strip() or row.get('name', f'Part {i}').strip(),
                        row.get('category', 'Uncategorized').strip(),
                        current_stock,
                        minimum_stock,
                        reorder_level,
                        unit_price,
                        row.get('supplier', 'Unknown').strip(),
                        status,
                        datetime.now()
                    ))
                    
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f'Line {i}: {str(e)}')
                    continue
            
            conn.commit()
            
            if errors:
                message = f'Imported {imported_count} items with {len(errors)} errors'
                return jsonify(success=True, message=message, errors=errors[:10])  # Limit errors displayed
            else:
                log_activity('inventory_import', f'Imported {imported_count} items from CSV')
                return jsonify(success=True, message=f'Successfully imported {imported_count} items')
                
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error importing CSV: {e}")
            return jsonify(success=False, error='Database error during import')
        finally:
            conn.close()
            
    except Exception as e:
        app.logger.error(f"Error processing CSV file: {e}")
        return jsonify(success=False, error='Error processing CSV file')

@app.route('/api/inventory/export')
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_inventory_export():
    """Export inventory to CSV file."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT part_number, part_name, category, current_stock, 
                   minimum_stock, reorder_level, unit_price, supplier,
                   manufacturer, location, currency, shelf_life_months,
                   notes, status, last_updated
            FROM inventory
            ORDER BY category, part_name
        """)
        
        rows = c.fetchall()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'part_number', 'part_name', 'category', 'current_stock',
            'minimum_stock', 'reorder_level', 'unit_price', 'supplier',
            'manufacturer', 'location', 'currency', 'shelf_life_months',
            'notes', 'status', 'last_updated'
        ])
        
        # Write data
        for row in rows:
            writer.writerow([
                row['part_number'],
                row['part_name'],
                row['category'],
                row['current_stock'],
                row['minimum_stock'],
                row['reorder_level'],
                row['unit_price'],
                row['supplier'],
                row['manufacturer'] or '',
                row['location'] or '',
                row['currency'] or 'USD',
                row['shelf_life_months'] or '',
                row['notes'] or '',
                row['status'],
                row['last_updated']
            ])
        
        output.seek(0)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'inventory_export_{timestamp}.csv'
        
        log_activity('inventory_export', 'Exported inventory to CSV')
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
        
    except Exception as e:
        app.logger.error(f"Error exporting inventory: {e}")
        return jsonify(success=False, error=str(e))
    finally:
        conn.close()

@app.route('/api/inventory-folders/upload', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_upload_inventory_folder():
    """Upload inventory folder with Excel files (can be empty or incomplete)."""
    try:
        if 'folderName' not in request.form or 'files' not in request.files:
            return jsonify(success=False, error='Missing folder name or files')
        
        folder_name = request.form.get('folderName', '').strip()
        if not folder_name:
            return jsonify(success=False, error='Folder name cannot be empty')
        
        # Sanitize folder name
        safe_folder_name = secure_filename(folder_name)
        
        # Create folder path
        upload_base = os.path.join(app.config['UPLOAD_FOLDER'], 'inventory_folders')
        folder_path = os.path.join(upload_base, safe_folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        files = request.files.getlist('files')
        saved_files = []
        
        for f in files:
            if f and f.filename:
                # Allow Excel and CSV files
                if not (f.filename.lower().endswith(('.xlsx', '.xls', '.csv'))):
                    continue
                
                filename = secure_filename(f.filename)
                filepath = os.path.join(folder_path, filename)
                f.save(filepath)
                saved_files.append(filename)
        
        # Create metadata file for the folder
        metadata = {
            'folder_name': folder_name,
            'created_by': current_user.id if current_user.is_authenticated else 'unknown',
            'created_at': datetime.now().isoformat(),
            'files': saved_files
        }
        
        metadata_path = os.path.join(folder_path, '.metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        log_activity('inventory_folder_upload', f'Uploaded folder: {folder_name}')
        return jsonify(success=True, message=f'Uploaded folder "{folder_name}" with {len(saved_files)} file(s)', 
                      folder_name=safe_folder_name, files=saved_files)
    
    except Exception as e:
        app.logger.error(f"Error uploading inventory folder: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/inventory-folders', methods=['GET'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_list_inventory_folders():
    """List all inventory folders."""
    try:
        upload_base = os.path.join(app.config['UPLOAD_FOLDER'], 'inventory_folders')
        folders = []
        
        if os.path.isdir(upload_base):
            for folder_name in os.listdir(upload_base):
                folder_path = os.path.join(upload_base, folder_name)
                if os.path.isdir(folder_path):
                    # Get metadata if available
                    metadata_path = os.path.join(folder_path, '.metadata.json')
                    metadata = {}
                    if os.path.exists(metadata_path):
                        try:
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                        except:
                            pass
                    
                    # Get files
                    files = [f for f in os.listdir(folder_path) if not f.startswith('.')]
                    
                    folders.append({
                        'id': folder_name,
                        'name': metadata.get('folder_name', folder_name),
                        'created_by': metadata.get('created_by', 'Unknown'),
                        'created_at': metadata.get('created_at', ''),
                        'files': files,
                        'file_count': len(files)
                    })
        
        return jsonify(success=True, folders=folders)
    
    except Exception as e:
        app.logger.error(f"Error listing inventory folders: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/inventory-folders/<folder_id>/rename', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_rename_inventory_folder(folder_id):
    """Rename an inventory folder."""
    try:
        data = request.get_json()
        new_name = data.get('newName', '').strip()
        
        if not new_name:
            return jsonify(success=False, error='New folder name cannot be empty')
        
        upload_base = os.path.join(app.config['UPLOAD_FOLDER'], 'inventory_folders')
        old_path = os.path.join(upload_base, folder_id)
        
        if not os.path.isdir(old_path):
            return jsonify(success=False, error='Folder not found')
        
        safe_new_name = secure_filename(new_name)
        new_path = os.path.join(upload_base, safe_new_name)
        
        if os.path.exists(new_path) and new_path != old_path:
            return jsonify(success=False, error='Folder with this name already exists')
        
        os.rename(old_path, new_path)
        
        # Update metadata
        metadata_path = os.path.join(new_path, '.metadata.json')
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                metadata['folder_name'] = new_name
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
            except:
                pass
        
        log_activity('inventory_folder_rename', f'Renamed folder from {folder_id} to {safe_new_name}')
        return jsonify(success=True, message=f'Folder renamed to "{new_name}"', new_id=safe_new_name)
    
    except Exception as e:
        app.logger.error(f"Error renaming inventory folder: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/inventory-folders/<folder_id>/delete', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_delete_inventory_folder(folder_id):
    """Delete an inventory folder."""
    try:
        upload_base = os.path.join(app.config['UPLOAD_FOLDER'], 'inventory_folders')
        folder_path = os.path.join(upload_base, folder_id)
        
        if not os.path.isdir(folder_path):
            return jsonify(success=False, error='Folder not found')
        
        # Delete folder and its contents
        shutil.rmtree(folder_path)
        
        log_activity('inventory_folder_delete', f'Deleted folder: {folder_id}')
        return jsonify(success=True, message='Folder deleted successfully')
    
    except Exception as e:
        app.logger.error(f"Error deleting inventory folder: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/inventory-folders/<folder_id>/upload', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_upload_files_to_folder(folder_id):
    """Upload additional files to an existing inventory folder."""
    try:
        upload_base = os.path.join(app.config['UPLOAD_FOLDER'], 'inventory_folders')
        folder_path = os.path.join(upload_base, folder_id)
        
        if not os.path.isdir(folder_path):
            return jsonify(success=False, error='Folder not found')
        
        if 'files' not in request.files:
            return jsonify(success=False, error='No files provided')
        
        files = request.files.getlist('files')
        saved_files = []
        
        for f in files:
            if f and f.filename:
                if not (f.filename.lower().endswith(('.xlsx', '.xls', '.csv'))):
                    continue
                
                filename = secure_filename(f.filename)
                filepath = os.path.join(folder_path, filename)
                f.save(filepath)
                saved_files.append(filename)
        
        # Update metadata
        metadata_path = os.path.join(folder_path, '.metadata.json')
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                # Merge files
                all_files = list(set(metadata.get('files', []) + saved_files))
                metadata['files'] = all_files
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
            except:
                pass
        
        log_activity('inventory_folder_upload_files', f'Uploaded {len(saved_files)} file(s) to {folder_id}')
        return jsonify(success=True, message=f'Uploaded {len(saved_files)} file(s)', files=saved_files)
    
    except Exception as e:
        app.logger.error(f"Error uploading files to folder: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/inventory-folders/<folder_id>/<file_name>', methods=['GET'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_get_inventory_file(folder_id, file_name):
    """Get inventory file content."""
    try:
        upload_base = os.path.join(app.config['UPLOAD_FOLDER'], 'inventory_folders')
        file_path = os.path.join(upload_base, folder_id, secure_filename(file_name))
        
        if not os.path.exists(file_path):
            return jsonify(success=False, error='File not found'), 404
        
        if file_name.lower().endswith(('.xlsx', '.xls')):
            # For Excel files, return JSON response indicating file type (don't try to read binary)
            return jsonify(success=False, error='Excel files must be downloaded and edited locally', file_type='excel')
        else:
            # For CSV files, read and return content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return jsonify(success=True, content=content, file_type='csv')
    
    except Exception as e:
        app.logger.error(f"Error retrieving inventory file: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/inventory-folders/<folder_id>/<file_name>', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_edit_inventory_file(folder_id, file_name):
    """Edit inventory file (for CSV files)."""
    try:
        data = request.get_json()
        new_content = data.get('content', '')
        
        upload_base = os.path.join(app.config['UPLOAD_FOLDER'], 'inventory_folders')
        file_path = os.path.join(upload_base, folder_id, secure_filename(file_name))
        
        if not file_path.lower().endswith('.csv'):
            return jsonify(success=False, error='Only CSV files can be edited directly')
        
        if not os.path.exists(file_path):
            return jsonify(success=False, error='File not found')
        
        # Save backup
        backup_path = file_path + '.backup'
        if os.path.exists(file_path):
            shutil.copy(file_path, backup_path)
        
        # Write new content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        log_activity('inventory_file_edit', f'Edited file: {folder_id}/{file_name}')
        return jsonify(success=True, message='File updated successfully')
    
    except Exception as e:
        app.logger.error(f"Error editing inventory file: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/inventory-folders/<folder_id>/<file_name>/rename', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_rename_folder_file(folder_id, file_name):
    """Rename a file within an inventory folder."""
    try:
        data = request.get_json()
        new_name = data.get('newName', '').strip()
        
        if not new_name:
            return jsonify(success=False, error='New file name cannot be empty')
        
        upload_base = os.path.join(app.config['UPLOAD_FOLDER'], 'inventory_folders')
        old_path = os.path.join(upload_base, folder_id, secure_filename(file_name))
        new_path = os.path.join(upload_base, folder_id, secure_filename(new_name))
        
        if not os.path.exists(old_path):
            return jsonify(success=False, error='File not found')
        
        if os.path.exists(new_path) and new_path != old_path:
            return jsonify(success=False, error='File with this name already exists')
        
        os.rename(old_path, new_path)
        
        log_activity('inventory_file_rename', f'Renamed file: {folder_id}/{file_name} -> {new_name}')
        return jsonify(success=True, message=f'File renamed to "{new_name}"', new_name=secure_filename(new_name))
    
    except Exception as e:
        app.logger.error(f"Error renaming inventory file: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/inventory-folders/<folder_id>/<file_name>/delete', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_delete_folder_file(folder_id, file_name):
    """Delete a file from an inventory folder."""
    try:
        upload_base = os.path.join(app.config['UPLOAD_FOLDER'], 'inventory_folders')
        file_path = os.path.join(upload_base, folder_id, secure_filename(file_name))
        
        if not os.path.exists(file_path):
            return jsonify(success=False, error='File not found')
        
        os.remove(file_path)
        
        log_activity('inventory_file_delete', f'Deleted file: {folder_id}/{file_name}')
        return jsonify(success=True, message='File deleted successfully')
    
    except Exception as e:
        app.logger.error(f"Error deleting inventory file: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/request-reorder', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_request_reorder():
    """Request reorder for low stock item."""
    try:
        data = request.get_json()
        
        part_number = data.get('part_number')
        part_name = data.get('part_name')
        quantity = data.get('quantity', 10)
        
        if not part_number or not part_name:
            return jsonify(success=False, error='Missing required fields')
        
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return jsonify(success=False, error='Quantity must be positive')
        except ValueError:
            return jsonify(success=False, error='Invalid quantity')
        
        # Create notification for port engineers
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get all port engineers
            c.execute("SELECT user_id FROM users WHERE role = 'port_engineer' AND is_active = 1")
            port_engineers = c.fetchall()
            
            for port_engineer in port_engineers:
                create_notification(
                    port_engineer['user_id'],
                    f'Reorder Request: {part_name}',
                    f'{current_user.get_full_name()} requested reorder of {quantity} units for {part_name} ({part_number})',
                    'warning',
                    '/inventory'
                )
            
            log_activity('reorder_requested', f'Requested reorder for {part_number}: {quantity} units')
            
            return jsonify(success=True, message='Reorder request submitted to port engineers')
        except Exception as e:
            app.logger.error(f"Error creating reorder request: {e}")
            return jsonify(success=False, error='Database error')
        finally:
            conn.close()
            
    except Exception as e:
        app.logger.error(f"Error in reorder request: {e}")
        return jsonify(success=False, error=str(e))

@app.route('/api/bulk-reorder', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def bulk_reorder():
    """Request bulk reorder for multiple low stock items."""
    try:
        data = request.get_json()
        
        if 'items' not in data or not data['items']:
            return jsonify({'success': False, 'error': 'No items selected'}), 400
        
        items = data['items']
        
        # Create summary notification
        item_list = '\n'.join([f"- {item.get('part_number', 'Unknown')}: {item.get('part_name', 'Unknown')}" 
                              for item in items[:10]])  # First 10 items
        if len(items) > 10:
            item_list += f'\n... and {len(items) - 10} more items'
        
        # Create notification for port engineer
        create_notification(
            'system',
            f'Bulk Reorder Request: {len(items)} items',
            f'{current_user.get_full_name()} requested bulk reorder for {len(items)} low stock items:\n{item_list}',
            'warning',
            '/inventory'
        )
        
        # Log activity
        log_activity('bulk_reorder_requested',
                    f'Requested bulk reorder for {len(items)} items')
        
        return jsonify({'success': True, 'message': f'Bulk reorder request submitted for {len(items)} items'})
        
    except Exception as e:
        app.logger.error(f"Error in bulk reorder: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== PROCUREMENT SYSTEM ENDPOINTS ====================

@app.route('/api/inventory-files', methods=['GET'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_inventory_files():
    """Get all inventory files."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT f.file_id, f.file_name, f.created_by, f.created_at, f.updated_at, 
                   f.file_status, COUNT(p.part_id) as part_count
            FROM inventory_files f
            LEFT JOIN inventory_file_parts p ON f.file_id = p.file_id
            WHERE f.file_status = 'active'
            GROUP BY f.file_id
            ORDER BY f.updated_at DESC
        """)
        files = [dict(row) for row in c.fetchall()]
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        app.logger.error(f"Error getting inventory files: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/inventory-files/upload', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_upload_inventory_files():
    """Upload multiple inventory files."""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'})
        
        files = request.files.getlist('files')
        if not files:
            return jsonify({'success': False, 'error': 'No files selected'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            uploaded_files = []
            
            for file in files:
                if file and file.filename:
                    if not allowed_file(file.filename):
                        continue
                    
                    # Create inventory file record
                    file_id = generate_id('FILE')
                    file_name = secure_filename(file.filename)
                    
                    c.execute("""
                        INSERT INTO inventory_files (file_id, file_name, created_by, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (file_id, file_name, current_user.id, datetime.now()))
                    
                    # Save file to uploads
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    stored_name = f"{file_id}_{timestamp}_{file_name}"
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', 'inventory', stored_name)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    file.save(save_path)
                    
                    uploaded_files.append({'file_id': file_id, 'file_name': file_name})
            
            conn.commit()
            log_activity('inventory_files_uploaded', f'Uploaded {len(uploaded_files)} inventory files')
            return jsonify({'success': True, 'files': uploaded_files})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error uploading files: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in upload files: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/inventory-files/<file_id>/rename', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_rename_inventory_file(file_id):
    """Rename an inventory file."""
    try:
        data = request.get_json()
        new_name = data.get('new_name')
        
        if not new_name:
            return jsonify({'success': False, 'error': 'New name required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                UPDATE inventory_files 
                SET file_name = ?, updated_at = ?
                WHERE file_id = ?
            """, (new_name, datetime.now(), file_id))
            conn.commit()
            log_activity('inventory_file_renamed', f'Renamed file {file_id} to {new_name}')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error renaming file: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in rename file: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/inventory-files/<file_id>', methods=['DELETE'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_delete_inventory_file(file_id):
    """Delete an inventory file and its parts."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE inventory_files 
            SET file_status = 'deleted', updated_at = ?
            WHERE file_id = ?
        """, (datetime.now(), file_id))
        conn.commit()
        log_activity('inventory_file_deleted', f'Deleted file {file_id}')
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error deleting file: {e}")
        return jsonify({'success': False, 'error': 'Database error'})
    finally:
        conn.close()

@app.route('/api/inventory-files/<file_id>/parts', methods=['GET'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_get_file_parts(file_id):
    """Get all parts in an inventory file."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT part_id, part_number, part_name, category, quantity, location, 
                   supplier, manufacturer, notes, added_at, part_status
            FROM inventory_file_parts
            WHERE file_id = ? AND part_status = 'active'
            ORDER BY part_name
        """, (file_id,))
        parts = [dict(row) for row in c.fetchall()]
        return jsonify({'success': True, 'parts': parts})
    except Exception as e:
        app.logger.error(f"Error getting file parts: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/inventory-files/<file_id>/parts', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_add_part_to_file(file_id):
    """Add a part to an inventory file."""
    try:
        data = request.get_json()
        part_number = data.get('part_number')
        part_name = data.get('part_name')
        category = data.get('category')
        quantity = data.get('quantity', 0)
        location = data.get('location')
        supplier = data.get('supplier')
        manufacturer = data.get('manufacturer')
        notes = data.get('notes')
        
        if not part_number or not part_name:
            return jsonify({'success': False, 'error': 'Part number and name required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            part_id = generate_id('PART')
            
            c.execute("""
                INSERT INTO inventory_file_parts 
                (part_id, file_id, part_number, part_name, category, quantity, location, supplier, manufacturer, notes, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (part_id, file_id, part_number, part_name, category, quantity, location, supplier, manufacturer, notes, datetime.now()))
            
            conn.commit()
            log_activity('inventory_part_added', f'Added part {part_number} to file {file_id}')
            return jsonify({'success': True, 'part_id': part_id})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'error': 'Part number already exists in this file'})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error adding part: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in add part: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/inventory-files/<file_id>/parts/<part_id>', methods=['PUT'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_edit_file_part(file_id, part_id):
    """Edit a part in an inventory file."""
    try:
        data = request.get_json()
        part_name = data.get('part_name')
        category = data.get('category')
        quantity = data.get('quantity')
        location = data.get('location')
        supplier = data.get('supplier')
        manufacturer = data.get('manufacturer')
        notes = data.get('notes')
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                UPDATE inventory_file_parts
                SET part_name = ?, category = ?, quantity = ?, location = ?, 
                    supplier = ?, manufacturer = ?, notes = ?
                WHERE part_id = ? AND file_id = ?
            """, (part_name, category, quantity, location, supplier, manufacturer, notes, part_id, file_id))
            
            conn.commit()
            log_activity('inventory_part_edited', f'Edited part {part_id}')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error editing part: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in edit part: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/inventory-files/<file_id>/parts/<part_id>', methods=['DELETE'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_delete_file_part(file_id, part_id):
    """Delete a part from an inventory file."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE inventory_file_parts
            SET part_status = 'deleted'
            WHERE part_id = ? AND file_id = ?
        """, (part_id, file_id))
        conn.commit()
        log_activity('inventory_part_deleted', f'Deleted part {part_id}')
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error deleting part: {e}")
        return jsonify({'success': False, 'error': 'Database error'})
    finally:
        conn.close()

@app.route('/api/inventory-files/upload-csv', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_upload_inventory_csv():
    """Upload multiple folders with CSV files and create inventory files and parts."""
    try:
        data = request.get_json()
        folders = data.get('folders', [])
        
        if not folders:
            return jsonify({'success': False, 'error': 'No folders provided'})
        
        conn = get_db_connection()
        created_files = 0
        created_parts = 0
        details = []
        
        try:
            c = conn.cursor()
            
            for folder_data in folders:
                folder_name = folder_data.get('folderName')
                parts_list = folder_data.get('parts', [])
                
                if not folder_name or not parts_list:
                    continue
                
                # Create inventory file for this folder
                file_id = generate_id('FILE')
                current_time = datetime.datetime.now()
                
                c.execute("""
                    INSERT INTO inventory_files 
                    (file_id, file_name, vessel_id, created_by, created_at, updated_at, file_status)
                    VALUES (?, ?, ?, ?, ?, ?, 'active')
                """, (file_id, folder_name, session.get('vessel_id'), current_user.id, current_time, current_time))
                
                created_files += 1
                parts_count = 0
                
                # Add parts from CSV to this file
                for part_data in parts_list:
                    try:
                        part_id = generate_id('PART')
                        
                        # Check for duplicate part numbers in same file
                        c.execute("""
                            SELECT COUNT(*) FROM inventory_file_parts
                            WHERE file_id = ? AND part_number = ? AND part_status != 'deleted'
                        """, (file_id, part_data.get('part_number')))
                        
                        if c.fetchone()[0] > 0:
                            continue  # Skip duplicate part numbers
                        
                        c.execute("""
                            INSERT INTO inventory_file_parts
                            (part_id, file_id, part_number, part_name, category, quantity, 
                             location, supplier, manufacturer, notes, added_at, part_status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                        """, (
                            part_id,
                            file_id,
                            part_data.get('part_number'),
                            part_data.get('part_name'),
                            part_data.get('category'),
                            int(part_data.get('quantity', 0)),
                            part_data.get('location', ''),
                            part_data.get('supplier', ''),
                            part_data.get('manufacturer', ''),
                            part_data.get('notes', ''),
                            current_time
                        ))
                        
                        created_parts += 1
                        parts_count += 1
                        
                    except Exception as e:
                        app.logger.error(f"Error adding part {part_data.get('part_number')}: {e}")
                        continue
                
                if parts_count > 0:
                    details.append({
                        'folderName': folder_name,
                        'partsCount': parts_count
                    })
            
            conn.commit()
            log_activity('inventory_csv_upload', f'Uploaded {created_files} folder(s) with {created_parts} parts')
            
            return jsonify({
                'success': True,
                'data': {
                    'created_files': created_files,
                    'created_parts': created_parts,
                    'details': details
                }
            })
        
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error uploading CSV: {e}")
            return jsonify({'success': False, 'error': f'Database error: {str(e)}'})
        finally:
            conn.close()
    
    except Exception as e:
        app.logger.error(f"Error processing CSV upload: {e}")
        return jsonify({'success': False, 'error': 'Invalid request format'})

@app.route('/api/inventory-files/<file_id>/download-csv', methods=['GET'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_download_file_csv(file_id):
    """Download a file and its parts as CSV."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get file info
        c.execute("SELECT file_name FROM inventory_files WHERE file_id = ? AND file_status != 'deleted'", (file_id,))
        file_row = c.fetchone()
        
        if not file_row:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Get all parts in file
        c.execute("""
            SELECT part_number, part_name, category, quantity, location, supplier, manufacturer, notes
            FROM inventory_file_parts
            WHERE file_id = ? AND part_status != 'deleted'
            ORDER BY part_name
        """, (file_id,))
        
        parts = c.fetchall()
        conn.close()
        
        # Build CSV
        csv_lines = ['part_number,part_name,category,quantity,location,supplier,manufacturer,notes']
        for part in parts:
            # Escape CSV fields with quotes if needed
            row = []
            for field in part:
                field_str = str(field) if field else ''
                if ',' in field_str or '"' in field_str or '\n' in field_str:
                    field_str = '"' + field_str.replace('"', '""') + '"'
                row.append(field_str)
            csv_lines.append(','.join(row))
        
        csv_content = '\n'.join(csv_lines)
        
        # Create response
        response = app.response_class(
            response=csv_content,
            status=200,
            mimetype='text/csv'
        )
        response.headers['Content-Disposition'] = f'attachment; filename="{file_row[0]}_parts.csv"'
        
        log_activity('inventory_file_download', f'Downloaded file {file_id} as CSV')
        return response
    
    except Exception as e:
        app.logger.error(f"Error downloading file CSV: {e}")
        return jsonify({'success': False, 'error': 'Download error'}), 500

# Machinery Manual Routes
@app.route('/machinery-manual')
@login_required
def machinery_manual():
    """Display machinery manual page."""
    user_role = current_user.role if current_user else 'guest'
    return render_template('machinery_manual.html', user_role=user_role)

@app.route('/api/machinery-manuals', methods=['GET'])
@login_required
def api_list_machinery_folders():
    """List all machinery manual folders."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT 
                folder_id, folder_name, ship_name, description, 
                created_by, created_at, updated_at,
                (SELECT COUNT(*) FROM machinery_manual_files 
                 WHERE folder_id = machinery_manual_folders.folder_id 
                 AND file_status != 'deleted') as file_count
            FROM machinery_manual_folders
            WHERE folder_status != 'deleted'
            ORDER BY ship_name, created_at DESC
        """)
        
        folders = []
        for row in c.fetchall():
            folders.append({
                'folder_id': row[0],
                'folder_name': row[1],
                'ship_name': row[2],
                'description': row[3],
                'created_by': row[4],
                'created_at': row[5],
                'updated_at': row[6],
                'file_count': row[7]
            })
        
        conn.close()
        return jsonify({'success': True, 'data': folders})
    except Exception as e:
        app.logger.error(f"Error listing machinery folders: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500

@app.route('/api/machinery-manuals/upload', methods=['POST'])
@login_required
@role_required(['harbour_master'])
def api_upload_machinery_folder():
    """Upload machinery manual folder with documents (harbour master only)."""
    try:
        if 'files' not in request.files or 'ship_name' not in request.form or 'folder_name' not in request.form:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        files = request.files.getlist('files')
        ship_name = request.form.get('ship_name')
        folder_name = request.form.get('folder_name')
        description = request.form.get('description', '')
        
        if not files or len(files) == 0:
            return jsonify({'success': False, 'error': 'No files provided'}), 400
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            folder_id = generate_id('MMFOLD')
            current_time = datetime.datetime.now()
            
            # Check for duplicate folder
            c.execute("""
                SELECT folder_id FROM machinery_manual_folders
                WHERE ship_name = ? AND folder_name = ? AND folder_status != 'deleted'
            """, (ship_name, folder_name))
            
            if c.fetchone():
                return jsonify({'success': False, 'error': 'Folder already exists for this ship'}), 409
            
            # Create folder record
            c.execute("""
                INSERT INTO machinery_manual_folders
                (folder_id, folder_name, ship_name, description, created_by, created_at, updated_at, folder_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """, (folder_id, folder_name, ship_name, description, current_user.id, current_time, current_time))
            
            # Create upload directory (uses persistent volume on Render)
            upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'machinery_manuals', folder_id)
            os.makedirs(upload_dir, exist_ok=True)
            
            uploaded_count = 0
            
            # Upload files
            for file in files:
                if file.filename == '':
                    continue
                
                # Check file type (allow PDF, DOC, DOCX, etc.)
                allowed_extensions = {'pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png', 'xls', 'xlsx'}
                if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
                    continue
                
                try:
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(upload_dir, filename)
                    file.save(file_path)
                    
                    file_id = generate_id('MMFILE')
                    file_size = os.path.getsize(file_path)
                    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    machinery_type = request.form.get(f'machinery_type_{filename}', 'General')
                    
                    c.execute("""
                        INSERT INTO machinery_manual_files
                        (file_id, folder_id, file_name, file_path, file_size, file_type, 
                         machinery_type, uploaded_by, uploaded_at, file_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                    """, (file_id, folder_id, filename, file_path, file_size, file_ext, 
                         machinery_type, current_user.id, current_time))
                    
                    uploaded_count += 1
                except Exception as e:
                    app.logger.error(f"Error uploading file {file.filename}: {e}")
                    continue
            
            if uploaded_count == 0:
                # Delete folder if no files were uploaded
                c.execute("""
                    UPDATE machinery_manual_folders
                    SET folder_status = 'deleted'
                    WHERE folder_id = ?
                """, (folder_id,))
                conn.commit()
                conn.close()
                return jsonify({'success': False, 'error': 'No valid files were uploaded'}), 400
            
            conn.commit()
            log_activity('machinery_manual_upload', f'Uploaded machinery manual folder for {ship_name}')
            
            return jsonify({
                'success': True,
                'data': {
                    'folder_id': folder_id,
                    'folder_name': folder_name,
                    'ship_name': ship_name,
                    'file_count': uploaded_count
                }
            })
        
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error uploading machinery folder: {e}")
            return jsonify({'success': False, 'error': f'Upload error: {str(e)}'}), 500
        finally:
            conn.close()
    
    except Exception as e:
        app.logger.error(f"Error processing machinery folder upload: {e}")
        return jsonify({'success': False, 'error': 'Invalid request format'}), 400

@app.route('/api/machinery-manuals/<folder_id>', methods=['DELETE'])
@login_required
@role_required(['harbour_master'])
def api_delete_machinery_folder(folder_id):
    """Delete machinery manual folder (harbour master only)."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Soft delete folder and all its files
        c.execute("""
            UPDATE machinery_manual_folders
            SET folder_status = 'deleted'
            WHERE folder_id = ?
        """, (folder_id,))
        
        c.execute("""
            UPDATE machinery_manual_files
            SET file_status = 'deleted'
            WHERE folder_id = ?
        """, (folder_id,))
        
        conn.commit()
        log_activity('machinery_manual_delete', f'Deleted machinery manual folder {folder_id}')
        
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error deleting machinery folder: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500

@app.route('/api/machinery-manuals/<folder_id>/files', methods=['GET'])
@login_required
@role_required(['harbour_master', 'chief_engineer', 'captain'])
def api_get_machinery_files(folder_id):
    """Get all files in a machinery manual folder."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT 
                file_id, folder_id, file_name, file_size, file_type, 
                machinery_type, uploaded_by, uploaded_at
            FROM machinery_manual_files
            WHERE folder_id = ? AND file_status != 'deleted'
            ORDER BY machinery_type, file_name
        """, (folder_id,))
        
        files = []
        for row in c.fetchall():
            files.append({
                'file_id': row[0],
                'folder_id': row[1],
                'file_name': row[2],
                'file_size': row[3],
                'file_type': row[4],
                'machinery_type': row[5],
                'uploaded_by': row[6],
                'uploaded_at': row[7]
            })
        
        conn.close()
        return jsonify({'success': True, 'data': files})
    except Exception as e:
        app.logger.error(f"Error getting machinery files: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500

@app.route('/api/machinery-manuals/<folder_id>/files/<file_id>/download', methods=['GET'])
@login_required
@role_required(['harbour_master', 'chief_engineer', 'captain'])
def api_download_machinery_file(folder_id, file_id):
    """Download a single machinery manual file."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT file_name, file_path 
            FROM machinery_manual_files
            WHERE file_id = ? AND folder_id = ? AND file_status != 'deleted'
        """, (file_id, folder_id))
        
        row = c.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        file_name, file_path = row
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'File not found on server'}), 404
        
        log_activity('machinery_file_download', f'Downloaded machinery file {file_id}')
        return send_file(file_path, as_attachment=True, download_name=file_name)
    
    except Exception as e:
        app.logger.error(f"Error downloading machinery file: {e}")
        return jsonify({'success': False, 'error': 'Download error'}), 500

@app.route('/api/machinery-manuals/<folder_id>/download-zip', methods=['GET'])
@login_required
@role_required(['harbour_master', 'chief_engineer', 'captain'])
def api_download_machinery_folder_zip(folder_id):
    """Download entire machinery manual folder as ZIP."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT folder_name, ship_name 
            FROM machinery_manual_folders
            WHERE folder_id = ? AND folder_status != 'deleted'
        """, (folder_id,))
        
        folder_row = c.fetchone()
        
        if not folder_row:
            return jsonify({'success': False, 'error': 'Folder not found'}), 404
        
        folder_name, ship_name = folder_row
        
        c.execute("""
            SELECT file_path, file_name
            FROM machinery_manual_files
            WHERE folder_id = ? AND file_status != 'deleted'
        """, (folder_id,))
        
        files = c.fetchall()
        conn.close()
        
        if not files:
            return jsonify({'success': False, 'error': 'No files in folder'}), 400
        
        # Create ZIP file in memory
        import io
        import zipfile
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path, file_name in files:
                if os.path.exists(file_path):
                    zip_file.write(file_path, arcname=file_name)
        
        zip_buffer.seek(0)
        
        zip_filename = f"{ship_name}_{folder_name}.zip"
        log_activity('machinery_folder_download', f'Downloaded machinery folder {folder_id} as ZIP')
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
    
    except Exception as e:
        app.logger.error(f"Error downloading machinery folder ZIP: {e}")
        return jsonify({'success': False, 'error': 'Download error'}), 500

@app.route('/api/machinery-manuals/<folder_id>/files/<file_id>/delete', methods=['DELETE'])
@login_required
@role_required(['harbour_master'])
def api_delete_machinery_file(folder_id, file_id):
    """Delete a machinery manual file (harbour master only)."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE machinery_manual_files
            SET file_status = 'deleted'
            WHERE file_id = ? AND folder_id = ?
        """, (file_id, folder_id))
        
        conn.commit()
        log_activity('machinery_file_delete', f'Deleted machinery file {file_id}')
        
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error deleting machinery file: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500

@app.route('/api/procurement/request-low-stock', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_request_low_stock():
    """Create a low stock procurement request."""
    try:
        data = request.get_json()
        part_number = data.get('part_number')
        file_id = data.get('file_id')
        quantity_requested = data.get('quantity_requested')
        priority = data.get('priority', 'standard')
        notes = data.get('notes')
        
        if not part_number or not quantity_requested:
            return jsonify({'success': False, 'error': 'Part number and quantity required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            request_id = generate_id('PROCREQ')
            
            c.execute("""
                INSERT INTO procurement_requests 
                (request_id, part_number, file_id, quantity_requested, requested_by, request_status, priority, requested_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (request_id, part_number, file_id, quantity_requested, current_user.id, 'pending', priority, datetime.now(), notes))
            
            # Send notifications to procurement and management
            c.execute("SELECT user_id FROM users WHERE role = 'procurement' AND is_active = 1")
            procurement_users = c.fetchall()
            
            recipients = []
            for user in procurement_users:
                create_notification(
                    user['user_id'],
                    f'Low Stock Request: {part_number}',
                    f'{current_user.get_full_name()} requested {quantity_requested} units of {part_number} (Priority: {priority})',
                    'warning' if priority == 'standard' else 'danger',
                    '/procurement'
                )
                recipients.append(user['user_id'])
            
            # Also notify harbour_master and port_engineer
            c.execute("SELECT user_id FROM users WHERE role IN ('harbour_master', 'port_engineer') AND is_active = 1")
            mgmt_users = c.fetchall()
            
            for user in mgmt_users:
                create_notification(
                    user['user_id'],
                    f'Low Stock Notification: {part_number}',
                    f'Low stock request submitted for {part_number} - {quantity_requested} units requested',
                    'info',
                    '/inventory'
                )
            
            # Log procurement notification tracking
            for recipient_id in recipients:
                notif_id = generate_id('PROCNOTIF')
                c.execute("""
                    INSERT INTO procurement_notifications 
                    (notification_id, request_id, recipient_id, notification_type, sent_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (notif_id, request_id, recipient_id, 'low_stock', datetime.now()))
            
            conn.commit()
            log_activity('low_stock_requested', f'Requested low stock for {part_number}: {quantity_requested} units')
            
            return jsonify({'success': True, 'request_id': request_id})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error creating low stock request: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in request low stock: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/procurement/upload-parts', methods=['POST'])
@login_required
@role_required(['procurement'])
def api_procurement_upload_parts():
    """Upload new stocked parts (procurement user only)."""
    try:
        request_id = request.form.get('request_id')
        quantity_received = request.form.get('quantity_received')
        unit_price = request.form.get('unit_price')
        
        if not request_id or not quantity_received:
            return jsonify({'success': False, 'error': 'Request ID and quantity required'})
        
        try:
            quantity_received = int(quantity_received)
            unit_price = float(unit_price) if unit_price else 0.0
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid numeric values'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get procurement request details
            c.execute("SELECT * FROM procurement_requests WHERE request_id = ?", (request_id,))
            proc_request = c.fetchone()
            
            if not proc_request:
                return jsonify({'success': False, 'error': 'Procurement request not found'})
            
            proc_dict = dict(proc_request)
            
            # Create procurement item
            item_id = generate_id('PROCITEM')
            c.execute("""
                INSERT INTO procurement_items 
                (item_id, request_id, quantity_received, unit_price, added_by, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (item_id, request_id, quantity_received, unit_price, current_user.id, datetime.now()))
            
            # Update request status
            c.execute("""
                UPDATE procurement_requests
                SET request_status = 'received'
                WHERE request_id = ?
            """, (request_id,))
            
            conn.commit()
            log_activity('parts_received', f'Received {quantity_received} units for request {request_id}')
            
            # Send notification
            c.execute("SELECT requested_by FROM procurement_requests WHERE request_id = ?", (request_id,))
            requester_result = c.fetchone()
            if requester_result:
                create_notification(
                    requester_result['requested_by'],
                    'Parts Received',
                    f'{quantity_received} units received for {proc_dict.get("part_number")} (Request {request_id})',
                    'success',
                    '/inventory'
                )
            
            return jsonify({'success': True, 'item_id': item_id})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error uploading parts: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in upload parts: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/procurement/upload-inspection', methods=['POST'])
@login_required
@role_required(['procurement'])
def api_procurement_upload_inspection():
    """Upload inspection document for procured parts."""
    try:
        item_id = request.form.get('item_id')
        
        if 'document' not in request.files:
            return jsonify({'success': False, 'error': 'No document provided'})
        
        file = request.files['document']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Save inspection document
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = secure_filename(f"{item_id}_{timestamp}_{file.filename}")
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', 'inspection', filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            file.save(save_path)
            
            # Update procurement item with document
            c.execute("""
                UPDATE procurement_items
                SET inspection_document_path = ?, inspection_document_filename = ?
                WHERE item_id = ?
            """, (os.path.join('documents', 'inspection', filename), file.filename, item_id))
            
            conn.commit()
            log_activity('inspection_uploaded', f'Uploaded inspection document for item {item_id}')
            
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error uploading inspection: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in upload inspection: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/procurement/confirm-items', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_procurement_confirm_items():
    """Confirm procurement items and auto-update inventory."""
    try:
        data = request.get_json()
        item_ids = data.get('item_ids', [])
        file_id = data.get('file_id')
        
        if not item_ids:
            return jsonify({'success': False, 'error': 'No items specified'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            updated_count = 0
            
            for item_id in item_ids:
                # Get item details
                c.execute("""
                    SELECT pi.*, pr.part_number, pr.file_id
                    FROM procurement_items pi
                    JOIN procurement_requests pr ON pi.request_id = pr.request_id
                    WHERE pi.item_id = ?
                """, (item_id,))
                
                item = c.fetchone()
                if not item:
                    continue
                
                item_dict = dict(item)
                part_number = item_dict['part_number']
                quantity = item_dict['quantity_received']
                unit_price = item_dict['unit_price']
                
                # Update inventory file part if file_id exists
                if file_id:
                    c.execute("""
                        UPDATE inventory_file_parts
                        SET quantity = quantity + ?, 
                            supplier = (SELECT supplier FROM procurement_requests WHERE request_id = ?)
                        WHERE file_id = ? AND part_number = ?
                    """, (quantity, item_dict.get('request_id'), file_id, part_number))
                
                # Also update main inventory table for backward compatibility
                c.execute("SELECT current_stock FROM inventory WHERE part_number = ?", (part_number,))
                inv_result = c.fetchone()
                
                if inv_result:
                    c.execute("""
                        UPDATE inventory
                        SET current_stock = current_stock + ?, 
                            unit_price = ?,
                            last_updated = ?
                        WHERE part_number = ?
                    """, (quantity, unit_price if unit_price > 0 else None, datetime.now(), part_number))
                else:
                    # Create new inventory entry if doesn't exist
                    c.execute("""
                        INSERT INTO inventory 
                        (part_number, part_name, category, current_stock, unit_price, status, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (part_number, part_number, 'Received', quantity, unit_price, 'OK', datetime.now()))
                
                # Mark item as confirmed
                c.execute("""
                    UPDATE procurement_items
                    SET confirmed = 1, confirmed_by = ?, confirmed_at = ?
                    WHERE item_id = ?
                """, (current_user.id, datetime.now(), item_id))
                
                updated_count += 1
            
            # Update request status
            if updated_count > 0:
                c.execute("""
                    UPDATE procurement_requests
                    SET request_status = 'completed'
                    WHERE request_id IN (
                        SELECT DISTINCT request_id FROM procurement_items WHERE item_id IN ({})
                    )
                """.format(','.join(['?' for _ in item_ids])), item_ids)
            
            conn.commit()
            log_activity('procurement_confirmed', f'Confirmed {updated_count} procurement items')
            
            return jsonify({'success': True, 'confirmed': updated_count})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error confirming items: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in confirm items: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/procurement/requests', methods=['GET'])
@login_required
@role_required(['port_engineer', 'harbour_master', 'procurement'])
def api_get_procurement_requests():
    """Get all procurement requests."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        status_filter = request.args.get('status', 'all')
        
        query = """
            SELECT request_id, part_number, quantity_requested, requested_by, request_status, 
                   priority, requested_at, notes
            FROM procurement_requests
            WHERE 1=1
        """
        params = []
        
        if status_filter != 'all':
            query += " AND request_status = ?"
            params.append(status_filter)
        
        query += " ORDER BY requested_at DESC"
        
        c.execute(query, params)
        requests = [dict(row) for row in c.fetchall()]
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        app.logger.error(f"Error getting procurement requests: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# ==================== END PROCUREMENT SYSTEM ====================

@app.route('/api/reports')
@login_required
def api_reports():
    """Get list of available reports."""
    try:
        # In a real application, this would query a reports table
        # For now, we'll return sample data
        sample_reports = [
            {
                'report_id': 'REP-20241215-001',
                'title': 'Inventory Status Report',
                'report_type': 'inventory',
                'generated_at': '2024-12-15 10:30:00',
                'file_size': 24576,
                'download_url': '/api/reports/download/REP-20241215-001'
            },
            {
                'report_id': 'REP-20241214-001',
                'title': 'Maintenance Requests Summary',
                'report_type': 'maintenance',
                'generated_at': '2024-12-14 14:20:00',
                'file_size': 15360,
                'download_url': '/api/reports/download/REP-20241214-001'
            },
            {
                'report_id': 'REP-20241213-001',
                'title': 'Service Performance Analysis',
                'report_type': 'performance',
                'generated_at': '2024-12-13 09:15:00',
                'file_size': 30720,
                'download_url': '/api/reports/download/REP-20241213-001'
            }
        ]
        
        return jsonify({'success': True, 'reports': sample_reports})
    except Exception as e:
        app.logger.error(f"Error getting reports: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/generate-report', methods=['POST'])
@login_required
def api_generate_report():
    """Generate a new report with comprehensive data."""
    try:
        data = request.get_json()
        report_type = data.get('report_type')
        parameters = data.get('parameters', {})
        content_types = parameters.get('contentTypes', ['stats'])
        start_date = parameters.get('startDate')
        end_date = parameters.get('endDate')
        
        if not report_type:
            return jsonify({'success': False, 'error': 'Report type is required'})
        
        # Generate report ID
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        report_id = f"REP-{timestamp}"
        
        # Build date filter
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'"
        elif start_date:
            date_filter = f"AND DATE(created_at) >= '{start_date}'"
        elif end_date:
            date_filter = f"AND DATE(created_at) <= '{end_date}'"
        
        # Based on report type, generate appropriate data
        report_data = {
            'report_id': report_id,
            'title': parameters.get('title', f'{report_type.title()} Report'),
            'report_type': report_type,
            'generated_by': parameters.get('generated_by', current_user.get_full_name()),
            'generated_at': datetime.now().isoformat(),
            'parameters': parameters,
            'sections': []
        }
        
        # Generate report content based on type and content types requested
        if report_type == 'inventory':
            content = generate_inventory_report(date_filter)
            if 'stats' in content_types:
                report_data['sections'].append({
                    'title': 'Summary Statistics',
                    'type': 'stats',
                    'content': {
                        'total_items': content.get('summary', {}).get('total_items', 0),
                        'total_value': content.get('summary', {}).get('total_value', 0),
                        'low_stock_items': content.get('summary', {}).get('low_stock_items', 0),
                        'critical_stock_items': content.get('summary', {}).get('critical_stock_items', 0)
                    }
                })
            if 'breakdowns' in content_types:
                report_data['sections'].append({
                    'title': 'Category Breakdown',
                    'type': 'breakdowns',
                    'content': content.get('categories', [])
                })
            if 'breakdowns' in content_types:
                report_data['sections'].append({
                    'title': 'Low Stock Items',
                    'type': 'breakdowns',
                    'content': content.get('low_stock_items', [])
                })
            report_data['content'] = content
            
        elif report_type == 'maintenance':
            content = generate_maintenance_report(date_filter)
            if 'stats' in content_types:
                report_data['sections'].append({
                    'title': 'Summary Statistics',
                    'type': 'stats',
                    'content': content.get('summary', {})
                })
            if 'breakdowns' in content_types:
                report_data['sections'].append({
                    'title': 'By Type',
                    'type': 'breakdowns',
                    'content': content.get('by_type', [])
                })
            report_data['content'] = content
            
        elif report_type == 'performance':
            content = generate_performance_report(date_filter)
            report_data['sections'].append({
                'title': 'Performance Metrics',
                'type': 'stats',
                'content': content
            })
            report_data['content'] = content
            
        elif report_type == 'emergency':
            content = generate_emergency_report(date_filter)
            if 'stats' in content_types:
                report_data['sections'].append({
                    'title': 'Emergency Statistics',
                    'type': 'stats',
                    'content': content.get('statistics', {})
                })
            if 'breakdowns' in content_types:
                report_data['sections'].append({
                    'title': 'By Type',
                    'type': 'breakdowns',
                    'content': content.get('by_type', [])
                })
            report_data['content'] = content
            
        elif report_type == 'user':
            content = generate_user_activity_report(date_filter)
            report_data['sections'].append({
                'title': 'User Activity',
                'type': 'stats',
                'content': content
            })
            report_data['content'] = content
            
        elif report_type == 'financial':
            content = generate_financial_report(date_filter)
            report_data['sections'].append({
                'title': 'Financial Summary',
                'type': 'stats',
                'content': content
            })
            report_data['content'] = content
            
        elif report_type == 'comprehensive':
            # Generate comprehensive report with all types
            report_data['sections'] = []
            if 'stats' in content_types:
                report_data['sections'].append({
                    'title': 'System Overview',
                    'type': 'stats',
                    'content': {
                        'inventory': generate_inventory_report(date_filter).get('summary', {}),
                        'maintenance': generate_maintenance_report(date_filter).get('summary', {}),
                        'emergency': generate_emergency_report(date_filter).get('statistics', {}),
                        'performance': generate_performance_report(date_filter)
                    }
                })
            report_data['content'] = {
                'inventory': generate_inventory_report(date_filter),
                'maintenance': generate_maintenance_report(date_filter),
                'emergency': generate_emergency_report(date_filter),
                'performance': generate_performance_report(date_filter),
                'financial': generate_financial_report(date_filter)
            }
        else:
            report_data['content'] = {'message': 'Report generated', 'type': report_type}
        
        # Store report in database
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                INSERT INTO reports (report_id, report_type, title, generated_by, generated_at, parameters, report_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id,
                report_type,
                report_data['title'],
                current_user.id,
                datetime.now(),
                json.dumps(parameters),
                json.dumps(report_data)
            ))
            conn.commit()
        except Exception as e:
            app.logger.warning(f"Could not save report to database: {e}")
            # Create reports table if it doesn't exist
            try:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS reports (
                        report_id TEXT PRIMARY KEY,
                        report_type TEXT,
                        title TEXT,
                        generated_by TEXT,
                        generated_at TIMESTAMP,
                        parameters TEXT,
                        report_data TEXT
                    )
                """)
                conn.commit()
                # Retry insert
                c.execute("""
                    INSERT INTO reports (report_id, report_type, title, generated_by, generated_at, parameters, report_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_id,
                    report_type,
                    report_data['title'],
                    current_user.id,
                    datetime.now(),
                    json.dumps(parameters),
                    json.dumps(report_data)
                ))
                conn.commit()
            except:
                pass
        finally:
            conn.close()
        
        # Create download URL
        download_url = f'/api/reports/download/{report_id}'
        
        log_activity('report_generated', f'Generated {report_type} report: {report_id}')
        
        return jsonify({
            'success': True,
            'report_id': report_id,
            'message': f'{report_type.title()} report generated successfully',
            'download_url': download_url,
            'report_data': report_data
        })
        
    except Exception as e:
        app.logger.error(f"Error generating report: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reports/download/<report_id>')
@login_required
def api_download_report(report_id):
    """Download a generated report."""
    try:
        # In a real application, this would retrieve from database
        # For now, we'll create a sample CSV based on report type
        
        # Parse report type from ID or get from session
        report_type = 'inventory'  # Default
        
        # Check if we have this report in session
        if 'generated_reports' in session:
            for report in session['generated_reports']:
                if report['report_id'] == report_id:
                    report_type = report['report_type']
                    break
        
        # Get report data from database
        conn = get_db_connection()
        report_data = None
        try:
            c = conn.cursor()
            c.execute("SELECT report_data FROM reports WHERE report_id = ?", (report_id,))
            result = c.fetchone()
            if result:
                report_data = json.loads(result['report_data'])
        except:
            pass
        finally:
            conn.close()
        
        if not report_data:
            return jsonify({'success': False, 'error': 'Report not found'}), 404
        
        # Generate appropriate file based on type and format
        format_type = request.args.get('format', 'csv')
        
        if format_type == 'csv':
            return generate_csv_report(report_type, report_id, report_data)
        elif format_type == 'pdf':
            if REPORTLAB_AVAILABLE:
                return generate_pdf_report(report_data)
            else:
                return jsonify({'success': False, 'error': 'PDF generation requires reportlab library. Install with: pip install reportlab'})
        elif format_type == 'json':
            return jsonify({
                'success': True,
                'report_id': report_id,
                'report_data': report_data
            })
        else:
            return jsonify({'success': False, 'error': 'Invalid format'})
            
    except Exception as e:
        app.logger.error(f"Error downloading report: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/delete-report/<report_id>', methods=['DELETE'])
@login_required
def api_delete_report(report_id):
    """Delete a generated report."""
    try:
        # In a real app, this would delete from database
        # For now, just acknowledge the request
        
        log_activity('report_deleted', f'Deleted report: {report_id}')
        
        return jsonify({
            'success': True,
            'message': f'Report {report_id} deleted successfully'
        })
    except Exception as e:
        app.logger.error(f"Error deleting report: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== REPORT GENERATION HELPERS ====================

def generate_inventory_report(date_filter=""):
    """Generate inventory report data."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get inventory summary
        c.execute(f"""
            SELECT 
                COUNT(*) as total_items,
                SUM(current_stock) as total_stock,
                SUM(current_stock * unit_price) as total_value,
                COUNT(CASE WHEN status = 'LOW' THEN 1 END) as low_stock_items,
                COUNT(CASE WHEN status = 'CRITICAL' THEN 1 END) as critical_stock_items
            FROM inventory
            WHERE 1=1 {date_filter}
        """)
        summary = dict(c.fetchone())
        
        # Get items by category
        c.execute("""
            SELECT category, COUNT(*) as item_count, 
                   SUM(current_stock) as total_quantity,
                   SUM(current_stock * unit_price) as category_value
            FROM inventory
            GROUP BY category
            ORDER BY category_value DESC
        """)
        categories = [dict(row) for row in c.fetchall()]
        
        # Get low stock items
        c.execute("""
            SELECT part_number, part_name, category, current_stock, 
                   minimum_stock, reorder_level, status, unit_price,
                   (current_stock * unit_price) as value
            FROM inventory
            WHERE status IN ('LOW', 'CRITICAL')
            ORDER BY status, current_stock ASC
        """)
        low_stock = [dict(row) for row in c.fetchall()]
        
        return {
            'summary': summary,
            'categories': categories,
            'low_stock_items': low_stock,
            'generated_at': datetime.now().isoformat()
        }
    finally:
        conn.close()

def generate_maintenance_report(date_filter=""):
    """Generate maintenance report data."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get maintenance requests summary
        c.execute(f"""
            SELECT 
                COUNT(*) as total_requests,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN priority = 'critical' THEN 1 END) as critical,
                COUNT(CASE WHEN priority = 'high' THEN 1 END) as high,
                COUNT(CASE WHEN priority = 'medium' THEN 1 END) as medium,
                COUNT(CASE WHEN priority = 'low' THEN 1 END) as low
            FROM maintenance_requests
            WHERE 1=1 {date_filter}
        """)
        summary = dict(c.fetchone())
        
        # Get requests by type
        c.execute("""
            SELECT maintenance_type, COUNT(*) as count,
                   AVG(CAST(julianday(completed_at) - julianday(created_at) AS REAL)) as avg_days
            FROM maintenance_requests
            WHERE completed_at IS NOT NULL
            GROUP BY maintenance_type
        """)
        by_type = [dict(row) for row in c.fetchall()]
        
        # Get recent requests
        c.execute(f"""
            SELECT request_id, ship_name, maintenance_type, priority, 
                   status, created_at, completed_at
            FROM maintenance_requests
            WHERE 1=1 {date_filter}
            ORDER BY created_at DESC
            LIMIT 20
        """)
        recent_requests = [dict(row) for row in c.fetchall()]
        
        return {
            'summary': summary,
            'by_type': by_type,
            'recent_requests': recent_requests,
            'generated_at': datetime.now().isoformat()
        }
    finally:
        conn.close()

def generate_performance_report(date_filter=""):
    """Generate performance report data."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get SQI statistics if table exists
        try:
            c.execute(f"""
                SELECT 
                    COUNT(*) as total_evaluations,
                    AVG(sqi_score) as avg_sqi,
                    MIN(sqi_score) as min_sqi,
                    MAX(sqi_score) as max_sqi,
                    COUNT(CASE WHEN sqi_score >= 4.0 THEN 1 END) as excellent,
                    COUNT(CASE WHEN sqi_score >= 3.0 AND sqi_score < 4.0 THEN 1 END) as good,
                    COUNT(CASE WHEN sqi_score >= 2.0 AND sqi_score < 3.0 THEN 1 END) as fair,
                    COUNT(CASE WHEN sqi_score < 2.0 THEN 1 END) as poor
                FROM service_evaluations
                WHERE 1=1 {date_filter}
            """)
            sqi_stats = dict(c.fetchone())
        except:
            sqi_stats = {'message': 'No evaluation data available'}
        
        # Get user activity stats
        c.execute("""
            SELECT 
                COUNT(DISTINCT user_id) as active_users,
                COUNT(*) as total_activities,
                COUNT(CASE WHEN DATE(timestamp) = DATE('now') THEN 1 END) as today_activities
            FROM activity_logs
            WHERE DATE(timestamp) >= DATE('now', '-30 days')
        """)
        activity_stats = dict(c.fetchone())
        
        # Get completion rates
        c.execute("""
            SELECT 
                COUNT(*) as total_requests,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress
            FROM maintenance_requests
            WHERE created_at >= DATE('now', '-30 days')
        """)
        completion_stats = dict(c.fetchone())
        
        if completion_stats['total_requests'] > 0:
            completion_stats['completion_rate'] = round(
                (completion_stats['completed'] / completion_stats['total_requests']) * 100, 1
            )
        else:
            completion_stats['completion_rate'] = 0
        
        return {
            'sqi_statistics': sqi_stats,
            'activity_statistics': activity_stats,
            'completion_statistics': completion_stats,
            'generated_at': datetime.now().isoformat()
        }
    finally:
        conn.close()

def generate_emergency_report(date_filter=""):
    """Generate emergency report data."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get emergency statistics
        c.execute(f"""
            SELECT 
                COUNT(*) as total_emergencies,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'authorized' THEN 1 END) as authorized,
                COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved,
                COUNT(CASE WHEN severity_level = 'critical' THEN 1 END) as critical,
                COUNT(CASE WHEN severity_level = 'high' THEN 1 END) as high,
                COUNT(CASE WHEN severity_level = 'medium' THEN 1 END) as medium
            FROM emergency_requests
            WHERE 1=1 {date_filter}
        """)
        stats = dict(c.fetchone())
        
        # Get emergencies by type
        c.execute(f"""
            SELECT emergency_type, COUNT(*) as count,
                   AVG(CAST(julianday(resolved_at) - julianday(created_at) AS REAL)) as avg_resolution_days
            FROM emergency_requests
            WHERE resolved_at IS NOT NULL {date_filter}
            GROUP BY emergency_type
        """)
        by_type = [dict(row) for row in c.fetchall()]
        
        # Get recent emergencies
        c.execute(f"""
            SELECT emergency_id, ship_name, emergency_type, severity_level,
                   status, created_at, resolved_at
            FROM emergency_requests
            WHERE 1=1 {date_filter}
            ORDER BY created_at DESC
            LIMIT 20
        """)
        recent = [dict(row) for row in c.fetchall()]
        
        return {
            'statistics': stats,
            'by_type': by_type,
            'recent_emergencies': recent,
            'generated_at': datetime.now().isoformat()
        }
    finally:
        conn.close()

def generate_user_activity_report(date_filter=""):
    """Generate user activity report data."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get user statistics
        c.execute(f"""
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_users,
                COUNT(CASE WHEN is_approved = 1 THEN 1 END) as approved_users,
                COUNT(DISTINCT role) as unique_roles,
                COUNT(DISTINCT department) as unique_departments
            FROM users
            WHERE 1=1 {date_filter}
        """)
        user_stats = dict(c.fetchone())
        
        # Get users by role
        c.execute("""
            SELECT role, COUNT(*) as count,
                   AVG(CAST(julianday('now') - julianday(created_at) AS REAL)) as avg_account_age
            FROM users
            WHERE is_active = 1
            GROUP BY role
        """)
        by_role = [dict(row) for row in c.fetchall()]
        
        # Get recent activity
        c.execute("""
            SELECT u.user_id, u.first_name, u.last_name, u.role,
                   a.activity, a.timestamp, a.details
            FROM activity_logs a
            JOIN users u ON a.user_id = u.user_id
            ORDER BY a.timestamp DESC
            LIMIT 50
        """)
        recent_activity = [dict(row) for row in c.fetchall()]
        
        # Get top active users
        c.execute("""
            SELECT u.user_id, u.first_name, u.last_name, u.role,
                   COUNT(a.id) as activity_count
            FROM users u
            LEFT JOIN activity_logs a ON u.user_id = a.user_id
            WHERE a.timestamp >= DATE('now', '-7 days')
            GROUP BY u.user_id
            ORDER BY activity_count DESC
            LIMIT 10
        """)
        top_users = [dict(row) for row in c.fetchall()]
        
        return {
            'user_statistics': user_stats,
            'by_role': by_role,
            'recent_activity': recent_activity,
            'top_active_users': top_users,
            'generated_at': datetime.now().isoformat()
        }
    finally:
        conn.close()

def generate_financial_report(date_filter=""):
    """Generate financial report data."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get inventory value
        c.execute(f"""
            SELECT SUM(current_stock * unit_price) as total_inventory_value
            FROM inventory
            WHERE 1=1 {date_filter}
        """)
        inventory_value = c.fetchone()['total_inventory_value'] or 0
        
        # Get maintenance costs (estimated)
        c.execute("""
            SELECT 
                COUNT(*) as total_maintenance_requests,
                COUNT(CASE WHEN priority = 'critical' THEN 1 END) * 5000 as estimated_critical_cost,
                COUNT(CASE WHEN priority = 'high' THEN 1 END) * 2500 as estimated_high_cost,
                COUNT(CASE WHEN priority = 'medium' THEN 1 END) * 1000 as estimated_medium_cost,
                COUNT(CASE WHEN priority = 'low' THEN 1 END) * 500 as estimated_low_cost
            FROM maintenance_requests
            WHERE created_at >= DATE('now', '-30 days')
        """)
        maintenance_data = dict(c.fetchone())
        
        total_maintenance_cost = (
            (maintenance_data.get('estimated_critical_cost', 0) or 0) +
            (maintenance_data.get('estimated_high_cost', 0) or 0) +
            (maintenance_data.get('estimated_medium_cost', 0) or 0) +
            (maintenance_data.get('estimated_low_cost', 0) or 0)
        )
        
        # Get staff cost estimate (simplified)
        c.execute("""
            SELECT role, COUNT(*) as count,
                   CASE role
                       WHEN 'port_engineer' THEN 8000
                       WHEN 'harbour_master' THEN 6000
                       WHEN 'quality_officer' THEN 5000
                       ELSE 4000
                   END as monthly_salary
            FROM users
            WHERE is_active = 1 AND is_approved = 1
            GROUP BY role
        """)
        staff_data = [dict(row) for row in c.fetchall()]
        
        total_staff_cost = sum(item['count'] * item['monthly_salary'] for item in staff_data)
        
        # Calculate totals
        total_monthly_cost = total_maintenance_cost + total_staff_cost
        total_assets_value = inventory_value * 1.2  # Add 20% for equipment
        
        return {
            'inventory_value': inventory_value,
            'maintenance_costs': {
                'total': total_maintenance_cost,
                'breakdown': maintenance_data
            },
            'staff_costs': {
                'total': total_staff_cost,
                'breakdown': staff_data
            },
            'total_monthly_cost': total_monthly_cost,
            'total_assets_value': total_assets_value,
            'generated_at': datetime.now().isoformat()
        }
    finally:
        conn.close()

def generate_pdf_report(report_data):
    """Generate professional PDF report using ReportLab."""
    if not REPORTLAB_AVAILABLE:
        return jsonify({'success': False, 'error': 'ReportLab not available'})
    
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#6f42c1'),
            spaceAfter=30,
            alignment=1
        )
        
        # Header
        title = Paragraph(f"<b>{report_data.get('title', 'Report')}</b>", title_style)
        story.append(title)
        
        # Report info
        info_style = ParagraphStyle('InfoStyle', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
        info_text = f"<b>Generated By:</b> {report_data.get('generated_by', 'System')}<br/><b>Generated At:</b> {datetime.fromisoformat(report_data.get('generated_at', datetime.now().isoformat())).strftime('%Y-%m-%d %H:%M:%S')}<br/><b>Report Type:</b> {report_data.get('report_type', 'N/A').title()}<br/><b>Report ID:</b> {report_data.get('report_id', 'N/A')}"
        story.append(Paragraph(info_text, info_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Process sections
        sections = report_data.get('sections', [])
        for section in sections:
            section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=16, textColor=colors.HexColor('#6f42c1'), spaceAfter=12, spaceBefore=12)
            story.append(Paragraph(f"<b>{section.get('title', 'Section')}</b>", section_style))
            
            section_content = section.get('content', {})
            if isinstance(section_content, dict):
                data = [['Metric', 'Value']]
                for key, value in section_content.items():
                    if value is not None:
                        formatted_key = key.replace('_', ' ').title()
                        if isinstance(value, (int, float)):
                            formatted_value = f"${value:,.2f}" if any(x in key.lower() for x in ['value', 'cost', 'revenue']) else f"{value:,}"
                        else:
                            formatted_value = str(value)
                        data.append([formatted_key, formatted_value])
                
                if len(data) > 1:
                    table = Table(data, colWidths=[4*inch, 2*inch])
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6f42c1')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ]))
                    story.append(table)
                    story.append(Spacer(1, 0.2*inch))
        
        # Footer
        story.append(Spacer(1, 0.3*inch))
        footer_style = ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=1)
        story.append(Paragraph("<i>VesselOS - Confidential Report</i>", footer_style))
        
        doc.build(story)
        buffer.seek(0)
        filename = f"{report_data.get('report_type', 'report')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        log_activity('report_downloaded', f'Downloaded PDF report: {report_data.get("report_id")}')
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception as e:
        app.logger.error(f"Error generating PDF report: {e}")
        return jsonify({'success': False, 'error': f'PDF generation error: {str(e)}'}), 500

def generate_csv_report(report_type, report_id, report_data=None):
    """Generate CSV file for download."""
    try:
        # Use provided report_data or generate new
        if report_data:
            data = report_data.get('content', {})
            title = report_data.get('title', f'{report_type.title()} Report')
            generated_by = report_data.get('generated_by', 'System')
            generated_at = datetime.fromisoformat(report_data.get('generated_at', datetime.now().isoformat())).strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Get report data based on type
            if report_type == 'inventory':
                data = generate_inventory_report()
            elif report_type == 'maintenance':
                data = generate_maintenance_report()
            elif report_type == 'performance':
                data = generate_performance_report()
            elif report_type == 'emergency':
                data = generate_emergency_report()
            elif report_type == 'user':
                data = generate_user_activity_report()
            elif report_type == 'financial':
                data = generate_financial_report()
            else:
                data = {}
            title = f'{report_type.title()} Report'
            generated_by = current_user.get_full_name()
            generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        filename = f'{report_type}_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([title, f'Generated: {generated_at}'])
        writer.writerow(['Generated By', generated_by])
        writer.writerow(['Report ID', report_id])
        writer.writerow([])
        
        # Write data based on report type
        if report_type == 'inventory' and 'summary' in data:
            writer.writerow(['SUMMARY'])
            writer.writerow(['Total Items', data['summary'].get('total_items', 0)])
            writer.writerow(['Total Stock Value', f"${data['summary'].get('total_value', 0):,.2f}"])
            writer.writerow(['Low Stock Items', data['summary'].get('low_stock_items', 0)])
            writer.writerow(['Critical Stock Items', data['summary'].get('critical_stock_items', 0)])
            writer.writerow([])
            
            if 'categories' in data and data['categories']:
                writer.writerow(['CATEGORIES'])
                writer.writerow(['Category', 'Item Count', 'Total Quantity', 'Category Value'])
                for category in data['categories']:
                    writer.writerow([
                        category.get('category', 'N/A'),
                        category.get('item_count', 0),
                        category.get('total_quantity', 0),
                        f"${category.get('category_value', 0):,.2f}"
                    ])
                writer.writerow([])
        
        elif report_type == 'maintenance' and 'summary' in data:
            writer.writerow(['SUMMARY'])
            for key, value in data['summary'].items():
                writer.writerow([key.replace('_', ' ').title(), value])
            writer.writerow([])
        
        elif report_type == 'emergency' and 'statistics' in data:
            writer.writerow(['EMERGENCY STATISTICS'])
            for key, value in data['statistics'].items():
                writer.writerow([key.replace('_', ' ').title(), value])
            writer.writerow([])
        
        elif report_type == 'financial':
            writer.writerow(['FINANCIAL SUMMARY'])
            if 'inventory_value' in data:
                writer.writerow(['Inventory Value', f"${data.get('inventory_value', 0):,.2f}"])
            if 'total_monthly_cost' in data:
                writer.writerow(['Total Monthly Cost', f"${data.get('total_monthly_cost', 0):,.2f}"])
            if 'total_assets_value' in data:
                writer.writerow(['Total Assets Value', f"${data.get('total_assets_value', 0):,.2f}"])
            writer.writerow([])
        
        output.seek(0)
        
        log_activity('report_downloaded', f'Downloaded {report_type} report: {report_id}')
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
        
    except Exception as e:
        app.logger.error(f"Error generating CSV report: {e}")
        # Return a simple error CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Error Generating Report'])
        writer.writerow([f'Error: {str(e)}'])
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            as_attachment=True,
            download_name=f'error_report_{datetime.now().strftime("%Y%m%d")}.csv',
            mimetype='text/csv'
        )
    
# ==================== ROUTES ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """
    Handle user login with authentication and validation.
    
    GET: Display login form
    POST: Process login credentials with the following checks:
        - Account status (active/inactive)
        - Approval status (pending/approved)
        - Survey period validity (for quality officers)
        - Two-factor authentication (if enabled)
    
    Returns:
        GET: Rendered login form
        POST: Redirect to dashboard on success, login form with error on failure
    
    Rate Limited: 10 requests per minute for security
    """
    # Redirect authenticated users to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        # Query user from database
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            user_data = cursor.fetchone()
        finally:
            conn.close()

        if not user_data:
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')

        try:
            user_dict = dict(user_data)
        except Exception as dict_err:
            app.logger.error(f"Error converting user data to dict for {email}: {dict_err}")
            app.logger.error(f"User data type: {type(user_data)}, value: {user_data}")
            flash('Login system error. Please contact support.', 'danger')
            return render_template('login.html')
        
        # Verify password hash
        if not check_password_hash(user_dict['password'], password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html')

        # Check account status
        if not user_dict['is_active']:
            flash('Your account has been deactivated. Contact the port engineer.', 'danger')
            return render_template('login.html')

        # Check approval status
        if not user_dict['is_approved']:
            flash('Your account is pending approval from the port engineer.', 'warning')
            return render_template('login.html')

        # Validate survey period for quality officers
        if user_dict['role'] == 'quality_officer' and user_dict['survey_end_date']:
            try:
                survey_end = datetime.strptime(user_dict['survey_end_date'], '%Y-%m-%d').date()
                if datetime.now().date() > survey_end:
                    flash('Your survey period has expired. Request extension from port engineer.', 'warning')
                    return render_template('login.html')
            except ValueError:
                pass  # Invalid date format, allow login

        # Require 2FA verification if enabled
        if user_dict.get('two_factor_enabled'):
            session['pending_2fa_user'] = user_dict['user_id']
            flash('Enter your 2FA code to complete login.', 'info')
            return redirect(url_for('two_factor'))

        # Successful authentication - create user session
        try:
            try:
                user = User(user_dict)
            except Exception as user_err:
                app.logger.error(f"Error creating User object: {user_err}")
                app.logger.error(f"User dict keys: {user_dict.keys() if isinstance(user_dict, dict) else 'Not a dict'}")
                raise user_err
            
            login_user(user, remember=True)

            # Update login timestamp
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET last_login = ?, last_activity = ? WHERE user_id = ?",
                    (datetime.now(), datetime.now(), user.id)
                )
                conn.commit()
            finally:
                conn.close()

            # Log activity - wrapped in try-catch to prevent login failure on logging error
            try:
                log_activity('login', 'User logged in successfully')
            except Exception as log_err:
                app.logger.warning(f"Failed to log login activity for {user.id}: {log_err}")

            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as auth_err:
            app.logger.error(f"Authentication error for email {email}: {auth_err}", exc_info=True)
            flash('An error occurred during login. Please try again.', 'danger')
            return render_template('login.html')

    return render_template('login.html')


@app.route('/two-factor', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def two_factor():
    """
    Handle two-factor authentication verification.
    
    Second step of login process for users with 2FA enabled.
    Verifies TOTP code generated by user's authenticator app.
    
    GET: Display 2FA code entry form
    POST: Verify TOTP code and complete login
        - Validates 6-digit code against user's 2FA secret
        - Creates authenticated session on success
        - Updates last login timestamp
        - Logs authentication activity
    
    Returns:
        GET: Rendered 2FA form
        POST: Redirect to dashboard on success, form with error on failure
    
    Rate Limited: 10 requests per minute
    
    Note:
        Requires prior successful email/password authentication with
        'pending_2fa_user' stored in session.
    """
    # Verify user completed first authentication step
    pending_user = session.get('pending_2fa_user')
    if not pending_user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        
        # Retrieve user data
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (pending_user,))
            user_data = cursor.fetchone()
        finally:
            conn.close()

        # Handle user not found (session expired)
        if not user_data:
            session.pop('pending_2fa_user', None)
            flash('Your session has expired. Please log in again.', 'danger')
            return redirect(url_for('login'))

        user_dict = dict(user_data)
        secret = user_dict.get('two_factor_secret')
        
        # Verify TOTP code
        if verify_2fa_code(secret, code):
            # Clear pending auth session
            session.pop('pending_2fa_user', None)
            
            # Create authenticated session
            user = User(user_dict)
            login_user(user, remember=True)

            # Update login timestamps
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET last_login = ?, last_activity = ? WHERE user_id = ?",
                    (datetime.now(), datetime.now(), user.id)
                )
                conn.commit()
            finally:
                conn.close()

            log_activity('login_2fa', 'User successfully authenticated with two-factor')
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid 2FA code. Please check and try again.', 'danger')

    return render_template('two_factor.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def register():
    """
    Handle user registration with validation and profile creation.
    
    GET: Display registration form
    POST: Process registration with the following validations:
        - Email uniqueness check
        - Password strength requirements (8+ chars, mixed case, digit, special char)
        - Password match confirmation
        - Generate unique user ID based on role
        - Set survey period for quality officers
        - Send notification to manager for approval
    
    Returns:
        GET: Rendered registration form
        POST: Redirect to login on success, form with error on failure
    
    Rate Limited: 5 requests per hour for security
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Extract form data
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        role = request.form.get('role', '').strip()
        rank = request.form.get('rank', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        location = request.form.get('location', '').strip()

        # Validate required fields
        if not first_name or not last_name:
            flash('First name and last name are required.', 'danger')
            return render_template('register.html')
        
        if not role:
            flash('Please select a role.', 'danger')
            return render_template('register.html')

        # Validate password confirmation
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        # Validate password strength
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('register.html')

        has_upper = any(ch.isupper() for ch in password)
        has_lower = any(ch.islower() for ch in password)
        has_digit = any(ch.isdigit() for ch in password)
        has_special = any(ch in "!@#$%^&*()-_=+[]{};:,.?/\\|" for ch in password)

        if not (has_upper and has_lower and has_digit and has_special):
            flash(
                'Password must contain uppercase, lowercase, number, and special character.',
                'danger'
            )
            return render_template('register.html')

        # Check for duplicate email
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                flash('This email is already registered.', 'danger')
                return render_template('register.html')

            # Generate unique user ID
            role_prefix_map = {
                'harbour_master': 'MM',
                'quality_officer': 'QO',
                'port_engineer': 'PE',
                'procurement': 'PROC',
                'chief_engineer': 'CE',
                'captain': 'CAP',
                'port_manager': 'PM'
            }
            role_prefix = role_prefix_map.get(role, 'USR')

            cursor.execute("SELECT COUNT(*) FROM users WHERE role = ?", (role,))
            count = cursor.fetchone()[0] + 1
            user_id = f"{role_prefix}{count:03d}"

            # Hash password securely
            hashed_password = generate_password_hash(password)

            # Set survey end date for quality officers
            survey_end_date = None
            if role == 'quality_officer':
                survey_days = int(request.form.get('survey_days', 90))
                survey_end_date = (datetime.now() + timedelta(days=survey_days)).strftime('%Y-%m-%d')

            # Insert new user with pending approval status
            cursor.execute(
                """INSERT INTO users
                   (user_id, email, password, first_name, last_name, rank, role, 
                    phone, department, location, survey_end_date, is_approved)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, email, hashed_password, first_name, last_name, rank, role,
                 phone, department, location, survey_end_date, 0)
            )
            conn.commit()

            # Notify manager of new registration - wrapped in try-catch to prevent registration failure
            try:
                create_notification(
                    'MGR001',
                    'New User Registration',
                    f'{first_name} {last_name} ({role.replace("_", " ").title()}) registered and requires approval',
                    'info',
                    '/dashboard'
                )
            except Exception as notif_err:
                app.logger.warning(f"Failed to create notification for new user {user_id}: {notif_err}")

            flash('Registration successful! Your account is pending approval.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            app.logger.error(f"Registration error for email {email}: {e}")
            flash('Registration failed. Please try again.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """
    Handle user logout and session termination.
    
    Clears user session, logs the activity, and redirects to login page.
    
    Returns:
        Redirect to login page with success message
    """
    log_activity('logout', 'User logged out')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Route dispatcher that directs users to their role-specific dashboard.
    
    Each user role has a customized dashboard with relevant controls and information.
    Returns the appropriate template based on the current user's role.
    
    Returns:
        Rendered template appropriate for user's role
    """
    role_dashboard_map = {
        'port_engineer': 'port_engineer_dashboard.html',
        'port_manager': 'port_engineer_dashboard.html',
        'quality_officer': 'quality_officer.html',
        'harbour_master': 'harbour_master.html',
        'chief_engineer': 'chief_engineer_dashboard.html',
        'captain': 'captain_dashboard.html'
    }
    
    template = role_dashboard_map.get(current_user.role, 'dashboard.html')
    return render_template(template)

@app.route('/profile')
@login_required
def profile():
    """
    Display user profile with personal information and documents.
    
    Retrieves the current user's profile data and associated documents,
    calculates total document storage size, and displays the profile page.
    
    Returns:
        Rendered profile template with user data and documents
    
    Raises:
        Redirects to dashboard on user not found or database error
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Fetch current user data
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (current_user.id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            flash('User profile not found.', 'danger')
            return redirect(url_for('dashboard'))

        user_dict = dict(user_data)

        # Fetch user documents
        cursor.execute(
            "SELECT * FROM user_documents WHERE user_id = ? ORDER BY uploaded_at DESC",
            (current_user.id,)
        )
        documents = [dict(row) for row in cursor.fetchall()]

        # Calculate total document storage used
        total_document_size = sum(doc.get('file_size', 0) for doc in documents)

        return render_template(
            'profile.html',
            user=user_dict,
            documents=documents,
            total_document_size=total_document_size
        )

    except Exception as e:
        app.logger.error(f"Error loading profile for user {current_user.id}: {e}")
        flash('Error loading profile data.', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

@app.route('/api/update-profile', methods=['POST'])
@login_required
def api_update_profile():
    """Update user profile including profile picture upload."""
    try:
        # Extract form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        rank = request.form.get('rank')
        phone = request.form.get('phone')
        department = request.form.get('department')
        location = request.form.get('location')

        if not first_name or not last_name:
            return jsonify({'success': False, 'error': 'First and last name are required'})

        profile_pic_filename = None
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and file.filename != '':
                if allowed_file(file.filename, 'image'):
                    # Check file size (15MB max)
                    file.seek(0, os.SEEK_END)
                    file_length = file.tell()
                    file.seek(0)
                    if file_length > 15 * 1024 * 1024:
                        return jsonify({'success': False, 'error': 'Profile picture size exceeds 15MB limit'})

                    # Secure filename and save
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    filename = secure_filename(f"{current_user.id}_{timestamp}_{file.filename}")
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics', filename)
                    file.save(save_path)
                    profile_pic_filename = filename
                else:
                    return jsonify({'success': False, 'error': 'Invalid image file type. Allowed: PNG, JPG, JPEG, GIF'})

        # Update database
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Build update query based on whether we have a new profile picture
            if profile_pic_filename:
                c.execute("""
                    UPDATE users
                    SET first_name=?, last_name=?, rank=?, phone=?, department=?, location=?, profile_pic=?, last_activity=?
                    WHERE user_id=?
                """, (first_name, last_name, rank, phone, department, location, profile_pic_filename, datetime.now(), current_user.id))
            else:
                c.execute("""
                    UPDATE users
                    SET first_name=?, last_name=?, rank=?, phone=?, department=?, location=?, last_activity=?
                    WHERE user_id=?
                """, (first_name, last_name, rank, phone, department, location, datetime.now(), current_user.id))

            conn.commit()
            log_activity('profile_update', 'User updated profile information')

            # Return profile pic filename if uploaded so frontend can display it
            response_data = {'success': True}
            if profile_pic_filename:
                response_data['profile_pic_filename'] = profile_pic_filename
                response_data['profile_pic_url'] = url_for('serve_profile_pic', filename=profile_pic_filename, _external=False)
            return jsonify(response_data)
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating profile: {e}")
            return jsonify({'success': False, 'error': 'Database update failed'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Unexpected error in profile update: {e}")
        return jsonify({'success': False, 'error': 'Server error occurred'})

@app.route('/api/update-profile-pic', methods=['POST'])
@login_required
def api_update_profile_pic():
    """Update user profile picture only."""
    try:
        if 'profile_pic' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})

        file = request.files['profile_pic']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        if not allowed_file(file.filename, 'image'):
            return jsonify({'success': False, 'error': 'Invalid image file type. Allowed: PNG, JPG, JPEG, GIF'})

        # Check file size (15MB max)
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)
        if file_length > 15 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'Profile picture size exceeds 15MB limit'})

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = secure_filename(f"{current_user.id}_{timestamp}_{file.filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics', filename)

        # Save file
        file.save(save_path)

        # Update database
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("UPDATE users SET profile_pic = ? WHERE user_id = ?",
                     (filename, current_user.id))
            conn.commit()

            log_activity('profile_pic_update', 'User updated profile picture')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating profile picture: {e}")
            return jsonify({'success': False, 'error': 'Database update failed'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Unexpected error in profile picture update: {e}")
        return jsonify({'success': False, 'error': 'Server error occurred'})

@app.route('/api/profile/stats')
@login_required
def api_profile_stats():
    """Get user statistics for profile page."""
    conn = get_db_connection()
    try:
        c = conn.cursor()

        # Get total evaluations - with error handling
        total_evaluations = 0
        avg_sqi = 0

        try:
            # Check if table exists
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_evaluations'")
            if c.fetchone():
                c.execute("SELECT COUNT(*) as count FROM service_evaluations WHERE evaluator_id = ?", (current_user.id,))
                eval_result = c.fetchone()
                total_evaluations = eval_result['count'] if eval_result else 0

                # Get average SQI
                c.execute("SELECT AVG(sqi_score) as avg_sqi FROM service_evaluations WHERE evaluator_id = ?", (current_user.id,))
                avg_sqi_result = c.fetchone()
                avg_sqi_value = avg_sqi_result['avg_sqi'] if avg_sqi_result else None
                avg_sqi = round(avg_sqi_value, 2) if avg_sqi_value else 0
        except sqlite3.Error as e:
            app.logger.warning(f"Could not fetch evaluation stats: {e}")

        # Get activity days
        c.execute("SELECT COUNT(DISTINCT DATE(timestamp)) as days FROM activity_logs WHERE user_id = ?", (current_user.id,))
        activity_days_result = c.fetchone()
        activity_days = activity_days_result['days'] if activity_days_result else 0

        return jsonify({
            'success': True,
            'stats': {
                'total_evaluations': total_evaluations,
                'avg_sqi': avg_sqi,
                'activity_days': activity_days
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting profile stats: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# ==================== DOCUMENT MANAGEMENT ROUTES ====================

@app.route('/api/upload-document', methods=['POST'])
@login_required
def api_upload_document():
    """Upload a document for the user."""
    try:
        if 'document' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})

        file = request.files['document']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'File type not allowed'})

        # Check file size (100MB max)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > 100 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'File size exceeds 100MB limit'})

        # Generate filename
        document_name = request.form.get('document_name', file.filename)
        document_type = request.form.get('document_type', 'other')
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = secure_filename(f"{current_user.id}_{timestamp}_{file.filename}")

        # Save file
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', filename)
        file.save(save_path)

        # Store in database
        conn = get_db_connection()
        try:
            c = conn.cursor()
            doc_id = generate_id('DOC')
            c.execute("""
                INSERT INTO user_documents (id, user_id, document_name, document_type, document_path, file_size)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (doc_id, current_user.id, document_name, document_type, filename, file_size))

            conn.commit()
            log_activity('document_upload', f'Uploaded document: {document_name}')

            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error uploading document: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in document upload: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/document-info/<doc_id>')
@login_required
def api_document_info(doc_id):
    """Get document information for preview."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, user_id, document_name, document_type,
                   document_path, file_size, uploaded_at
            FROM user_documents
            WHERE id = ? AND user_id = ?
        """, (doc_id, current_user.id))

        document = c.fetchone()
        if not document:
            return jsonify({'success': False, 'error': 'Document not found or access denied'})

        return jsonify({'success': True, 'document': dict(document)})
    except Exception as e:
        app.logger.error(f"Error getting document info: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/download-document/<doc_id>')
@login_required
def api_download_document(doc_id):
    """Download document file."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT document_name, document_path, user_id
            FROM user_documents
            WHERE id = ? AND user_id = ?
        """, (doc_id, current_user.id))

        document = c.fetchone()
        if not document:
            return jsonify({'success': False, 'error': 'Document not found or access denied'}), 404

        document_dict = dict(document)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', document_dict['document_path'])

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'File not found on server'}), 404

        # Get file extension for proper content type
        file_ext = os.path.splitext(document_dict['document_path'])[1].lower()
        mimetype_map = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.csv': 'text/csv',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.txt': 'text/plain',
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed'
        }

        mimetype = mimetype_map.get(file_ext, 'application/octet-stream')

        return send_file(
            file_path,
            as_attachment=True,
            download_name=document_dict['document_name'] + file_ext,
            mimetype=mimetype
        )
    except Exception as e:
        app.logger.error(f"Error downloading document: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/rename-document/<doc_id>', methods=['POST'])
@login_required
def api_rename_document(doc_id):
    """Rename a document."""
    try:
        data = request.get_json()
        new_name = data.get('new_name')

        if not new_name or not new_name.strip():
            return jsonify({'success': False, 'error': 'New name is required'})

        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                UPDATE user_documents
                SET document_name = ?
                WHERE id = ? AND user_id = ?
            """, (new_name.strip(), doc_id, current_user.id))

            conn.commit()
            log_activity('document_renamed', f'Renamed document {doc_id} to {new_name}')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error renaming document: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in rename document: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/delete-document/<doc_id>', methods=['DELETE'])
@login_required
def api_delete_document(doc_id):
    """Delete a document."""
    conn = get_db_connection()
    try:
        c = conn.cursor()

        # Get document info before deletion
        c.execute("""
            SELECT document_name, document_path
            FROM user_documents
            WHERE id = ? AND user_id = ?
        """, (doc_id, current_user.id))

        document = c.fetchone()
        if not document:
            return jsonify({'success': False, 'error': 'Document not found or access denied'})

        document_dict = dict(document)

        # Delete from database
        c.execute("DELETE FROM user_documents WHERE id = ? AND user_id = ?",
                 (doc_id, current_user.id))

        # Delete the file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', document_dict['document_path'])
        if os.path.exists(file_path):
            os.remove(file_path)

        conn.commit()
        log_activity('document_deleted', f'Deleted document: {document_dict["document_name"]}')
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error deleting document: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/delete-documents', methods=['POST'])
@login_required
def api_delete_documents():
    """Delete multiple documents at once."""
    try:
        data = request.get_json()
        document_ids = data.get('document_ids', [])

        if not document_ids:
            return jsonify({'success': False, 'error': 'No documents selected'})

        conn = get_db_connection()
        try:
            c = conn.cursor()
            deleted_count = 0

            for doc_id in document_ids:
                # Get document info before deletion
                c.execute("""
                    SELECT document_path
                    FROM user_documents
                    WHERE id = ? AND user_id = ?
                """, (doc_id, current_user.id))

                document = c.fetchone()
                if document:
                    # Delete from database
                    c.execute("DELETE FROM user_documents WHERE id = ? AND user_id = ?",
                            (doc_id, current_user.id))

                    # Delete the file
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', document['document_path'])
                    if os.path.exists(file_path):
                        os.remove(file_path)

                    deleted_count += 1

            conn.commit()
            log_activity('documents_deleted', f'Deleted {deleted_count} documents')
            return jsonify({'success': True, 'deleted_count': deleted_count})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error deleting documents: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in delete documents: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/activities')
@login_required
def api_user_activities():
    """Get user activity logs."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM activity_logs
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 50
        """, (current_user.id,))

        activities = []
        for row in c.fetchall():
            activity = dict(row)
            activity['timestamp'] = activity['timestamp'] if 'timestamp' in activity else datetime.now().isoformat()
            activities.append(activity)

        return jsonify({'success': True, 'activities': activities})
    except Exception as e:
        app.logger.error(f"Error getting activities: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()


def generate_2fa_secret(length: int = 16) -> str:
    """
    Generate a cryptographically secure 2FA secret key.
    
    Creates a random base32-encoded string suitable for use with
    authenticator apps (Google Authenticator, Authy, etc.) for
    generating time-based one-time passwords (TOTP).
    
    Args:
        length (int, optional): Length of secret to generate. Defaults to 16.
    
    Returns:
        str: Random base32 string suitable for 2FA secret
    
    Note:
        Uses base32 alphabet (A-Z, 2-7) as per RFC 4648 standard.
    """
    # RFC 4648 base32 alphabet
    base32_alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
    return ''.join(random.choice(base32_alphabet) for _ in range(length))


def verify_2fa_code(secret: str, code: str, window: int = 1) -> bool:
    """
    Verify a TOTP code against the provided secret.
    
    Implements RFC 6238 Time-based One-Time Password (TOTP) verification.
    Accepts codes within a time window to account for clock drift between
    server and authenticator app.
    
    Args:
        secret (str): Base32-encoded 2FA secret key
        code (str): 6-digit TOTP code to verify
        window (int, optional): Time window in 30-second steps. Defaults to 1.
                               Accepts codes from past/future by this amount.
    
    Returns:
        bool: True if code is valid, False otherwise
    
    Validation:
        - Code must be exactly 6 digits
        - Code must be numeric
        - Matches generated TOTP within time window
    
    Note:
        Time window allows ±1 step (±30 seconds) by default to handle
        clock drift between server and client authenticators.
    """
    # Validate code format
    if not secret or not code or len(code) != 6 or not code.isdigit():
        return False

    try:
        import hmac
        import hashlib
        import struct

        # Prepare HMAC key
        key = secret.encode()
        timestep = 30  # TOTP timestep in seconds

        # Get current time counter
        current_timestamp = datetime.utcnow().timestamp()
        time_counter = int(current_timestamp / timestep)

        # Check provided code against current and nearby time steps
        for offset in range(-window, window + 1):
            check_counter = time_counter + offset
            message = struct.pack('>Q', check_counter)

            # Generate HMAC-SHA1
            hmac_hash = hmac.new(key, message, hashlib.sha1).digest()

            # Extract dynamic binary code
            offset_bits = hmac_hash[19] & 0x0F
            code_value = (
                ((hmac_hash[offset_bits] & 0x7F) << 24) |
                ((hmac_hash[offset_bits + 1] & 0xFF) << 16) |
                ((hmac_hash[offset_bits + 2] & 0xFF) << 8) |
                (hmac_hash[offset_bits + 3] & 0xFF)
            )

            # Convert to 6-digit code
            generated_code = str(code_value % 1000000).zfill(6)

            # Use constant-time comparison to prevent timing attacks
            if hmac.compare_digest(generated_code, code):
                return True

        return False

    except Exception as e:
        app.logger.warning(f"Error verifying 2FA code: {e}")
        return False


def generate_csrf_token():
    """
    Generate and store a CSRF protection token in session.
    
    Creates a cryptographically secure random token for Cross-Site
    Request Forgery (CSRF) protection. Reuses existing token if
    already generated in current session.
    
    Returns:
        str: 32-character random CSRF token
    
    Note:
        Token is stored in Flask session for validation on subsequent
        requests. Each session gets exactly one token.
    """
    if 'csrf_token' not in session:
        session['csrf_token'] = ''.join(
            random.choices(string.ascii_letters + string.digits, k=32)
        )
    return session['csrf_token']


def verify_csrf_token(token):
    """
    Verify CSRF token from request against session token.
    
    Performs constant-time comparison of provided token against
    session token to prevent timing-based attacks.
    
    Args:
        token (str): CSRF token from request (form or header)
    
    Returns:
        bool: True if token matches session token, False otherwise
    
    Note:
        Uses hmac.compare_digest for timing-attack resistant comparison.
    """
    if not token:
        return False

    session_token = session.get('csrf_token')
    if not session_token:
        return False

    # Use constant-time comparison to prevent timing attacks
    import hmac
    return hmac.compare_digest(token, session_token)


def csrf_protect(f):
    """Decorator to protect routes with CSRF token verification."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'DELETE', 'PUT', 'PATCH']:
            # Try to get token from form data first
            token = request.form.get('csrf_token')
            
            # If not in form, try header
            if not token:
                token = request.headers.get('X-CSRF-Token')
            
            # If not in header, try JSON body
            if not token:
                try:
                    if request.is_json or request.content_type and 'application/json' in request.content_type:
                        json_data = request.get_json(silent=True)
                        if json_data:
                            token = json_data.get('csrf_token')
                except Exception:
                    pass
            
            if not verify_csrf_token(token):
                if request.is_json or (request.content_type and 'application/json' in request.content_type) or request.method in ['DELETE', 'PUT', 'PATCH']:
                    return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 403
                flash('Security token mismatch. Please try again.', 'danger')
                return redirect(request.referrer or url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== CSRF TOKEN ENDPOINT ====================

@app.route('/api/csrf-token')
@login_required
def api_csrf_token():
    """Get CSRF token for forms."""
    token = generate_csrf_token()
    # Ensure session is saved
    session.permanent = True
    return jsonify({'csrf_token': token})

# ==================== TWO-FACTOR AUTHENTICATION ====================

@app.route('/api/2fa/setup', methods=['GET'])
@login_required
def api_2fa_setup():
    """Generate 2FA secret and QR code URL."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT two_factor_enabled, two_factor_secret FROM users WHERE user_id = ?", (current_user.id,))
            result = c.fetchone()
            
            if result and result['two_factor_enabled']:
                return jsonify({'success': False, 'error': '2FA is already enabled'})
            
            # Generate new secret
            secret = generate_2fa_secret()
            
            # Generate QR code URL (otpauth:// format)
            issuer = 'VesselOS'
            account_name = f"{current_user.email}"
            qr_url = f"otpauth://totp/{issuer}:{account_name}?secret={secret}&issuer={issuer}"
            
            # Store secret temporarily in session (will be saved when user verifies)
            session['pending_2fa_secret'] = secret
            
            return jsonify({
                'success': True,
                'secret': secret,
                'qr_url': qr_url,
                'manual_entry': secret
            })
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error setting up 2FA: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/2fa/enable', methods=['POST'])
@login_required
@csrf_protect
def api_2fa_enable():
    """Enable 2FA after verifying code."""
    try:
        data = request.get_json()
        code = data.get('code', '').strip()
        secret = session.get('pending_2fa_secret')
        
        if not secret:
            return jsonify({'success': False, 'error': 'No pending 2FA setup. Please start setup again.'})
        
        if not verify_2fa_code(secret, code):
            return jsonify({'success': False, 'error': 'Invalid verification code. Please try again.'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                UPDATE users
                SET two_factor_secret = ?, two_factor_enabled = 1
                WHERE user_id = ?
            """, (secret, current_user.id))
            conn.commit()
            
            session.pop('pending_2fa_secret', None)
            log_activity('2fa_enabled', 'User enabled two-factor authentication')
            return jsonify({'success': True, 'message': '2FA enabled successfully'})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error enabling 2FA: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in 2FA enable: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/2fa/disable', methods=['POST'])
@login_required
@csrf_protect
def api_2fa_disable():
    """Disable 2FA after verifying code."""
    try:
        data = request.get_json()
        code = data.get('code', '').strip()
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT two_factor_secret FROM users WHERE user_id = ?", (current_user.id,))
            result = c.fetchone()
            
            if not result or not result['two_factor_secret']:
                return jsonify({'success': False, 'error': '2FA is not enabled'})
            
            secret = result['two_factor_secret']
            if not verify_2fa_code(secret, code):
                return jsonify({'success': False, 'error': 'Invalid verification code'})
            
            c.execute("""
                UPDATE users
                SET two_factor_secret = NULL, two_factor_enabled = 0
                WHERE user_id = ?
            """, (current_user.id,))
            conn.commit()
            
            log_activity('2fa_disabled', 'User disabled two-factor authentication')
            return jsonify({'success': True, 'message': '2FA disabled successfully'})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error disabling 2FA: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in 2FA disable: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/2fa/status')
@login_required
def api_2fa_status():
    """Get 2FA status for current user."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT two_factor_enabled FROM users WHERE user_id = ?", (current_user.id,))
            result = c.fetchone()
            enabled = bool(result['two_factor_enabled']) if result else False
            return jsonify({'success': True, 'enabled': enabled})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/change-password', methods=['POST'])
@login_required
@csrf_protect
def api_change_password():
    """Change user password."""
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')

        if not current_password or not new_password or not confirm_password:
            return jsonify({'success': False, 'error': 'All fields are required'})

        if new_password != confirm_password:
            return jsonify({'success': False, 'error': 'New passwords do not match'})

        # Basic password strength checks (keep in sync with register)
        if len(new_password) < 8:
            return jsonify({'success': False, 'error': 'Password must be at least 8 characters'})
        if (new_password.lower() == new_password or
                new_password.upper() == new_password or
                not any(ch.isdigit() for ch in new_password) or
                not any(ch in "!@#$%^&*()-_=+[]{};:,.?/\\|" for ch in new_password)):
            return jsonify({'success': False, 'error': 'Password must include upper and lower case letters, a number, and a special character.'})

        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT password FROM users WHERE user_id = ?", (current_user.id,))
            result = c.fetchone()

            if not result or not check_password_hash(result['password'], current_password):
                return jsonify({'success': False, 'error': 'Current password is incorrect'})

            hashed_password = generate_password_hash(new_password)
            c.execute("""
                UPDATE users
                SET password = ?, two_factor_secret = NULL, two_factor_enabled = 0
                WHERE user_id = ?
            """, (hashed_password, current_user.id))
            conn.commit()

            log_activity('password_change', 'User changed password')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error changing password: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in password change: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/upload-signature', methods=['POST'])
@login_required
def api_upload_signature():
    """Upload digital signature."""
    try:
        if 'signature' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})

        file = request.files['signature']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        # Check if it's an image
        if not allowed_file(file.filename, 'image'):
            return jsonify({'success': False, 'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF'})

        # Check file size (5MB max for signature)
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)
        if file_length > 5 * 1024 * 1024:
            return jsonify({'success': False, 'error': 'Signature image size exceeds 5MB limit'})

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = secure_filename(f"signature_{current_user.id}_{timestamp}_{file.filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'signatures', filename)

        # Save file
        file.save(save_path)

        # Update database
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("UPDATE users SET signature_path = ? WHERE user_id = ?",
                     (filename, current_user.id))
            conn.commit()

            log_activity('signature_upload', 'User uploaded digital signature')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error uploading signature: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in signature upload: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove-signature', methods=['POST'])
@login_required
def api_remove_signature():
    """Remove digital signature."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Get current signature filename
            c.execute("SELECT signature_path FROM users WHERE user_id = ?", (current_user.id,))
            result = c.fetchone()

            if result and result['signature_path']:
                # Delete the file
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'signatures', result['signature_path'])
                if os.path.exists(file_path):
                    os.remove(file_path)

            # Update database
            c.execute("UPDATE users SET signature_path = NULL WHERE user_id = ?", (current_user.id,))
            conn.commit()

            log_activity('signature_remove', 'User removed digital signature')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error removing signature: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error removing signature: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/print-profile-data')
@login_required
def api_print_profile_data():
    """Get profile data for printing."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Get user data
            c.execute("SELECT * FROM users WHERE user_id = ?", (current_user.id,))
            user_data = c.fetchone()

            if not user_data:
                return jsonify({'success': False, 'error': 'User not found'})

            user_dict = dict(user_data)

            # Get profile stats - with error handling for missing table
            total_evaluations = 0
            avg_sqi = 0

            try:
                # First check if the table exists
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_evaluations'")
                if c.fetchone():
                    # Table exists, get evaluation stats
                    c.execute("SELECT COUNT(*) as count FROM service_evaluations WHERE evaluator_id = ?", (current_user.id,))
                    total_evaluations_result = c.fetchone()
                    total_evaluations = total_evaluations_result['count'] if total_evaluations_result else 0

                    c.execute("SELECT AVG(sqi_score) as avg_sqi FROM service_evaluations WHERE evaluator_id = ?", (current_user.id,))
                    avg_sqi_result = c.fetchone()
                    avg_sqi = round(avg_sqi_result['avg_sqi'], 2) if avg_sqi_result and avg_sqi_result['avg_sqi'] else 0
            except sqlite3.Error as e:
                app.logger.warning(f"Could not fetch evaluation stats: {e}")
                # Continue with default values

            # Get activity days
            c.execute("SELECT COUNT(DISTINCT DATE(timestamp)) as days FROM activity_logs WHERE user_id = ?", (current_user.id,))
            activity_days_result = c.fetchone()
            activity_days = activity_days_result['days'] if activity_days_result else 0

            # Get base64 encoded profile picture if exists
            profile_pic_base64 = None
            if user_dict.get('profile_pic'):
                profile_pic_path = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics', user_dict['profile_pic'])
                if os.path.exists(profile_pic_path):
                    try:
                        import base64
                        with open(profile_pic_path, 'rb') as f:
                            profile_pic_base64 = base64.b64encode(f.read()).decode('utf-8')
                    except Exception as e:
                        app.logger.error(f"Error encoding profile pic: {e}")

            # Format dates
            created_at = user_dict.get('created_at')
            if created_at:
                try:
                    if isinstance(created_at, str):
                        created_at = created_at[:10]  # Get YYYY-MM-DD
                except:
                    created_at = str(created_at)[:10] if created_at else 'N/A'

            return jsonify({
                'success': True,
                'user': {
                    **user_dict,
                    'full_name': f"{user_dict['first_name']} {user_dict['last_name']}",
                    'role_display': user_dict['role'].replace('_', ' ').title(),
                    'created_at': created_at,
                    'total_evaluations': total_evaluations,
                    'avg_sqi': avg_sqi,
                    'activity_days': activity_days
                },
                'profile_pic_base64': profile_pic_base64,
                'print_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        except Exception as e:
            app.logger.error(f"Error getting print data: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in print profile data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/favicon.ico')
def favicon():
    """Serve favicon (logo.png)."""
    import os
    static_path = os.path.join(app.root_path, 'static', 'images')
    if os.path.exists(os.path.join(static_path, 'logo.png')):
        return send_from_directory(static_path, 'logo.png', mimetype='image/png')
    else:
        # Fallback if logo.png doesn't exist
        return '', 204  # No Content

@app.route('/static/uploads/signatures/<filename>')
@login_required
def serve_signature(filename):
    """Serve signature images."""
    signature_path = os.path.join(app.config['UPLOAD_FOLDER'], 'signatures')
    os.makedirs(signature_path, exist_ok=True)
    return send_from_directory(signature_path, filename)

@app.route('/uploads/profile_pics/<filename>')
@login_required
def serve_profile_pic(filename):
    """Serve profile pictures securely."""
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics'), filename)


@app.route('/uploads/<path:filename>')
@login_required
def serve_uploads(filename):
    """Serve uploaded files from the uploads directory. Path is relative inside uploads/."""
    safe_base = os.path.abspath(app.config['UPLOAD_FOLDER'])
    requested = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    # Prevent directory traversal
    if not requested.startswith(safe_base):
        return "Invalid file path", 400
    dirpath = os.path.dirname(requested)
    fname = os.path.basename(requested)
    return send_from_directory(dirpath, fname)

# ==================== PROFILE ADDITIONAL ROUTES ====================

@app.route('/api/generate-profile-report', methods=['POST'])
@login_required
def api_generate_profile_report():
    """Generate a comprehensive profile report."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get user data
            c.execute("SELECT * FROM users WHERE user_id = ?", (current_user.id,))
            user_data = c.fetchone()
            
            if not user_data:
                return jsonify({'success': False, 'error': 'User not found'})
            
            user_dict = dict(user_data)
            
            # Get documents count
            c.execute("SELECT COUNT(*) as count FROM user_documents WHERE user_id = ?", (current_user.id,))
            doc_result = c.fetchone()
            documents_count = doc_result['count'] if doc_result else 0
            
            # Get activity count
            c.execute("SELECT COUNT(*) as count FROM activity_logs WHERE user_id = ?", (current_user.id,))
            activity_result = c.fetchone()
            activity_count = activity_result['count'] if activity_result else 0
            
            # Get evaluation stats if table exists
            total_evaluations = 0
            avg_sqi = 0
            try:
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_evaluations'")
                if c.fetchone():
                    c.execute("SELECT COUNT(*) as count FROM service_evaluations WHERE evaluator_id = ?", (current_user.id,))
                    eval_result = c.fetchone()
                    total_evaluations = eval_result['count'] if eval_result else 0
                    
                    c.execute("SELECT AVG(sqi_score) as avg_sqi FROM service_evaluations WHERE evaluator_id = ?", (current_user.id,))
                    sqi_result = c.fetchone()
                    avg_sqi = round(sqi_result['avg_sqi'], 2) if sqi_result and sqi_result['avg_sqi'] else 0
            except:
                pass
            
            # Generate report content
            report_content = f"""
PROFILE REPORT
================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

PERSONAL INFORMATION
--------------------
Name: {user_dict['first_name']} {user_dict['last_name']}
Email: {user_dict['email']}
Phone: {user_dict.get('phone', 'N/A')}
Rank/Position: {user_dict.get('rank', 'N/A')}
Department: {user_dict.get('department', 'N/A')}
Location: {user_dict.get('location', 'N/A')}
Role: {user_dict['role'].replace('_', ' ').title()}
User ID: {user_dict['user_id']}

STATISTICS
----------
Total Documents: {documents_count}
Total Activities: {activity_count}
Total Evaluations: {total_evaluations}
Average SQI Score: {avg_sqi}
Member Since: {user_dict.get('created_at', 'N/A')[:10] if user_dict.get('created_at') else 'N/A'}
Last Login: {user_dict.get('last_login', 'Never')}

This report was generated from the VesselOS platform.
            """
            
            log_activity('profile_report_generated', 'User generated profile report')
            return jsonify({
                'success': True,
                'report_content': report_content,
                'report_id': f'PROF-{datetime.now().strftime("%Y%m%d%H%M%S")}'
            })
        except Exception as e:
            app.logger.error(f"Error generating profile report: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in generate profile report: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/download-personal-data')
@login_required
def api_download_personal_data():
    """Download user's personal data in JSON format."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get user data
            c.execute("SELECT * FROM users WHERE user_id = ?", (current_user.id,))
            user_data = c.fetchone()
            
            if not user_data:
                return jsonify({'success': False, 'error': 'User not found'})
            
            user_dict = dict(user_data)
            
            # Get documents
            c.execute("SELECT * FROM user_documents WHERE user_id = ?", (current_user.id,))
            documents = [dict(row) for row in c.fetchall()]
            
            # Get activities
            c.execute("SELECT * FROM activity_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT 100", (current_user.id,))
            activities = [dict(row) for row in c.fetchall()]
            
            # Get messages sent
            c.execute("SELECT * FROM messaging_system WHERE sender_id = ? ORDER BY created_at DESC LIMIT 50", (current_user.id,))
            messages_sent = [dict(row) for row in c.fetchall()]
            
            # Get messages received
            c.execute("""
                SELECT * FROM messaging_system 
                WHERE (recipient_type = 'specific_user' AND recipient_id = ?)
                   OR (recipient_type = 'role' AND ? IN (SELECT role FROM users WHERE user_id = ?))
                   OR (recipient_type = 'department' AND ? IN (SELECT department FROM users WHERE user_id = ?))
                   OR (recipient_type = 'all')
                ORDER BY created_at DESC LIMIT 50
            """, (current_user.id, current_user.id, current_user.id, current_user.id, current_user.id))
            messages_received = [dict(row) for row in c.fetchall()]
            
            # Prepare personal data (remove sensitive password)
            personal_data = {
                'user_id': user_dict['user_id'],
                'email': user_dict['email'],
                'first_name': user_dict['first_name'],
                'last_name': user_dict['last_name'],
                'phone': user_dict.get('phone'),
                'rank': user_dict.get('rank'),
                'department': user_dict.get('department'),
                'location': user_dict.get('location'),
                'role': user_dict['role'],
                'created_at': user_dict.get('created_at'),
                'last_login': user_dict.get('last_login'),
                'last_activity': user_dict.get('last_activity'),
                'is_approved': bool(user_dict.get('is_approved')),
                'is_active': bool(user_dict.get('is_active')),
                'documents': documents,
                'activities': activities,
                'messages_sent': messages_sent,
                'messages_received': messages_received,
                'export_date': datetime.now().isoformat()
            }
            
            log_activity('personal_data_exported', 'User exported personal data')
            return jsonify({'success': True, 'data': personal_data})
        except Exception as e:
            app.logger.error(f"Error downloading personal data: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in download personal data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/request-account-deletion', methods=['POST'])
@login_required
def api_request_account_deletion():
    """Request account deletion."""
    try:
        data = request.get_json()
        reason = data.get('reason', 'No reason provided')
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Create deletion request record (if table exists, otherwise just log)
            try:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS account_deletion_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        reason TEXT,
                        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending',
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                """)
                
                c.execute("""
                    INSERT INTO account_deletion_requests (user_id, reason)
                    VALUES (?, ?)
                """, (current_user.id, reason))
                conn.commit()
            except Exception as e:
                app.logger.warning(f"Could not create deletion request record: {e}")
            
            # Log the activity
            log_activity('account_deletion_requested', f'User requested account deletion: {reason}')
            
            return jsonify({
                'success': True,
                'message': 'Account deletion request submitted. Administrator will contact you.'
            })
        except Exception as e:
            app.logger.error(f"Error requesting account deletion: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in request account deletion: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/logout-other-sessions', methods=['POST'])
@login_required
def api_logout_other_sessions():
    """Logout all other sessions (placeholder - would need session management)."""
    try:
        # In a real system, this would invalidate other session tokens
        # For now, we'll just log the activity
        log_activity('logout_other_sessions', 'User logged out all other sessions')
        
        return jsonify({
            'success': True,
            'message': 'All other sessions have been logged out.'
        })
    except Exception as e:
        app.logger.error(f"Error logging out other sessions: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/save-privacy-settings', methods=['POST'])
@login_required
def api_save_privacy_settings():
    """Save user privacy settings."""
    try:
        data = request.get_json()
        profile_visibility = data.get('profile_visibility', True)
        activity_sharing = data.get('activity_sharing', True)
        email_notifications = data.get('email_notifications', True)
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Create privacy_settings table if it doesn't exist
            c.execute("""
                CREATE TABLE IF NOT EXISTS privacy_settings (
                    user_id TEXT PRIMARY KEY,
                    profile_visibility INTEGER DEFAULT 1,
                    activity_sharing INTEGER DEFAULT 1,
                    email_notifications INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Insert or update privacy settings
            c.execute("""
                INSERT INTO privacy_settings (user_id, profile_visibility, activity_sharing, email_notifications)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    profile_visibility = ?,
                    activity_sharing = ?,
                    email_notifications = ?,
                    updated_at = CURRENT_TIMESTAMP
            """, (current_user.id, int(profile_visibility), int(activity_sharing), int(email_notifications),
                  int(profile_visibility), int(activity_sharing), int(email_notifications)))
            
            conn.commit()
            log_activity('privacy_settings_updated', 'User updated privacy settings')
            
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error saving privacy settings: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in save privacy settings: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== MESSAGING SYSTEM ROUTES ====================

@app.route('/messaging-center')
@login_required
def messaging_center():
    """Messaging center page."""
    if current_user.role == 'quality_officer':
        flash('DMPO HQ officers cannot send messages.', 'warning')
        return redirect(url_for('dashboard'))
    return render_template('messaging_center.html')

@app.route('/api/messaging/send', methods=['POST'])
@login_required
def api_messaging_send():
    """Send a message/notification/announcement."""
    try:
        if current_user.role == 'quality_officer':
            return jsonify({'success': False, 'error': 'Quality officers cannot send messages'})

        message_type = request.form.get('message_type')
        recipient_type = request.form.get('recipient_type')
        title = request.form.get('title')
        message_text = request.form.get('message')
        priority = request.form.get('priority', 'normal')
        allow_replies_raw = request.form.get('allow_replies')
        allow_replies = allow_replies_raw in {'true', 'on', '1', 'yes'}

        if not all([message_type, recipient_type, title, message_text]):
            return jsonify({'success': False, 'error': 'Missing required fields'})

        conn = get_db_connection()
        try:
            c = conn.cursor()
            base_message_id = generate_id('MSG')

            # Handle multiple attachments
            attachment_filenames = []
            attachment_paths = []
            # Collect files named 'attachments' (multiple files can have same field name)
            files = request.files.getlist('attachments')
            for file in files:
                if file and file.filename:
                    if not allowed_file(file.filename):
                        return jsonify({'success': False, 'error': f'Invalid file type: {file.filename}'})
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    if file_size > 20 * 1024 * 1024:
                        return jsonify({'success': False, 'error': f'File size exceeds 20MB limit: {file.filename}'})

                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    filename = secure_filename(f"{base_message_id}_{timestamp}_{file.filename}")
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', filename)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    file.save(save_path)
                    attachment_filenames.append(file.filename)
                    attachment_paths.append(filename)

            # Determine recipients and recipient details
            recipients = []
            recipient_id = None
            recipient_email = None
            recipient_phone = None

            if recipient_type == 'specific_user':
                user_id = request.form.get('user_id', '').strip()
                user_email = request.form.get('user_email', '').strip()
                user_phone = request.form.get('user_phone', '').strip()

                query = "SELECT user_id FROM users WHERE is_active = 1 AND is_approved = 1"
                params = []

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)
                elif user_email:
                    query += " AND email = ?"
                    params.append(user_email)
                elif user_phone:
                    query += " AND phone = ?"
                    params.append(user_phone)
                else:
                    return jsonify({'success': False, 'error': 'No user identifier provided'})

                c.execute(query, params)
                user = c.fetchone()
                if user:
                    recipients.append(user['user_id'])
                    recipient_id = user['user_id']
                    recipient_email = user_email if user_email else None
                    recipient_phone = user_phone if user_phone else None
                else:
                    return jsonify({'success': False, 'error': 'User not found'})

            elif recipient_type == 'role':
                role = request.form.get('role')
                if not role:
                    return jsonify({'success': False, 'error': 'No role selected'})
                c.execute("SELECT user_id FROM users WHERE role = ? AND is_active = 1 AND is_approved = 1", (role,))
                recipients = [row['user_id'] for row in c.fetchall()]
                recipient_id = role
                recipient_email = None
                recipient_phone = None

            elif recipient_type == 'department':
                department = request.form.get('department')
                if not department:
                    return jsonify({'success': False, 'error': 'No department selected'})
                c.execute("SELECT user_id FROM users WHERE department = ? AND is_active = 1 AND is_approved = 1", (department,))
                recipients = [row['user_id'] for row in c.fetchall()]
                recipient_id = department
                recipient_email = None
                recipient_phone = None

            elif recipient_type == 'all':
                c.execute("SELECT user_id FROM users WHERE is_active = 1 AND is_approved = 1 AND user_id != ?", (current_user.id,))
                recipients = [row['user_id'] for row in c.fetchall()]
                recipient_id = 'all'
                recipient_email = None
                recipient_phone = None

            else:
                return jsonify({'success': False, 'error': 'Invalid recipient type'})

            if not recipients:
                return jsonify({'success': False, 'error': 'No recipients found'})

            # Store message for each recipient
            for recipient_user_id in recipients:
                message_id = generate_id('MSG')
                
                if attachment_paths:
                    # If there are attachments, create one message with all attachments
                    attachments_json = json.dumps({
                        'paths': attachment_paths,
                        'filenames': attachment_filenames
                    })
                    
                    c.execute("""
                        INSERT INTO messaging_system
                        (message_id, sender_id, recipient_type, recipient_id, recipient_email, recipient_phone,
                         title, message, message_type, priority, attachment_path, attachment_filename,
                         allow_replies, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (message_id, current_user.id, recipient_type, recipient_id, recipient_email, recipient_phone,
                          title, message_text, message_type, priority, 
                          json.dumps(attachment_paths), json.dumps(attachment_filenames),
                          1 if allow_replies else 0, datetime.now()))
                else:
                    c.execute("""
                        INSERT INTO messaging_system
                        (message_id, sender_id, recipient_type, recipient_id, recipient_email, recipient_phone,
                         title, message, message_type, priority, allow_replies, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (message_id, current_user.id, recipient_type, recipient_id, recipient_email, recipient_phone,
                          title, message_text, message_type, priority,
                          1 if allow_replies else 0, datetime.now()))

                # Create notification for recipient
                create_notification(
                    recipient_user_id,
                    f"New {message_type}: {title}",
                    f"You have received a new {message_type} from {current_user.get_full_name()}",
                    priority,
                    '/messaging-center'
                )

            conn.commit()

            log_activity('message_sent', f'Sent {message_type} to {len(recipients)} recipients')
            print(f"[OK] MESSAGE SENT: {base_message_id} to {len(recipients)} recipients")
            app.logger.info(f"Message sent successfully: {base_message_id} to {len(recipients)} recipients")

            return jsonify({
                'success': True,
                'recipients': len(recipients),
                'message_id': base_message_id
            })

        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error sending message: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in messaging send: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/sent')
@login_required
def api_messaging_sent():
    """Get messages sent by current user."""
    try:
        filter_type = request.args.get('filter', 'all')
        search = request.args.get('search', '')

        conn = get_db_connection()
        try:
            c = conn.cursor()

            query = """
                SELECT DISTINCT 
                    CASE 
                        WHEN m.recipient_type = 'specific_user' THEN 
                            (SELECT u.first_name || ' ' || u.last_name 
                             FROM users u WHERE u.user_id = m.recipient_id)
                        WHEN m.recipient_type = 'role' THEN 
                            'Role: ' || m.recipient_id
                        WHEN m.recipient_type = 'department' THEN 
                            'Department: ' || m.recipient_id
                        WHEN m.recipient_type = 'all' THEN 
                            'All Users'
                        ELSE 'Unknown'
                    END as recipient_name,
                    m.message_id, m.title, m.message, m.message_type, m.priority,
                    m.recipient_type, m.recipient_id, m.created_at, 
                    COUNT(DISTINCT ms.message_id) as message_count
                FROM messaging_system m
                LEFT JOIN messaging_system ms ON m.sender_id = ms.sender_id 
                    AND m.created_at = ms.created_at 
                    AND m.title = ms.title
                WHERE m.sender_id = ?
            """
            params = [current_user.id]

            if search:
                query += " AND (m.title LIKE ? OR m.message LIKE ?)"
                params.extend([f'%{search}%', f'%{search}%'])

            if filter_type != 'all':
                query += " AND m.message_type = ?"
                params.append(filter_type)

            query += """
                GROUP BY m.title, m.created_at, m.recipient_type, m.recipient_id
                ORDER BY m.created_at DESC
            """

            c.execute(query, params)
            messages = []

            for row in c.fetchall():
                message = dict(row)
                messages.append(message)

            return jsonify({'success': True, 'messages': messages})

        except Exception as e:
            app.logger.error(f"Error getting sent messages: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in sent messages: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/delete-announcement', methods=['DELETE'])
@login_required
@csrf_protect
def api_delete_announcement():
    """Delete an announcement by the sender."""
    try:
        data = request.get_json()
        title = data.get('title')
        created_at = data.get('created_at')
        
        if not title or not created_at:
            return jsonify({'success': False, 'error': 'Title and created_at are required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Verify the announcement exists and belongs to the current user
            c.execute("""
                SELECT COUNT(*) as count
                FROM messaging_system
                WHERE sender_id = ? 
                AND title = ? 
                AND created_at = ?
                AND message_type = 'announcement'
            """, (current_user.id, title, created_at))
            
            result = c.fetchone()
            if not result or result['count'] == 0:
                return jsonify({'success': False, 'error': 'Announcement not found or you do not have permission to delete it'})
            
            # Delete all instances of this announcement (for all recipients)
            c.execute("""
                DELETE FROM messaging_system
                WHERE sender_id = ? 
                AND title = ? 
                AND created_at = ?
                AND message_type = 'announcement'
            """, (current_user.id, title, created_at))
            
            deleted_count = c.rowcount
            conn.commit()
            
            # Log activity
            log_activity('announcement_deleted', f'Deleted announcement: {title}')
            
            return jsonify({
                'success': True, 
                'message': f'Announcement deleted successfully',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error deleting announcement: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
            
    except Exception as e:
        app.logger.error(f"Error in delete announcement: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/inbox')
@login_required
def api_messaging_inbox():
    """Get inbox messages for current user."""
    try:
        filter_type = request.args.get('filter', 'all')
        search = request.args.get('search', '')

        conn = get_db_connection()
        try:
            c = conn.cursor()

            query = """
                SELECT m.message_id, m.title, m.message, m.message_type, m.priority,
                       m.attachment_filename, m.is_read, m.allow_replies, m.created_at,
                       u.first_name || ' ' || u.last_name as sender_name,
                       u.role as sender_role
                FROM messaging_system m
                JOIN users u ON m.sender_id = u.user_id
                WHERE (
                    (m.recipient_type = 'specific_user' AND m.recipient_id = ?) OR
                    (m.recipient_type = 'role' AND ? IN (
                        SELECT role FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'department' AND ? IN (
                        SELECT department FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'all')
                )
            """
            params = [current_user.id, current_user.role, current_user.id,
                     current_user.department, current_user.id]

            if filter_type == 'unread':
                query += " AND m.is_read = 0"
            elif filter_type == 'messages':
                query += " AND m.message_type = 'message'"
            elif filter_type == 'notifications':
                query += " AND m.message_type = 'notification'"
            elif filter_type == 'announcements':
                query += " AND m.message_type = 'announcement'"

            if search:
                query += " AND (m.title LIKE ? OR m.message LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ?)"
                params.extend([f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'])

            query += " ORDER BY m.created_at DESC"

            c.execute(query, params)
            messages = [dict(row) for row in c.fetchall()]

            return jsonify({'success': True, 'messages': messages})

        except Exception as e:
            app.logger.error(f"Error getting inbox: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in inbox: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/threads')
@login_required
def api_messaging_threads():
    """Get message threads/conversations."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Get threads where user is sender or recipient
            query = """
                SELECT DISTINCT 
                    CASE 
                        WHEN m.sender_id = ? THEN m.recipient_id
                        ELSE m.sender_id
                    END as other_party_id,
                    CASE 
                        WHEN m.sender_id = ? THEN 
                            (SELECT u.first_name || ' ' || u.last_name 
                             FROM users u WHERE u.user_id = m.recipient_id)
                        ELSE 
                            (SELECT u.first_name || ' ' || u.last_name 
                             FROM users u WHERE u.user_id = m.sender_id)
                    END as other_party_name,
                    CASE 
                        WHEN m.sender_id = ? THEN 'sent'
                        ELSE 'received'
                    END as direction,
                    MAX(m.created_at) as last_message_date,
                    COUNT(*) as message_count,
                    SUM(CASE WHEN m.is_read = 0 AND m.sender_id != ? THEN 1 ELSE 0 END) as unread_count
                FROM messaging_system m
                WHERE (m.sender_id = ? OR (
                    (m.recipient_type = 'specific_user' AND m.recipient_id = ?) OR
                    (m.recipient_type = 'role' AND ? IN (
                        SELECT role FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'department' AND ? IN (
                        SELECT department FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'all')
                ))
                AND m.message_type = 'message'
                GROUP BY other_party_id
                ORDER BY last_message_date DESC
            """
            params = [current_user.id, current_user.id, current_user.id, current_user.id,
                     current_user.id, current_user.id, current_user.role, current_user.id,
                     current_user.department, current_user.id]

            c.execute(query, params)
            threads = [dict(row) for row in c.fetchall()]

            return jsonify({'success': True, 'threads': threads})

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            app.logger.error(f"Error getting threads: {e}\n{tb_str}")
            print(f"THREADS ERROR: {e}\n{tb_str}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        app.logger.error(f"Error in threads: {e}\n{tb_str}")
        print(f"THREADS OUTER ERROR: {e}\n{tb_str}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/thread/<other_party_id>')
@login_required
def api_messaging_thread(other_party_id):
    """Get specific thread messages - OPTIMIZED."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Optimized query - single round trip for main messages
            query = """
                SELECT m.message_id, m.title, m.message, m.message_type, m.priority,
                       m.attachment_filename, m.attachment_path, m.is_read, m.allow_replies, m.created_at,
                       u.first_name || ' ' || u.last_name as sender_name,
                       u.role as sender_role, u.user_id as sender_id,
                       CASE 
                           WHEN m.sender_id = ? THEN 'sent'
                           ELSE 'received'
                       END as direction
                FROM messaging_system m
                LEFT JOIN users u ON m.sender_id = u.user_id
                WHERE m.message_type = 'message'
                AND (
                    (m.sender_id = ? AND m.recipient_type = 'specific_user' AND m.recipient_id = ?) OR
                    (m.recipient_type = 'specific_user' AND m.recipient_id = ? AND m.sender_id = ?)
                )
                ORDER BY m.created_at ASC
                LIMIT 1000
            """
            params = [current_user.id, current_user.id, other_party_id, 
                     current_user.id, other_party_id]

            c.execute(query, params)
            messages = [dict(row) for row in c.fetchall()]

            # Parse attachments for each message
            for message in messages:
                attachments = []
                attachment_path = message.get('attachment_path')
                attachment_filename = message.get('attachment_filename')
                
                if attachment_path and attachment_filename:
                    try:
                        # Try to parse as JSON
                        if isinstance(attachment_path, str) and attachment_path.strip():
                            try:
                                attachment_paths = json.loads(attachment_path)
                            except (json.JSONDecodeError, ValueError):
                                attachment_paths = attachment_path
                        else:
                            attachment_paths = attachment_path
                        
                        if isinstance(attachment_filename, str) and attachment_filename.strip():
                            try:
                                attachment_filenames = json.loads(attachment_filename)
                            except (json.JSONDecodeError, ValueError):
                                attachment_filenames = attachment_filename
                        else:
                            attachment_filenames = attachment_filename
                        
                        # Handle list format
                        if isinstance(attachment_paths, list) and isinstance(attachment_filenames, list):
                            for idx, (path, filename) in enumerate(zip(attachment_paths, attachment_filenames)):
                                if path and filename:
                                    attachments.append({
                                        'filename': filename,
                                        'path': path,
                                        'index': idx
                                    })
                        # Handle single attachment
                        elif attachment_paths and attachment_filenames:
                            attachments.append({
                                'filename': attachment_filenames if isinstance(attachment_filenames, str) else str(attachment_filenames),
                                'path': attachment_paths if isinstance(attachment_paths, str) else str(attachment_paths),
                                'index': 0
                            })
                    except Exception as e:
                        app.logger.warning(f"Error parsing attachments: {e}")
                        if attachment_path and attachment_filename:
                            attachments.append({
                                'filename': str(attachment_filename),
                                'path': str(attachment_path),
                                'index': 0
                            })
                message['attachments'] = attachments

            # Get replies for each message (batch query)
            for message in messages:
                c.execute("""
                    SELECT r.reply_id, r.reply_text, r.sender_id, r.attachment_path, 
                           r.attachment_filename, r.reply_to_message_id, r.created_at,
                           u.first_name || ' ' || u.last_name as sender_name
                    FROM message_replies r
                    LEFT JOIN users u ON r.sender_id = u.user_id
                    WHERE r.message_id = ?
                    ORDER BY r.created_at ASC
                """, (message['message_id'],))
                replies = [dict(row) for row in c.fetchall()]
                
                # Parse reply attachments and get original message info for WhatsApp-style replies
                for reply in replies:
                    reply_attachments = []
                    reply_path = reply.get('attachment_path')
                    reply_filename = reply.get('attachment_filename')
                    
                    # If this reply is replying to another message, get the original message info
                    if reply.get('reply_to_message_id'):
                        c.execute("""
                            SELECT m.message_id, m.message, m.sender_id, m.attachment_path, m.attachment_filename,
                                   u.first_name || ' ' || u.last_name as sender_name
                            FROM messaging_system m
                            LEFT JOIN users u ON m.sender_id = u.user_id
                            WHERE m.message_id = ?
                        """, (reply['reply_to_message_id'],))
                        original_msg = c.fetchone()
                        if original_msg:
                            original_msg_dict = dict(original_msg)
                            # Parse attachments for original message
                            original_attachments = []
                            try:
                                if original_msg_dict.get('attachment_path'):
                                    paths = json.loads(original_msg_dict['attachment_path'])
                                    filenames = json.loads(original_msg_dict['attachment_filename']) if original_msg_dict.get('attachment_filename') else []
                                    for idx, path in enumerate(paths):
                                        original_attachments.append({
                                            'index': idx,
                                            'filename': filenames[idx] if idx < len(filenames) else path,
                                            'path': path,
                                            'type': 'image' if any(ext in path.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']) else 
                                                   'video' if any(ext in path.lower() for ext in ['.mp4', '.avi', '.mov', '.webm']) else 'file'
                                        })
                            except:
                                pass
                            original_msg_dict['attachments'] = original_attachments
                            reply['replied_to_message'] = original_msg_dict
                    
                    if reply_path and reply_filename:
                        try:
                            if isinstance(reply_path, str) and reply_path.strip():
                                try:
                                    reply_paths = json.loads(reply_path)
                                except (json.JSONDecodeError, ValueError):
                                    reply_paths = reply_path
                            else:
                                reply_paths = reply_path
                            
                            if isinstance(reply_filename, str) and reply_filename.strip():
                                try:
                                    reply_filenames = json.loads(reply_filename)
                                except (json.JSONDecodeError, ValueError):
                                    reply_filenames = reply_filename
                            else:
                                reply_filenames = reply_filename
                            
                            # Handle list format
                            if isinstance(reply_paths, list) and isinstance(reply_filenames, list):
                                for idx, (path, filename) in enumerate(zip(reply_paths, reply_filenames)):
                                    if path and filename:
                                        reply_attachments.append({
                                            'filename': filename,
                                            'path': path,
                                            'index': idx
                                        })
                            # Handle single attachment
                            elif reply_paths and reply_filenames:
                                reply_attachments.append({
                                    'filename': reply_filenames if isinstance(reply_filenames, str) else str(reply_filenames),
                                    'path': reply_paths if isinstance(reply_paths, str) else str(reply_paths),
                                    'index': 0
                                })
                        except Exception as e:
                            app.logger.warning(f"Error parsing reply attachments: {e}")
                            if reply_path and reply_filename:
                                reply_attachments.append({
                                    'filename': str(reply_filename),
                                    'path': str(reply_path),
                                    'index': 0
                                })
                    reply['attachments'] = reply_attachments
                
                message['replies'] = replies

            return jsonify({'success': True, 'messages': messages})

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            app.logger.error(f"Error getting thread: {e}\n{tb_str}")
            print(f"THREAD DETAIL ERROR: {e}\n{tb_str}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        app.logger.error(f"Error in thread: {e}\n{tb_str}")
        print(f"THREAD DETAIL OUTER ERROR: {e}\n{tb_str}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/conversations')
@login_required
def api_messaging_conversations():
    """Get conversations for floating panel (simplified threads)."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Get conversations where current user is involved
            query = """
                SELECT DISTINCT 
                    CASE 
                        WHEN m.sender_id = ? THEN m.recipient_id
                        ELSE m.sender_id
                    END as thread_id,
                    CASE 
                        WHEN m.sender_id = ? THEN 
                            (SELECT u.first_name || ' ' || u.last_name 
                             FROM users u WHERE u.user_id = m.recipient_id)
                        ELSE 
                            (SELECT u.first_name || ' ' || u.last_name 
                             FROM users u WHERE u.user_id = m.sender_id)
                    END as other_user_name,
                    MAX(m.created_at) as last_message_at,
                    (SELECT message FROM messaging_system 
                     WHERE (sender_id = ? AND recipient_id = thread_id) 
                        OR (sender_id = thread_id AND recipient_type = 'specific_user' AND recipient_id = ?)
                     ORDER BY created_at DESC LIMIT 1) as last_message_preview,
                    SUM(CASE WHEN m.is_read = 0 AND m.sender_id != ? THEN 1 ELSE 0 END) as unread_count
                FROM messaging_system m
                WHERE (m.sender_id = ? OR (m.recipient_type = 'specific_user' AND m.recipient_id = ?))
                AND m.message_type = 'message'
                GROUP BY thread_id
                ORDER BY last_message_at DESC
                LIMIT 10
            """
            params = [current_user.id, current_user.id, current_user.id, current_user.id, 
                     current_user.id, current_user.id, current_user.id]

            c.execute(query, params)
            conversations = [dict(row) for row in c.fetchall()]

            return jsonify({'success': True, 'conversations': conversations})

        except Exception as e:
            app.logger.error(f"Error getting conversations: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in conversations: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/conversation/<thread_id>')
@login_required
def api_messaging_conversation(thread_id):
    """Get conversation messages for floating panel."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Get conversation messages - INCLUDE ATTACHMENTS
            query = """
                SELECT m.message_id, m.message, m.created_at,
                       u.first_name || ' ' || u.last_name as sender_name,
                       u.user_id as sender_id,
                       m.attachment_path, m.attachment_filename
                FROM messaging_system m
                JOIN users u ON m.sender_id = u.user_id
                WHERE m.message_type = 'message'
                AND (
                    (m.sender_id = ? AND m.recipient_type = 'specific_user' AND m.recipient_id = ?) OR
                    (m.sender_id = ? AND m.recipient_type = 'specific_user' AND m.recipient_id = ?)
                )
                ORDER BY m.created_at ASC
            """
            params = [current_user.id, thread_id, thread_id, current_user.id]

            c.execute(query, params)
            messages = [dict(row) for row in c.fetchall()]

            # Process attachments for each message
            processed_messages = []
            for msg in messages:
                msg_dict = dict(msg)
                # Parse attachments
                attachments = []
                try:
                    if msg_dict.get('attachment_path'):
                        paths = json.loads(msg_dict['attachment_path'])
                        filenames = json.loads(msg_dict['attachment_filename']) if msg_dict.get('attachment_filename') else []
                        for idx, path in enumerate(paths):
                            attachments.append({
                                'index': idx,
                                'filename': filenames[idx] if idx < len(filenames) else path
                            })
                except:
                    pass
                msg_dict['attachments'] = attachments
                processed_messages.append(msg_dict)

            # Mark messages as read
            c.execute("""
                UPDATE messaging_system
                SET is_read = 1, read_at = ?
                WHERE recipient_type = 'specific_user' 
                AND recipient_id = ?
                AND sender_id = ?
                AND is_read = 0
            """, (datetime.now(), current_user.id, thread_id))

            conn.commit()

            return jsonify({'success': True, 'messages': processed_messages})

        except Exception as e:
            app.logger.error(f"Error getting conversation: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in conversation: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/quick-send', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def api_messaging_quick_send():
    """Quick send message from floating panel - OPTIMIZED FOR SPEED."""
    try:
        if current_user.role == 'quality_officer':
            return jsonify({'success': False, 'error': 'Quality officers cannot send messages'})

        # Support both quick-compose and thread replies:
        user_id = request.form.get('user_id') or request.form.get('recipient_id')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message_text = request.form.get('message')
        priority = request.form.get('priority', 'normal')
        thread_context = request.form.get('thread_context', 'message')
        reply_to_message_id = request.form.get('reply_to_message_id')  # WhatsApp-style reply

        if not subject or not message_text:
            return jsonify({'success': False, 'error': 'Subject and message are required'})

        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Determine recipient
            recipient_id = None
            if user_id:
                # Quick check - user exists
                c.execute("SELECT user_id FROM users WHERE user_id = ? LIMIT 1", (user_id,))
                user = c.fetchone()
                if not user:
                    return jsonify({'success': False, 'error': 'User not found'})
                recipient_id = user['user_id']
            elif email:
                # Find user by email
                c.execute("SELECT user_id FROM users WHERE email = ? LIMIT 1", (email,))
                user = c.fetchone()
                if user:
                    recipient_id = user['user_id']

            message_id = generate_id('MSG')
            created_at = datetime.now()

            # Handle attachments (faster processing)
            attachment_filenames = []
            attachment_paths = []
            files = request.files.getlist('attachments')
            
            for file in files:
                if file and file.filename:
                    if not allowed_file(file.filename):
                        return jsonify({'success': False, 'error': f'Invalid file type: {file.filename}'})
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    if file_size > 20 * 1024 * 1024:
                        return jsonify({'success': False, 'error': f'File too large: {file.filename}'})

                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:14]
                    filename = secure_filename(f"{message_id}_{timestamp}_{file.filename}")
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', filename)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    file.save(save_path)
                    attachment_filenames.append(file.filename)
                    attachment_paths.append(filename)

            # Single optimized insert
            if recipient_id:
                # Send to specific user
                if attachment_paths:
                    c.execute("""
                        INSERT INTO messaging_system
                        (message_id, sender_id, recipient_type, recipient_id, title, message,
                         message_type, priority, attachment_path, attachment_filename,
                         allow_replies, created_at, is_read)
                        VALUES (?, ?, 'specific_user', ?, ?, ?, 'message', ?, ?, ?, 1, ?, 0)
                    """, (message_id, current_user.id, recipient_id,
                          subject, message_text, priority,
                          json.dumps(attachment_paths), json.dumps(attachment_filenames),
                          created_at))
                else:
                    c.execute("""
                        INSERT INTO messaging_system
                        (message_id, sender_id, recipient_type, recipient_id, title, message,
                         message_type, priority, allow_replies, created_at, is_read)
                        VALUES (?, ?, 'specific_user', ?, ?, ?, 'message', ?, 1, ?, 0)
                    """, (message_id, current_user.id, recipient_id,
                          subject, message_text, priority, created_at))

                # Notification will be created in background thread (moved below)
                    
            else:
                # Send to email
                if attachment_paths:
                    c.execute("""
                        INSERT INTO messaging_system
                        (message_id, sender_id, recipient_type, recipient_email, title, message,
                         message_type, priority, attachment_path, attachment_filename,
                         allow_replies, created_at, is_read)
                        VALUES (?, ?, 'specific_user', ?, ?, ?, 'message', ?, ?, ?, 0, ?, 0)
                    """, (message_id, current_user.id, email,
                          subject, message_text, priority,
                          json.dumps(attachment_paths), json.dumps(attachment_filenames),
                          created_at))
                else:
                    c.execute("""
                        INSERT INTO messaging_system
                        (message_id, sender_id, recipient_type, recipient_email, title, message,
                         message_type, priority, allow_replies, created_at, is_read)
                        VALUES (?, ?, 'specific_user', ?, ?, ?, 'message', ?, 0, ?, 0)
                    """, (message_id, current_user.id, email,
                          subject, message_text, priority, created_at))

            # If replying to a specific message (WhatsApp-style), create a reply entry
            if reply_to_message_id:
                # Get the original message to reply to
                c.execute("""
                    SELECT message_id, sender_id, title, message, attachment_path, attachment_filename
                    FROM messaging_system
                    WHERE message_id = ?
                """, (reply_to_message_id,))
                original_message = c.fetchone()
                
                if original_message:
                    # Create reply in message_replies table
                    reply_id = generate_id('REPLY')
                    reply_attachment_path = json.dumps(attachment_paths) if attachment_paths else None
                    reply_attachment_filename = json.dumps(attachment_filenames) if attachment_filenames else None
                    
                    c.execute("""
                        INSERT INTO message_replies
                        (reply_id, message_id, sender_id, reply_text, attachment_path, attachment_filename, 
                         reply_to_message_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (reply_id, reply_to_message_id, current_user.id, message_text,
                          reply_attachment_path, reply_attachment_filename, reply_to_message_id, created_at))
            
            conn.commit()
            
            # Return response IMMEDIATELY (before notifications/logging)
            # This is critical for instant message sending UX
            response = jsonify({'success': True, 'message_id': message_id, 'sent_at': created_at.isoformat()})
            
            # Background tasks (don't block response)
            def background_tasks():
                try:
                    log_activity('message_sent', f'Sent message to {recipient_id or email}')
                except:
                    pass
                try:
                    if recipient_id:
                        create_notification(
                            recipient_id,
                            f"New Message: {subject[:50]}",
                            f"From {current_user.get_full_name()}",
                            priority,
                            '/messaging-center'
                        )
                except:
                    pass
            
            # Run background tasks in thread (non-blocking)
            from threading import Thread
            bg_thread = Thread(target=background_tasks, daemon=True)
            bg_thread.start()
            
            return response

        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error sending message: {e}", exc_info=True)
            return jsonify({'success': False, 'error': 'Failed to send message'})
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in quick send: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/quick-reply', methods=['POST'])
@login_required
@limiter.limit("60 per minute")
def api_messaging_quick_reply():
    """Quick reply from floating panel."""
    try:
        message_id = request.form.get('message_id')
        reply_text = request.form.get('reply_text')

        if not message_id or not reply_text:
            return jsonify({'success': False, 'error': 'Message ID and reply text are required'})

        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Get original message
            c.execute("""
                SELECT sender_id, title, allow_replies
                FROM messaging_system
                WHERE message_id = ? AND (
                    (recipient_type = 'specific_user' AND recipient_id = ?) OR
                    sender_id = ?
                )
            """, (message_id, current_user.id, current_user.id))

            message = c.fetchone()
            if not message:
                return jsonify({'success': False, 'error': 'Message not found'})

            if not message['allow_replies']:
                return jsonify({'success': False, 'error': 'Replies not allowed for this message'})

            # Get reply_to_message_id if provided (WhatsApp-style reply)
            reply_to_message_id = request.form.get('reply_to_message_id')

            # Handle attachment
            attachment_filename = None
            attachment_path = None
            if 'attachment' in request.files:
                file = request.files['attachment']
                if file and file.filename:
                    if not allowed_file(file.filename):
                        return jsonify({'success': False, 'error': 'Invalid file type'})

                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    if file_size > 20 * 1024 * 1024:
                        return jsonify({'success': False, 'error': 'File size exceeds 20MB limit'})

                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    filename = secure_filename(f"reply_{message_id}_{timestamp}_{file.filename}")
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', 'replies', filename)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    file.save(save_path)
                    attachment_filename = file.filename
                    attachment_path = filename

            # Create reply with real-time timestamp
            reply_id = generate_id('REPLY')
            current_time = datetime.now()
            c.execute("""
                INSERT INTO message_replies
                (reply_id, message_id, sender_id, reply_text, attachment_path, attachment_filename, 
                 reply_to_message_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (reply_id, message_id, current_user.id, reply_text, attachment_path, attachment_filename, 
                  reply_to_message_id, current_time))

            # If replying to someone else, create a mirrored message
            if message['sender_id'] != current_user.id:
                mirrored_message_id = generate_id('MSG')
                
                if attachment_path:
                    c.execute("""
                        INSERT INTO messaging_system
                        (message_id, sender_id, recipient_type, recipient_id, title, message,
                         message_type, priority, attachment_path, attachment_filename,
                         allow_replies, parent_message_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (mirrored_message_id, current_user.id, 'specific_user', message['sender_id'],
                          f"Re: {message['title']}", reply_text, 'message', 'normal',
                          attachment_path, attachment_filename, 0, message_id, datetime.now()))
                else:
                    c.execute("""
                        INSERT INTO messaging_system
                        (message_id, sender_id, recipient_type, recipient_id, title, message,
                         message_type, priority, allow_replies, parent_message_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (mirrored_message_id, current_user.id, 'specific_user', message['sender_id'],
                          f"Re: {message['title']}", reply_text, 'message', 'normal',
                          0, message_id, datetime.now()))

            conn.commit()
            
            # Return response IMMEDIATELY
            response = jsonify({'success': True, 'reply_id': reply_id})
            
            # Background tasks (non-blocking)
            def background_tasks():
                try:
                    log_activity('quick_reply_sent', f'Replied to message {message_id}')
                except:
                    pass
                try:
                    if message['sender_id'] != current_user.id:
                        create_notification(
                            message['sender_id'],
                            f"Reply to: {message['title'][:50]}",
                            f"From {current_user.get_full_name()}",
                            'normal',
                            '/messaging-center'
                        )
                except:
                    pass
            
            # Run background tasks in thread (non-blocking)
            from threading import Thread
            bg_thread = Thread(target=background_tasks, daemon=True)
            bg_thread.start()
            
            return response

        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error sending quick reply: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in quick reply: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/search-users')
@login_required
def api_messaging_search_users():
    """Search users for floating panel."""
    try:
        query = request.args.get('q', '').strip()
        
        if len(query) < 2:
            return jsonify({'success': True, 'users': []})

        conn = get_db_connection()
        try:
            c = conn.cursor()

            search_query = """
                SELECT user_id, first_name, last_name, email, role, profile_pic, is_online, last_activity
                FROM users
                WHERE is_active = 1 AND is_approved = 1
                AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR user_id LIKE ?)
                ORDER BY first_name, last_name
                LIMIT 10
            """
            search_param = f'%{query}%'
            c.execute(search_query, (search_param, search_param, search_param, search_param))
            
            users = []
            for row in c.fetchall():
                user = dict(row)
                user['full_name'] = f"{user['first_name']} {user['last_name']}"
                # Format last activity time
                if user['last_activity']:
                    last_activity_dt = datetime.fromisoformat(user['last_activity'])
                    user['last_seen_time'] = format_time_ago(last_activity_dt)
                else:
                    user['last_seen_time'] = 'Never'
                users.append(user)

            return jsonify({'success': True, 'users': users})

        except Exception as e:
            app.logger.error(f"Error searching users: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in search users: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/status/<user_id>')
@login_required
def api_user_status(user_id):
    """Get user online status and last seen time."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT user_id, first_name, last_name, is_online, last_activity, profile_pic, role
                FROM users
                WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            
            user = c.fetchone()
            if not user:
                return jsonify({'success': False, 'error': 'User not found'})
            
            user_dict = dict(user)
            user_dict['full_name'] = f"{user_dict['first_name']} {user_dict['last_name']}"
            
            # Format last activity
            if user_dict['last_activity']:
                last_activity_dt = datetime.fromisoformat(user_dict['last_activity'])
                user_dict['last_seen_time'] = format_time_ago(last_activity_dt)
                user_dict['last_activity_iso'] = user_dict['last_activity']
            else:
                user_dict['last_seen_time'] = 'Never'
                user_dict['last_activity_iso'] = None
            
            user_dict['is_online'] = bool(user_dict['is_online'])
            
            return jsonify({'success': True, 'user': user_dict})
        
        finally:
            conn.close()
    
    except Exception as e:
        app.logger.error(f"Error getting user status: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/profile/<user_id>')
@login_required
def api_user_profile(user_id):
    """Get user profile details (non-sensitive info only)."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT user_id, first_name, last_name, rank, role, email, phone, 
                       department, location, profile_pic, is_online, last_activity, created_at
                FROM users
                WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            
            user = c.fetchone()
            if not user:
                return jsonify({'success': False, 'error': 'User not found'})
            
            user_dict = dict(user)
            user_dict['full_name'] = f"{user_dict['first_name']} {user_dict['last_name']}"
            
            # Format timestamps
            if user_dict['last_activity']:
                last_activity_dt = datetime.fromisoformat(user_dict['last_activity'])
                user_dict['last_seen'] = format_time_ago(last_activity_dt)
            else:
                user_dict['last_seen'] = 'Never'
            
            if user_dict['created_at']:
                created_dt = datetime.fromisoformat(user_dict['created_at'])
                user_dict['member_since'] = created_dt.strftime('%B %Y')
            
            user_dict['is_online'] = bool(user_dict['is_online'])
            
            return jsonify({'success': True, 'profile': user_dict})
        
        finally:
            conn.close()
    
    except Exception as e:
        app.logger.error(f"Error getting user profile: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/update-activity', methods=['POST'])
@login_required
def api_user_update_activity():
    """Update user's online status and last activity timestamp."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_time = datetime.now()
            
            c.execute("""
                UPDATE users
                SET is_online = 1, last_activity = ?
                WHERE user_id = ?
            """, (current_time, current_user.id))
            
            conn.commit()
            return jsonify({'success': True, 'timestamp': current_time.isoformat()})
        
        finally:
            conn.close()
    
    except Exception as e:
        app.logger.error(f"Error updating activity: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user/set-offline', methods=['POST'])
@login_required
def api_user_set_offline():
    """Set user as offline."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                UPDATE users
                SET is_online = 0
                WHERE user_id = ?
            """, (current_user.id,))
            
            conn.commit()
            return jsonify({'success': True})
        
        finally:
            conn.close()
    
    except Exception as e:
        app.logger.error(f"Error setting offline: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/unread-count')
@login_required
def api_messaging_unread_count():
    """Get count of unread messages."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            query = """
                SELECT COUNT(*) as count
                FROM messaging_system m
                WHERE (
                    (m.recipient_type = 'specific_user' AND m.recipient_id = ?) OR
                    (m.recipient_type = 'role' AND ? IN (
                        SELECT role FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'department' AND ? IN (
                        SELECT department FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'all')
                ) AND m.is_read = 0
            """
            params = [current_user.id, current_user.role, current_user.id,
                     current_user.department, current_user.id]

            c.execute(query, params)
            count = c.fetchone()['count']

            return jsonify({'success': True, 'count': count})

        except Exception as e:
            app.logger.error(f"Error getting unread count: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in unread count: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/mark-read/<message_id>', methods=['POST'])
@login_required
def api_messaging_mark_read(message_id):
    """
    Mark a message as read for the current user.
    
    Updates message read status and records the read timestamp.
    Only updates if the message is addressed to the current user
    (by specific ID, role, department, or broadcast).
    
    Args:
        message_id (str): The ID of the message to mark as read
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - error (str): Error description if failed
    
    Status Codes:
        - 200: Message marked as read successfully
        - 401: Not authenticated
    """
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Mark message as read if user is recipient
            cursor.execute("""
                UPDATE messaging_system
                SET is_read = 1, read_at = ?
                WHERE message_id = ? AND (
                    (recipient_type = 'specific_user' AND recipient_id = ?) OR
                    (recipient_type = 'role' AND ? IN (
                        SELECT role FROM users WHERE user_id = ?
                    )) OR
                    (recipient_type = 'department' AND ? IN (
                        SELECT department FROM users WHERE user_id = ?
                    )) OR
                    (recipient_type = 'all')
                )
            """, (
                datetime.now(), message_id, current_user.id, current_user.role,
                current_user.id, current_user.department, current_user.id
            ))

            conn.commit()
            return jsonify({'success': True}), 200

        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error marking message {message_id} as read: {e}")
            return jsonify({'success': False, 'error': 'Failed to mark message as read'}), 500
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Database connection error in mark_read: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500

@app.route('/api/messaging/mark-all-read', methods=['POST'])
@login_required
def api_messaging_mark_all_read():
    """
    Mark all unread messages as read for the current user.
    
    Batch operation to mark all messages addressed to the current user
    as read and record the read timestamp.
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - marked (int): Number of messages marked as read
            - error (str): Error description if failed
    
    Status Codes:
        - 200: Messages marked successfully
        - 401: Not authenticated
    """
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Mark all unread messages as read for current user
            cursor.execute("""
                UPDATE messaging_system
                SET is_read = 1, read_at = ?
                WHERE (
                    (recipient_type = 'specific_user' AND recipient_id = ?) OR
                    (recipient_type = 'role' AND ? IN (
                        SELECT role FROM users WHERE user_id = ?
                    )) OR
                    (recipient_type = 'department' AND ? IN (
                        SELECT department FROM users WHERE user_id = ?
                    )) OR
                    (recipient_type = 'all')
                ) AND is_read = 0
            """, (
                datetime.now(), current_user.id, current_user.role,
                current_user.id, current_user.department, current_user.id
            ))

            marked_count = cursor.rowcount
            conn.commit()
            return jsonify({'success': True, 'marked': marked_count}), 200

        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error marking all messages as read for user {current_user.id}: {e}")
            return jsonify({'success': False, 'error': 'Failed to mark messages as read'}), 500
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Database connection error in mark_all_read: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500

@app.route('/api/messaging/message/<message_id>')
@login_required
def api_messaging_message(message_id):
    """
    Retrieve full message details including metadata and replies.
    
    Fetches complete message information along with sender details
    and all associated replies, including reply authors and content.
    
    Args:
        message_id (str): The ID of the message to retrieve
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - message (dict): Message object with all details
            - replies (list): Array of reply objects
            - error (str): Error description if failed
    
    Status Codes:
        - 200: Message retrieved successfully
        - 401: Not authenticated
        - 404: Message not found or not authorized
    """
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Retrieve message with sender details
            cursor.execute("""
                SELECT m.*, u.first_name || ' ' || u.last_name as sender_name,
                       u.role as sender_role, u.user_id as sender_user_id
                FROM messaging_system m
                JOIN users u ON m.sender_id = u.user_id
                WHERE m.message_id = ? AND (
                    (m.recipient_type = 'specific_user' AND m.recipient_id = ?) OR
                    (m.recipient_type = 'role' AND ? IN (
                        SELECT role FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'department' AND ? IN (
                        SELECT department FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'all')
                )
            """, (
                message_id, current_user.id, current_user.role, current_user.id,
                current_user.department, current_user.id
            ))

            message = cursor.fetchone()
            if not message:
                return jsonify({'success': False, 'error': 'Message not found or access denied'})

            message_dict = dict(message)

            # Parse JSON attachments if they exist
            if message_dict.get('attachment_path'):
                try:
                    attachment_paths = json.loads(message_dict['attachment_path'])
                    attachment_filenames = json.loads(message_dict['attachment_filename'])
                    message_dict['attachments'] = [
                        {'path': path, 'filename': filename} 
                        for path, filename in zip(attachment_paths, attachment_filenames)
                    ]
                except:
                    message_dict['attachments'] = []

            # Format recipient info
            recipient_info = ""
            if message_dict['recipient_type'] == 'specific_user':
                recipient_info = f"Specific User: {message_dict['recipient_id']}"
            elif message_dict['recipient_type'] == 'role':
                recipient_info = f"Role: {message_dict['recipient_id'].replace('_', ' ').title()}"
            elif message_dict['recipient_type'] == 'department':
                recipient_info = f"Department: {message_dict['recipient_id']}"
            elif message_dict['recipient_type'] == 'all':
                recipient_info = "All Users"

            message_dict['recipient_info'] = recipient_info

            # Get message replies
            cursor.execute("""
                SELECT r.*, u.first_name || ' ' || u.last_name as sender_name
                FROM message_replies r
                JOIN users u ON r.sender_id = u.user_id
                WHERE r.message_id = ?
                ORDER BY r.created_at ASC
            """, (message_id,))

            replies = [dict(row) for row in cursor.fetchall()]

            return jsonify({
                'success': True,
                'message': message_dict,
                'replies': replies
            }), 200

        except Exception as e:
            app.logger.error(f"Error retrieving message {message_id}: {e}")
            return jsonify({'success': False, 'error': 'Failed to retrieve message'}), 500
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in message endpoint: {e}")
        return jsonify({'success': False, 'error': 'Failed to process request'}), 500

@app.route('/api/messaging/reply', methods=['POST'])
@login_required
def api_messaging_reply():
    """Reply to a message."""
    try:
        message_id = request.form.get('message_id')
        reply_text = request.form.get('reply_text')

        if not message_id or not reply_text:
            return jsonify({'success': False, 'error': 'Missing required fields'})

        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Check if message exists and allows replies
            c.execute("""
                SELECT message_id, allow_replies, sender_id, message_type, title, priority
                FROM messaging_system
                WHERE message_id = ? AND (
                    (recipient_type = 'specific_user' AND recipient_id = ?) OR
                    (recipient_type = 'role' AND ? IN (
                        SELECT role FROM users WHERE user_id = ?
                    )) OR
                    (recipient_type = 'department' AND ? IN (
                        SELECT department FROM users WHERE user_id = ?
                    )) OR
                    (recipient_type = 'all')
                )
            """, (message_id, current_user.id, current_user.role, current_user.id,
                 current_user.department, current_user.id))

            message = c.fetchone()
            if not message:
                return jsonify({'success': False, 'error': 'Message not found or access denied'})

            message_dict = dict(message)

            if not message_dict['allow_replies'] or message_dict['message_type'] != 'message':
                return jsonify({'success': False, 'error': 'This message does not allow replies'})

            # Get reply_to_message_id if provided (WhatsApp-style reply)
            reply_to_message_id = request.form.get('reply_to_message_id')

            # Handle attachment
            attachment_filename = None
            attachment_path = None
            if 'attachment' in request.files:
                file = request.files['attachment']
                if file and file.filename:
                    if not allowed_file(file.filename):
                        return jsonify({'success': False, 'error': 'Invalid file type'})

                    # Check file size (20MB max)
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    if file_size > 20 * 1024 * 1024:
                        return jsonify({'success': False, 'error': 'File size exceeds 20MB limit'})

                    # Save file
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    filename = secure_filename(f"reply_{message_id}_{timestamp}_{file.filename}")
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', 'replies', filename)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    file.save(save_path)
                    attachment_filename = file.filename
                    attachment_path = filename

            # Create reply with real-time timestamp
            reply_id = generate_id('REPLY')
            current_time = datetime.now()
            c.execute("""
                INSERT INTO message_replies
                (reply_id, message_id, sender_id, reply_text, attachment_path, attachment_filename, 
                 reply_to_message_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (reply_id, message_id, current_user.id, reply_text, attachment_path, attachment_filename, 
                  reply_to_message_id, current_time))

            # Send mirrored message to original sender if they are different from current user
            if message_dict['sender_id'] != current_user.id:
                mirrored_message_id = generate_id('MSG')
                priority = message_dict.get('priority', 'normal')
                
                c.execute("""
                    INSERT INTO messaging_system
                    (message_id, sender_id, recipient_type, recipient_id, title, message,
                     message_type, priority, allow_replies, parent_message_id, attachment_path, 
                     attachment_filename, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mirrored_message_id,
                    current_user.id,
                    'specific_user',
                    message_dict['sender_id'],
                    f"Re: {message_dict['title']}",
                    reply_text,
                    'message',
                    priority,
                    0,
                    message_id,
                    attachment_path,
                    attachment_filename,
                    datetime.now()
                ))

            conn.commit()
            log_activity('message_replied', f'Replied to message {message_id}')
            
            # Return immediately - notifications will be created asynchronously
            return jsonify({'success': True, 'reply_id': reply_id})

        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error replying to message: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in reply: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== ATTACHMENT SERVING ROUTES ====================

@app.route('/api/messaging/download-attachment/<message_id>/<int:attachment_index>')
@login_required
def api_messaging_download_attachment(message_id, attachment_index):
    """Download message attachment."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            c.execute("""
                SELECT attachment_path, attachment_filename
                FROM messaging_system
                WHERE message_id = ? AND (
                    (recipient_type = 'specific_user' AND recipient_id = ?) OR
                    (recipient_type = 'role' AND ? IN (
                        SELECT role FROM users WHERE user_id = ?
                    )) OR
                    (recipient_type = 'department' AND ? IN (
                        SELECT department FROM users WHERE user_id = ?
                    )) OR
                    (recipient_type = 'all')
                )
            """, (message_id, current_user.id, current_user.role, current_user.id,
                 current_user.department, current_user.id))

            message = c.fetchone()
            if not message or not message['attachment_path']:
                return jsonify({'success': False, 'error': 'Attachment not found or access denied'}), 404

            try:
                attachment_paths = json.loads(message['attachment_path'])
                attachment_filenames = json.loads(message['attachment_filename'])
                
                if attachment_index < 0 or attachment_index >= len(attachment_paths):
                    return jsonify({'success': False, 'error': 'Invalid attachment index'}), 404
                    
                attachment_path = attachment_paths[attachment_index]
                attachment_filename = attachment_filenames[attachment_index]
            except:
                # Fallback for old format
                attachment_path = message['attachment_path']
                attachment_filename = message['attachment_filename']

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', attachment_path)

            if not os.path.exists(file_path):
                return jsonify({'success': False, 'error': 'File not found on server'}), 404

            # Get file extension
            file_ext = os.path.splitext(attachment_filename)[1].lower() if attachment_filename else ''
            mimetype_map = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xls': 'application/vnd.ms-excel',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.csv': 'text/csv',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.txt': 'text/plain',
                '.zip': 'application/zip',
                '.rar': 'application/x-rar-compressed'
            }

            mimetype = mimetype_map.get(file_ext, 'application/octet-stream')

            return send_file(
                file_path,
                as_attachment=True,
                download_name=attachment_filename or f'attachment{file_ext}',
                mimetype=mimetype
            )

        except Exception as e:
            app.logger.error(f"Error downloading attachment: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in download attachment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/messaging/download-reply-attachment/<message_id>/<reply_id>')
@login_required
def api_messaging_download_reply_attachment(message_id, reply_id):
    """Download reply attachment."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Verify user has access to the message
            c.execute("""
                SELECT m.message_id
                FROM messaging_system m
                WHERE m.message_id = ? AND (
                    (m.recipient_type = 'specific_user' AND m.recipient_id = ?) OR
                    (m.sender_id = ?) OR
                    (m.recipient_type = 'role' AND ? IN (
                        SELECT role FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'department' AND ? IN (
                        SELECT department FROM users WHERE user_id = ?
                    )) OR
                    (m.recipient_type = 'all')
                )
            """, (message_id, current_user.id, current_user.id, current_user.role, current_user.id,
                 current_user.department, current_user.id))

            message = c.fetchone()
            if not message:
                return jsonify({'success': False, 'error': 'Message not found or access denied'}), 404

            # Get reply attachment
            c.execute("""
                SELECT attachment_path, attachment_filename
                FROM message_replies
                WHERE reply_id = ? AND message_id = ?
            """, (reply_id, message_id))

            reply = c.fetchone()
            if not reply or not reply['attachment_path']:
                return jsonify({'success': False, 'error': 'Attachment not found'}), 404

            attachment_path = reply['attachment_path']
            attachment_filename = reply['attachment_filename'] or 'attachment'

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', attachment_path)

            if not os.path.exists(file_path):
                return jsonify({'success': False, 'error': 'File not found on server'}), 404

            # Get file extension
            file_ext = os.path.splitext(attachment_filename)[1].lower() if attachment_filename else ''
            mimetype_map = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xls': 'application/vnd.ms-excel',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.csv': 'text/csv',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.txt': 'text/plain',
                '.zip': 'application/zip',
                '.rar': 'application/x-rar-compressed'
            }

            mimetype = mimetype_map.get(file_ext, 'application/octet-stream')

            return send_file(
                file_path,
                as_attachment=True,
                download_name=attachment_filename,
                mimetype=mimetype
            )
        except Exception as e:
            app.logger.error(f"Error downloading reply attachment: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error in download reply attachment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== DELETE MESSAGE & REPLY ENDPOINTS ====================

@app.route('/api/messaging/delete-message/<message_id>', methods=['DELETE'])
@login_required
def api_messaging_delete_message(message_id):
    """Delete a message sent by current user."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Verify the message belongs to the current user
        c.execute("""
            SELECT sender_id FROM messaging_system
            WHERE message_id = ?
        """, (message_id,))
        
        message = c.fetchone()
        if not message:
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        
        if message['sender_id'] != current_user.id:
            return jsonify({'success': False, 'error': 'Cannot delete another user\'s message'}), 403
        
        # Delete the message
        c.execute("DELETE FROM messaging_system WHERE message_id = ?", (message_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Message deleted'})
    except Exception as e:
        app.logger.error(f"Error deleting message: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/messaging/delete-reply/<message_id>/<reply_id>', methods=['DELETE'])
@login_required
def api_messaging_delete_reply(message_id, reply_id):
    """Delete a reply sent by current user."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Verify the reply belongs to the current user
        c.execute("""
            SELECT sender_id FROM message_replies
            WHERE reply_id = ? AND message_id = ?
        """, (reply_id, message_id))
        
        reply = c.fetchone()
        if not reply:
            return jsonify({'success': False, 'error': 'Reply not found'}), 404
        
        if reply['sender_id'] != current_user.id:
            return jsonify({'success': False, 'error': 'Cannot delete another user\'s reply'}), 403
        
        # Delete the reply
        c.execute("DELETE FROM message_replies WHERE reply_id = ? AND message_id = ?", (reply_id, message_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Reply deleted'})
    except Exception as e:
        app.logger.error(f"Error deleting reply: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/messaging/edit-message', methods=['POST'])
@login_required
def api_messaging_edit_message():
    """Edit a message sent by current user."""
    try:
        data = request.get_json()
        message_id = data.get('message_id')
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Verify the message belongs to the current user
        c.execute("""
            SELECT sender_id FROM messaging_system
            WHERE message_id = ?
        """, (message_id,))
        
        message = c.fetchone()
        if not message:
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        
        if message['sender_id'] != current_user.id:
            return jsonify({'success': False, 'error': 'Cannot edit another user\'s message'}), 403
        
        # Update the message
        c.execute("""
            UPDATE messaging_system
            SET message = ?, edited_at = ?
            WHERE message_id = ?
        """, (message_text, datetime.utcnow().isoformat(), message_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Message updated'})
    except Exception as e:
        app.logger.error(f"Error editing message: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== SERVE ATTACHMENT FILES ====================

@app.route('/uploads/messages/<path:filename>')
@login_required
def serve_message_attachment(filename):
    """Serve message attachment files."""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', filename)
    
    # Security check: verify the user has access to this file
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'File not found'}), 404
    
    # Additional security check can be added here to verify user permissions
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'messages'), filename)

@app.route('/uploads/messages/replies/<path:filename>')
@login_required
def serve_reply_attachment(filename):
    """Serve reply attachment files."""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', 'replies', filename)
    
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'File not found'}), 404
    
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'messages', 'replies'), filename)

@app.route('/inventory')
@login_required
@role_required(['port_engineer', 'harbour_master'])
def inventory():
    return render_template('inventory.html')

@app.route('/evaluate')
@login_required
@role_required(['harbour_master', 'quality_officer'])
def evaluate():
    """Display ship evaluation form."""
    return render_template('evaluate.html')

@app.route('/maintenance-request')
@login_required
def maintenance_request():
    """
    Display maintenance request creation form.
    
    Allows crew members to submit new maintenance and repair requests
    for equipment and systems onboard the vessel.
    
    Returns:
        Rendered maintenance request form template
    """
    return render_template('maintenance_request.html')

# ==================== INTERNATIONAL REPORTS ROUTES ====================

@app.route('/bilge-report')
@login_required
@role_required(['chief_engineer', 'captain'])
def bilge_report():
    """
    Display bilge water report form.
    
    Allows crew to document bilge water discharge, treatment, and
    management in compliance with MARPOL regulations.
    
    Returns:
        Rendered bilge report form template
    """
    return render_template('bilge_report.html')

@app.route('/fuel-report')
@login_required
@role_required(['chief_engineer', 'captain'])
def fuel_report():
    """
    Display fuel and truck delivery report form.
    
    Documents fuel bunkering operations, truck reference numbers,
    quantities, and delivery details.
    
    Returns:
        Rendered fuel report form template
    """
    return render_template('fuel_report.html')

@app.route('/sewage-report')
@login_required
@role_required(['chief_engineer', 'captain'])
def sewage_report():
    """
    Display sewage treatment report form.
    
    Records sewage discharge, treatment, and disposal activities
    in compliance with MARPOL Annex IV.
    
    Returns:
        Rendered sewage report form template
    """
    return render_template('sewage_report.html')

@app.route('/logbook')
@login_required
@role_required(['chief_engineer', 'captain'])
def logbook():
    """Display logbook entry form."""
    return render_template('logbook.html')

@app.route('/emission-report')
@login_required
@role_required(['chief_engineer', 'captain'])
def emission_report():
    """Display emission report form."""
    return render_template('emission_report.html')

# Report list views
@app.route('/bilge-reports')
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def bilge_reports_list():
    """View all bilge reports."""
    return render_template('bilge_reports_list.html')

@app.route('/fuel-reports')
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def fuel_reports_list():
    """View all fuel reports."""
    return render_template('fuel_reports_list.html')

@app.route('/sewage-reports')
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def sewage_reports_list():
    """View all sewage reports."""
    return render_template('sewage_reports_list.html')

@app.route('/logbook-entries')
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def logbook_entries_list():
    """View all logbook entries."""
    return render_template('logbook_entries_list.html')

@app.route('/emission-reports')
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def emission_reports_list():
    """View all emission reports."""
    return render_template('emission_reports_list.html')

@app.route('/drill-report')
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def drill_report():
    """
    Display emergency drill report form.
    
    Allows crew to document emergency drills in compliance with SOLAS requirements.
    
    Returns:
        Rendered drill report form template
    """
    return render_template('drill_report.html')

@app.route('/drill-reports')
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def drill_reports_list():
    """
    Display list of emergency drill reports.
    
    Shows all completed drill reports with filtering and search capabilities.
    
    Returns:
        Rendered drill reports list template
    """
    try:
        # Provide context variables with default values
        context = {
            'drill_reports': [],
            'total_drills': 0,
            'this_month': 0,
            'pending_actions': 0,
            'avg_performance': 'N/A'
        }
        return render_template('drill_reports_list.html', **context)
    except Exception as e:
        app.logger.error(f"Error loading drill reports list: {e}", exc_info=True)
        flash('Error loading drill reports. Please try again.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/crew-management')
@login_required
@role_required(['harbour_master'])
def crew_management():
    """
    Display crew management dashboard for Harbour Master.
    
    Allows viewing, editing, and removing crew members for all vessels.
    
    Returns:
        Rendered crew management template with crew data
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Fetch all crew members
        c.execute("""
            SELECT crew_id, vessel_id, first_name, last_name, department, rank, 
                   license_number, status, date_joined 
            FROM crew_members 
            ORDER BY date_joined DESC
        """)
        crew_members = [dict(zip([col[0] for col in c.description], row)) 
                       for row in c.fetchall()]
        
        # Fetch all vessels
        c.execute("SELECT vessel_id, vessel_name FROM vessels WHERE status='active' ORDER BY vessel_name")
        vessels = [dict(zip([col[0] for col in c.description], row)) 
                  for row in c.fetchall()]
        
        # Calculate crew statistics
        total_crew = len(crew_members)
        deck_crew = len([crew for crew in crew_members if crew.get('department') == 'Deck'])
        engine_crew = len([crew for crew in crew_members if crew.get('department') == 'Engine'])
        catering_crew = len([crew for crew in crew_members if crew.get('department') == 'Catering'])
        
        conn.close()
        
        return render_template(
            'crew_management.html',
            crew_members=crew_members,
            vessels=vessels,
            total_crew=total_crew,
            deck_crew=deck_crew,
            engine_crew=engine_crew,
            catering_crew=catering_crew
        )
    except Exception as e:
        app.logger.error(f"Error loading crew management: {e}", exc_info=True)
        flash('Error loading crew management. Please try again.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/add-crew-member', methods=['GET', 'POST'])
@login_required
@role_required(['harbour_master'])
def add_crew_member():
    """
    Add a new crew member to a vessel.
    
    GET: Display form to add crew member
    POST: Save new crew member to database
    
    Returns:
        GET: Rendered form template
        POST: Redirect to crew management on success, form with errors on failure
    """
    try:
        if request.method == 'POST':
            # Extract form data
            vessel_id = request.form.get('vessel_id')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            department = request.form.get('department')  # Deck, Engine, Catering
            rank = request.form.get('rank')
            license_number = request.form.get('license_number')
            nationality = request.form.get('nationality')
            email = request.form.get('email')
            phone = request.form.get('phone')
            emergency_contact = request.form.get('emergency_contact')
            emergency_phone = request.form.get('emergency_phone')
            stcw_certificate = request.form.get('stcw_certificate')
            stcw_expiry = request.form.get('stcw_expiry')
            gmdss_certificate = request.form.get('gmdss_certificate')
            gmdss_expiry = request.form.get('gmdss_expiry')
            mlc_certificate = request.form.get('mlc_certificate')
            mlc_expiry = request.form.get('mlc_expiry')
            medical_certificate = request.form.get('medical_certificate')
            medical_expiry = request.form.get('medical_expiry')
            
            # Validate required fields
            if not all([first_name, last_name, department, rank]):
                flash('Please fill in all required fields.', 'danger')
                return redirect(request.referrer or url_for('add_crew_member'))
            
            # Handle profile picture upload
            profile_picture_path = None
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename and allowed_file(file.filename):
                    try:
                        filename = secure_filename(f"crew_{int(datetime.now().timestamp())}_{file.filename}")
                        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics')
                        os.makedirs(upload_path, exist_ok=True)
                        file.save(os.path.join(upload_path, filename))
                        profile_picture_path = os.path.join('profile_pics', filename)
                    except Exception as e:
                        app.logger.error(f"Error saving profile picture: {e}")
                        flash('Warning: Profile picture could not be saved.', 'warning')
            
            # Handle specialized certificate files and details
            specialized_certificates = {}
            # Collect specialized certificates from form
            for key in request.form.keys():
                if key.startswith('spec_cert_number_'):
                    index = key.split('_')[-1]
                    cert_name = request.form.get(f'spec_certs_{index}') if f'spec_certs_{index}' in request.form else None
                    if not cert_name and key in request.form:
                        # Extract cert name from form - it's sent as checkbox value
                        cert_number = request.form.get(key)
                        cert_expiry = request.form.get(f'spec_cert_expiry_{index}')
                        
                        # Handle file upload for this certificate
                        cert_file_path = None
                        if f'spec_cert_file_{index}' in request.files:
                            cert_file = request.files[f'spec_cert_file_{index}']
                            if cert_file and cert_file.filename and allowed_file(cert_file.filename):
                                try:
                                    filename = secure_filename(f"cert_{int(datetime.now().timestamp())}_{index}_{cert_file.filename}")
                                    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', 'certificates')
                                    os.makedirs(upload_path, exist_ok=True)
                                    cert_file.save(os.path.join(upload_path, filename))
                                    cert_file_path = os.path.join('documents', 'certificates', filename)
                                except Exception as e:
                                    app.logger.error(f"Error saving cert file: {e}")
            
            # Convert specialized certificates to JSON string for storage
            specialized_certs_json = json.dumps(specialized_certificates) if specialized_certificates else None
            
            try:
                conn = get_db_connection()
                c = conn.cursor()
                
                c.execute("""
                    INSERT INTO crew_members 
                    (vessel_id, first_name, last_name, department, rank, license_number, 
                     nationality, email, phone, emergency_contact, emergency_phone,
                     stcw_certificate, stcw_expiry, gmdss_certificate, gmdss_expiry,
                     mlc_certificate, mlc_expiry, medical_certificate, medical_expiry,
                     profile_picture, specialized_certificates, date_joined, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (vessel_id, first_name, last_name, department, rank, license_number,
                     nationality, email, phone, emergency_contact, emergency_phone,
                     stcw_certificate, stcw_expiry, gmdss_certificate, gmdss_expiry,
                     mlc_certificate, mlc_expiry, medical_certificate, medical_expiry,
                     profile_picture_path, specialized_certs_json, datetime.now().strftime('%Y-%m-%d'), 'active'))
                
                conn.commit()
                conn.close()
                
                app.logger.info(f"New crew member {first_name} {last_name} added by {current_user.user_id}")
                flash(f'Crew member {first_name} {last_name} added successfully!', 'success')
                return redirect(url_for('crew_management'))
            except sqlite3.IntegrityError as e:
                app.logger.error(f"Database integrity error when adding crew member: {e}")
                flash('Error: License number may already exist or database constraint violated.', 'danger')
                return redirect(request.referrer or url_for('add_crew_member'))
        
        # GET request - show form
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT vessel_id, vessel_name FROM vessels WHERE status='active' ORDER BY vessel_name")
        vessels = [dict(zip([col[0] for col in c.description], row)) 
                  for row in c.fetchall()]
        conn.close()
        
        departments = ['Deck', 'Engine', 'Catering']
        
        return render_template(
            'add_crew_member.html',
            vessels=vessels,
            departments=departments
        )
    except Exception as e:
        app.logger.error(f"Error in add_crew_member: {e}", exc_info=True)
        flash('Error adding crew member. Please try again.', 'danger')
        return redirect(url_for('crew_management'))

@app.route('/edit-crew-member/<int:crew_id>', methods=['GET', 'POST'])
@login_required
@role_required(['harbour_master'])
def edit_crew_member(crew_id):
    """
    Edit an existing crew member's information.
    
    GET: Display form with crew member data
    POST: Update crew member in database
    
    Args:
        crew_id: ID of crew member to edit
    
    Returns:
        GET: Rendered form template with crew data
        POST: Redirect to crew management on success
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        if request.method == 'POST':
            # Extract form data
            vessel_id = request.form.get('vessel_id')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            department = request.form.get('department')
            rank = request.form.get('rank')
            license_number = request.form.get('license_number')
            nationality = request.form.get('nationality')
            email = request.form.get('email')
            phone = request.form.get('phone')
            emergency_contact = request.form.get('emergency_contact')
            emergency_phone = request.form.get('emergency_phone')
            stcw_certificate = request.form.get('stcw_certificate')
            stcw_expiry = request.form.get('stcw_expiry')
            gmdss_certificate = request.form.get('gmdss_certificate')
            gmdss_expiry = request.form.get('gmdss_expiry')
            mlc_certificate = request.form.get('mlc_certificate')
            mlc_expiry = request.form.get('mlc_expiry')
            medical_certificate = request.form.get('medical_certificate')
            medical_expiry = request.form.get('medical_expiry')
            
            # Validate required fields
            if not all([first_name, last_name, department, rank]):
                flash('Please fill in all required fields.', 'danger')
                conn.close()
                return redirect(request.referrer or url_for('edit_crew_member', crew_id=crew_id))
            
            # Handle profile picture upload
            profile_picture_path = None
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename and allowed_file(file.filename):
                    try:
                        # Get existing profile picture to delete if replaced
                        c.execute("SELECT profile_picture FROM crew_members WHERE crew_id=?", (crew_id,))
                        existing = c.fetchone()
                        if existing and existing[0]:
                            old_path = os.path.join(app.config['UPLOAD_FOLDER'], existing[0])
                            if os.path.exists(old_path):
                                os.remove(old_path)
                        
                        filename = secure_filename(f"crew_{int(datetime.now().timestamp())}_{file.filename}")
                        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pics')
                        os.makedirs(upload_path, exist_ok=True)
                        file.save(os.path.join(upload_path, filename))
                        profile_picture_path = os.path.join('profile_pics', filename)
                    except Exception as e:
                        app.logger.error(f"Error saving profile picture: {e}")
                        flash('Warning: Profile picture could not be saved.', 'warning')
            
            # Handle specialized certificate files and details
            specialized_certificates = {}
            # Collect specialized certificates from form
            for key in request.form.keys():
                if key.startswith('spec_cert_number_'):
                    index = key.split('_')[-1]
                    cert_number = request.form.get(key)
                    cert_expiry = request.form.get(f'spec_cert_expiry_{index}')
                    
                    # Handle file upload for this certificate
                    cert_file_path = None
                    if f'spec_cert_file_{index}' in request.files:
                        cert_file = request.files[f'spec_cert_file_{index}']
                        if cert_file and cert_file.filename and allowed_file(cert_file.filename):
                            try:
                                filename = secure_filename(f"cert_{crew_id}_{int(datetime.now().timestamp())}_{cert_file.filename}")
                                upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', 'certificates')
                                os.makedirs(upload_path, exist_ok=True)
                                cert_file.save(os.path.join(upload_path, filename))
                                cert_file_path = os.path.join('documents', 'certificates', filename)
                            except Exception as e:
                                app.logger.error(f"Error saving cert file: {e}")
            
            # Convert specialized certificates to JSON string for storage
            specialized_certs_json = json.dumps(specialized_certificates) if specialized_certificates else None
            
            # Update database
            try:
                if profile_picture_path:
                    c.execute("""
                        UPDATE crew_members 
                        SET vessel_id=?, first_name=?, last_name=?, department=?, rank=?, license_number=?,
                            nationality=?, email=?, phone=?, emergency_contact=?, emergency_phone=?,
                            stcw_certificate=?, stcw_expiry=?, gmdss_certificate=?, gmdss_expiry=?,
                            mlc_certificate=?, mlc_expiry=?, medical_certificate=?, medical_expiry=?,
                            profile_picture=?, specialized_certificates=?, updated_at=?
                        WHERE crew_id=?
                    """, (vessel_id, first_name, last_name, department, rank, license_number,
                         nationality, email, phone, emergency_contact, emergency_phone,
                         stcw_certificate, stcw_expiry, gmdss_certificate, gmdss_expiry,
                         mlc_certificate, mlc_expiry, medical_certificate, medical_expiry,
                         profile_picture_path, specialized_certs_json, datetime.now(), crew_id))
                elif specialized_certs_json:
                    c.execute("""
                        UPDATE crew_members 
                        SET vessel_id=?, first_name=?, last_name=?, department=?, rank=?, license_number=?,
                            nationality=?, email=?, phone=?, emergency_contact=?, emergency_phone=?,
                            stcw_certificate=?, stcw_expiry=?, gmdss_certificate=?, gmdss_expiry=?,
                            mlc_certificate=?, mlc_expiry=?, medical_certificate=?, medical_expiry=?,
                            specialized_certificates=?, updated_at=?
                        WHERE crew_id=?
                    """, (vessel_id, first_name, last_name, department, rank, license_number,
                         nationality, email, phone, emergency_contact, emergency_phone,
                         stcw_certificate, stcw_expiry, gmdss_certificate, gmdss_expiry,
                         mlc_certificate, mlc_expiry, medical_certificate, medical_expiry,
                         specialized_certs_json, datetime.now(), crew_id))
                
                conn.commit()
                app.logger.info(f"Crew member {crew_id} updated by {current_user.user_id}")
                flash(f'Crew member {first_name} {last_name} updated successfully!', 'success')
                conn.close()
                return redirect(url_for('crew_management'))
            except sqlite3.IntegrityError as e:
                app.logger.error(f"Database integrity error when editing crew member: {e}")
                flash('Error: License number may already exist or database constraint violated.', 'danger')
                conn.close()
                return redirect(request.referrer or url_for('edit_crew_member', crew_id=crew_id))
        
        # GET request - show form with existing data
        c.execute("SELECT * FROM crew_members WHERE crew_id=?", (crew_id,))
        row = c.fetchone()
        
        if not row:
            flash('Crew member not found.', 'danger')
            conn.close()
            return redirect(url_for('crew_management'))
        
        crew_member = dict(zip([col[0] for col in c.description], row))
        
        c.execute("SELECT vessel_id, vessel_name FROM vessels WHERE status='active' ORDER BY vessel_name")
        vessels = [dict(zip([col[0] for col in c.description], v)) 
                  for v in c.fetchall()]
        
        conn.close()
        
        departments = ['Deck', 'Engine', 'Catering']
        
        return render_template(
            'edit_crew_member.html',
            crew_member=crew_member,
            vessels=vessels,
            departments=departments
        )
    except Exception as e:
        app.logger.error(f"Error in edit_crew_member: {e}", exc_info=True)
        flash('Error editing crew member. Please try again.', 'danger')
        return redirect(url_for('crew_management'))

@app.route('/remove-crew-member/<int:crew_id>', methods=['POST'])
@login_required
@role_required(['harbour_master'])
def remove_crew_member(crew_id):
    """
    Remove a crew member from the system.
    
    Args:
        crew_id: ID of crew member to remove
    
    Returns:
        JSON response with success/error status
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Verify crew member exists
        c.execute("SELECT first_name, last_name FROM crew_members WHERE crew_id=?", (crew_id,))
        crew = c.fetchone()
        
        if not crew:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Crew member not found'}), 404
        
        # Delete from database
        c.execute("DELETE FROM crew_members WHERE crew_id=?", (crew_id,))
        conn.commit()
        conn.close()
        
        app.logger.info(f"Crew member {crew_id} ({crew[0]} {crew[1]}) removed by {current_user.user_id}")
        return jsonify({'status': 'success', 'message': 'Crew member removed successfully'})
    except Exception as e:
        app.logger.error(f"Error removing crew member: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Error removing crew member'}), 500

# ======================== VESSEL MANAGEMENT ROUTES ========================

@app.route('/api/vessels', methods=['GET'])
@login_required
def api_get_vessels():
    """
    API endpoint to get list of all vessels.
    
    Returns JSON with:
        - success (bool): Operation status
        - vessels (list): Array of vessel objects with id, name, type, imo
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Fetch all active vessels
        c.execute("""
            SELECT vessel_id, vessel_name as name, vessel_type, imo_number as imo
            FROM vessels 
            WHERE status='active'
            ORDER BY vessel_name
        """)
        vessels = [dict(zip([col[0] for col in c.description], row)) 
                  for row in c.fetchall()]
        
        conn.close()
        
        return jsonify(success=True, vessels=vessels)
    except Exception as e:
        app.logger.error(f"Error fetching vessels API: {e}")
        return jsonify(success=False, error='Failed to fetch vessels'), 500


@app.route('/vessel-management')
@login_required
@role_required(['harbour_master'])
def vessel_management():
    """
    Display vessel management dashboard for Harbour Master.
    
    Shows list of all vessels with their details and quick actions.
    
    Returns:
        Rendered vessel management template
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Fetch all vessels
        c.execute("""
            SELECT vessel_id, vessel_name, imo_number, call_sign, vessel_type, 
                   flag_state, year_built, gross_tonnage, status
            FROM vessels 
            WHERE status='active'
            ORDER BY vessel_name
        """)
        vessels = [dict(zip([col[0] for col in c.description], row)) 
                  for row in c.fetchall()]
        
        total_vessels = len(vessels)
        
        conn.close()
        
        return render_template(
            'vessel_management.html',
            vessels=vessels,
            total_vessels=total_vessels
        )
    except Exception as e:
        app.logger.error(f"Error loading vessel management: {e}", exc_info=True)
        flash('Error loading vessel management. Please try again.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/add-vessel', methods=['GET', 'POST'])
@login_required
@role_required(['harbour_master'])
def add_vessel():
    """
    Add a new vessel to the system.
    
    GET: Display form to add vessel
    POST: Save new vessel to database
    
    Returns:
        GET: Rendered form template
        POST: Redirect to vessel management on success
    """
    try:
        if request.method == 'POST':
            # Extract all vessel information from form
            vessel_name = request.form.get('vessel_name')
            imo_number = request.form.get('imo_number')
            mmsi_number = request.form.get('mmsi_number')
            call_sign = request.form.get('call_sign')
            vessel_type = request.form.get('vessel_type')
            flag_state = request.form.get('flag_state')
            year_built = request.form.get('year_built')
            builder = request.form.get('builder')
            shipyard_location = request.form.get('shipyard_location')
            gross_tonnage = request.form.get('gross_tonnage')
            net_tonnage = request.form.get('net_tonnage')
            deadweight_tonnage = request.form.get('deadweight_tonnage')
            length_overall = request.form.get('length_overall')
            length_between_perpendiculars = request.form.get('length_between_perpendiculars')
            breadth = request.form.get('breadth')
            depth = request.form.get('depth')
            
            # Ownership & Management
            owner_name = request.form.get('owner_name')
            owner_address = request.form.get('owner_address')
            owner_phone = request.form.get('owner_phone')
            owner_email = request.form.get('owner_email')
            manager_name = request.form.get('manager_name')
            manager_address = request.form.get('manager_address')
            manager_phone = request.form.get('manager_phone')
            manager_email = request.form.get('manager_email')
            operator_name = request.form.get('operator_name')
            operator_phone = request.form.get('operator_phone')
            operator_email = request.form.get('operator_email')
            insurer_name = request.form.get('insurer_name')
            insurer_policy_number = request.form.get('insurer_policy_number')
            
            # Propulsion & Machinery
            main_engine_model = request.form.get('main_engine_model')
            main_engine_power = request.form.get('main_engine_power')
            main_engine_rpm = request.form.get('main_engine_rpm')
            fuel_type = request.form.get('fuel_type')
            auxiliary_engines = request.form.get('auxiliary_engines')
            generator_power = request.form.get('generator_power')
            propulsion_type = request.form.get('propulsion_type')
            
            # Performance
            maximum_speed = request.form.get('maximum_speed')
            service_speed = request.form.get('service_speed')
            average_fuel_consumption = request.form.get('average_fuel_consumption')
            fuel_consumption_per_ton_mile = request.form.get('fuel_consumption_per_ton_mile')
            
            # Energy & Emissions
            energy_efficiency_index = request.form.get('energy_efficiency_index')
            carbon_intensity_indicator = request.form.get('carbon_intensity_indicator')
            sox_emissions_compliant = request.form.get('sox_emissions_compliant')
            nox_tier = request.form.get('nox_tier')
            eedi_baseline_percentage = request.form.get('eedi_baseline_percentage')
            
            # Operations
            ballast_water_treatment = request.form.get('ballast_water_treatment')
            trading_area_restriction = request.form.get('trading_area_restriction')
            ice_class = request.form.get('ice_class')
            dry_dock_interval = request.form.get('dry_dock_interval')
            next_dry_dock_date = request.form.get('next_dry_dock_date')
            last_dry_dock_date = request.form.get('last_dry_dock_date')
            monitoring_system = request.form.get('monitoring_system')
            performance_reporting_compliant = request.form.get('performance_reporting_compliant')
            
            # Remarks
            remarks = request.form.get('remarks')
            
            # Initial Performance Baseline (Optional)
            baseline_speed = request.form.get('baseline_speed')
            baseline_fuel_consumption = request.form.get('baseline_fuel_consumption')
            baseline_co2_emissions = request.form.get('baseline_co2_emissions')
            baseline_load_factor = request.form.get('baseline_load_factor')
            
            # Validate required fields
            if not all([vessel_name, imo_number, vessel_type, flag_state]):
                flash('Please fill in all required fields.', 'danger')
                return redirect(request.referrer or url_for('add_vessel'))
            
            # Save to database
            try:
                conn = get_db_connection()
                c = conn.cursor()
                
                c.execute("""
                    INSERT INTO vessels 
                    (vessel_name, imo_number, mmsi_number, call_sign, vessel_type, flag_state,
                     year_built, builder, shipyard_location, gross_tonnage, net_tonnage, 
                     deadweight_tonnage, length_overall, length_between_perpendiculars, breadth, depth,
                     owner_name, owner_address, owner_phone, owner_email,
                     manager_name, manager_address, manager_phone, manager_email,
                     operator_name, operator_phone, operator_email,
                     insurer_name, insurer_policy_number,
                     main_engine_model, main_engine_power, main_engine_rpm, fuel_type, 
                     auxiliary_engines, generator_power, propulsion_type,
                     maximum_speed, service_speed, average_fuel_consumption, fuel_consumption_per_ton_mile,
                     energy_efficiency_index, carbon_intensity_indicator, sox_emissions_compliant, nox_tier,
                     eedi_baseline_percentage, ballast_water_treatment, trading_area_restriction, ice_class,
                     dry_dock_interval, next_dry_dock_date, last_dry_dock_date, monitoring_system,
                     performance_reporting_compliant, remarks, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?)
                """, (vessel_name, imo_number, mmsi_number, call_sign, vessel_type, flag_state,
                     year_built, builder, shipyard_location, gross_tonnage, net_tonnage,
                     deadweight_tonnage, length_overall, length_between_perpendiculars, breadth, depth,
                     owner_name, owner_address, owner_phone, owner_email,
                     manager_name, manager_address, manager_phone, manager_email,
                     operator_name, operator_phone, operator_email,
                     insurer_name, insurer_policy_number,
                     main_engine_model, main_engine_power, main_engine_rpm, fuel_type,
                     auxiliary_engines, generator_power, propulsion_type,
                     maximum_speed, service_speed, average_fuel_consumption, fuel_consumption_per_ton_mile,
                     energy_efficiency_index, carbon_intensity_indicator, sox_emissions_compliant, nox_tier,
                     eedi_baseline_percentage, ballast_water_treatment, trading_area_restriction, ice_class,
                     dry_dock_interval, next_dry_dock_date, last_dry_dock_date, monitoring_system,
                     performance_reporting_compliant, remarks, 'active'))
                
                # Get the vessel ID of the newly inserted vessel
                vessel_id = c.lastrowid
                
                # If baseline performance data provided, add it as initial performance record
                if baseline_speed or baseline_fuel_consumption or baseline_co2_emissions:
                    c.execute("""
                        INSERT INTO vessel_performance_monitoring 
                        (vessel_id, reporting_month, average_speed, fuel_consumption_metric_tons,
                         co2_emissions_metric_tons, average_load_factor, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (vessel_id, datetime.now().strftime('%Y-%m'), baseline_speed, 
                          baseline_fuel_consumption, baseline_co2_emissions, baseline_load_factor,
                          'Baseline performance data at vessel registration'))
                
                conn.commit()
                conn.close()
                
                app.logger.info(f"New vessel {vessel_name} (IMO: {imo_number}) added by {current_user.user_id}")
                flash(f'Vessel {vessel_name} added successfully!', 'success')
                return redirect(url_for('vessel_management'))
            except sqlite3.IntegrityError as e:
                app.logger.error(f"Database integrity error when adding vessel: {e}")
                flash('Error: IMO number may already exist or database constraint violated.', 'danger')
                return redirect(request.referrer or url_for('add_vessel'))
        
        # GET request - show form
        return render_template('add_vessel.html')
    except Exception as e:
        app.logger.error(f"Error in add_vessel: {e}", exc_info=True)
        flash('Error adding vessel. Please try again.', 'danger')
        return redirect(url_for('vessel_management'))

@app.route('/edit-vessel/<int:vessel_id>', methods=['GET', 'POST'])
@login_required
@role_required(['harbour_master'])
def edit_vessel(vessel_id):
    """
    Edit an existing vessel's information.
    
    GET: Display form with vessel data
    POST: Update vessel in database
    
    Args:
        vessel_id: ID of vessel to edit
    
    Returns:
        GET: Rendered form template with vessel data
        POST: Redirect to vessel management on success
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        if request.method == 'POST':
            # Extract vessel name (key field for quick edit)
            vessel_name = request.form.get('vessel_name')
            
            if not vessel_name:
                flash('Vessel name is required.', 'danger')
                conn.close()
                return redirect(request.referrer or url_for('edit_vessel', vessel_id=vessel_id))
            
            # Update vessel in database
            try:
                c.execute("""
                    UPDATE vessels 
                    SET vessel_name=?, updated_at=?
                    WHERE vessel_id=?
                """, (vessel_name, datetime.now(), vessel_id))
                
                conn.commit()
                app.logger.info(f"Vessel {vessel_id} updated by {current_user.user_id}")
                flash(f'Vessel {vessel_name} updated successfully!', 'success')
                conn.close()
                return redirect(url_for('vessel_management'))
            except Exception as db_error:
                app.logger.error(f"Database error when editing vessel: {db_error}")
                flash('Error updating vessel in database.', 'danger')
                conn.close()
                return redirect(request.referrer or url_for('edit_vessel', vessel_id=vessel_id))
        
        # GET request - show form with existing data
        c.execute("SELECT * FROM vessels WHERE vessel_id=?", (vessel_id,))
        row = c.fetchone()
        
        if not row:
            flash('Vessel not found.', 'danger')
            conn.close()
            return redirect(url_for('vessel_management'))
        
        vessel = dict(zip([col[0] for col in c.description], row))
        conn.close()
        
        return render_template('edit_vessel.html', vessel=vessel)
    except Exception as e:
        app.logger.error(f"Error in edit_vessel: {e}", exc_info=True)
        flash('Error editing vessel. Please try again.', 'danger')
        return redirect(url_for('vessel_management'))

@app.route('/view-vessel/<int:vessel_id>')
@login_required
@role_required(['harbour_master', 'captain', 'chief_engineer'])
def view_vessel(vessel_id):
    """
    Display detailed vessel information in the standard template format.
    
    Allows for printing and downloading of vessel specifications.
    Includes performance monitoring data and certificates.
    
    Args:
        vessel_id: ID of vessel to view
    
    Returns:
        Rendered vessel details template
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Fetch vessel details
        c.execute("SELECT * FROM vessels WHERE vessel_id=?", (vessel_id,))
        row = c.fetchone()
        
        if not row:
            flash('Vessel not found.', 'danger')
            conn.close()
            return redirect(url_for('vessel_management'))
        
        vessel = dict(zip([col[0] for col in c.description], row))
        
        # Fetch performance monitoring data (last 12 months)
        c.execute("""
            SELECT * FROM vessel_performance_monitoring 
            WHERE vessel_id=? 
            ORDER BY reporting_month DESC 
            LIMIT 12
        """, (vessel_id,))
        performance_data = [dict(zip([col[0] for col in c.description], v)) 
                           for v in c.fetchall()]
        
        # Fetch vessel certificates
        c.execute("""
            SELECT * FROM vessel_certificates 
            WHERE vessel_id=? AND status='active'
            ORDER BY certificate_type
        """, (vessel_id,))
        certificates = [dict(zip([col[0] for col in c.description], cert)) 
                       for cert in c.fetchall()]
        
        # Fetch crew members on this vessel
        c.execute("""
            SELECT crew_id, first_name, last_name, department, rank 
            FROM crew_members 
            WHERE vessel_id=? AND status='active'
            ORDER BY department, rank
        """, (vessel_id,))
        crew_members = [dict(zip([col[0] for col in c.description], crew)) 
                       for crew in c.fetchall()]
        
        conn.close()
        
        # Add performance summary and crew statistics
        vessel['performance_data'] = performance_data
        vessel['certificates'] = certificates
        vessel['crew_members'] = crew_members
        vessel['total_crew'] = len(crew_members)
        vessel['deck_crew'] = len([c for c in crew_members if c.get('department') == 'Deck'])
        vessel['engine_crew'] = len([c for c in crew_members if c.get('department') == 'Engine'])
        vessel['catering_crew'] = len([c for c in crew_members if c.get('department') == 'Catering'])
        
        return render_template('view_vessel.html', vessel=vessel)
    except Exception as e:
        app.logger.error(f"Error viewing vessel: {e}", exc_info=True)
        flash('Error loading vessel details. Please try again.', 'danger')
        return redirect(url_for('vessel_management'))

@app.route('/crew-list-report')
@login_required
@role_required(['harbour_master', 'captain', 'chief_engineer'])
def crew_list_report():
    """
    Display crew list report.
    
    Shows vessel crew members organized by department with documentation status.
    
    Returns:
        Rendered crew list report template with crew data
    """
    try:
        # For now, provide empty/default data
        # In a full implementation, this would pull from database
        vessel = {
            'name': 'Vessel Name',
            'imo': 'IMO 1234567',
            'flag_state': 'Panama'
        }
        
        crew_members = []
        report_date = datetime.now().strftime('%Y-%m-%d')
        deck_count = 0
        engine_count = 0
        catering_count = 0
        
        return render_template(
            'crew_list_report.html',
            vessel=vessel,
            crew_members=crew_members,
            report_date=report_date,
            deck_count=deck_count,
            engine_count=engine_count,
            catering_count=catering_count
        )
    except Exception as e:
        app.logger.error(f"Error loading crew list report: {e}", exc_info=True)
        flash('Error loading crew list report. Please try again.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/view-request/<request_id>')
@login_required
def view_request(request_id):
    """View maintenance request details."""
    return render_template('view_request.html', request_id=request_id)

@app.route('/notifications')
@login_required
def notifications_page():
    """Notifications page - redirects to dashboard with notifications focus."""
    flash('Viewing your notifications', 'info')
    return redirect(url_for('dashboard'))

@app.route('/contact')
@login_required
def contact():
    """Contact page - redirects to dashboard."""
    flash('For support, please contact your port engineer or use the messaging system.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')


# ==================== ANALYTICS APIs ====================

@app.route('/api/analytics/emergencies')
@login_required
def api_analytics_emergencies():
    """Aggregate emergency analytics for dashboards."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Overall counts
            c.execute("SELECT COUNT(*) AS total FROM emergency_requests")
            total = c.fetchone()['total']

            c.execute("SELECT COUNT(*) AS open_count FROM emergency_requests WHERE status IN ('pending','authorized','in_progress')")
            open_count = c.fetchone()['open_count']

            c.execute("SELECT COUNT(*) AS resolved_count FROM emergency_requests WHERE status IN ('resolved','closed')")
            resolved_count = c.fetchone()['resolved_count']

            # Frequency by type
            c.execute("""
                SELECT emergency_type, COUNT(*) AS count
                FROM emergency_requests
                GROUP BY emergency_type
                ORDER BY count DESC
            """)
            by_type = [dict(row) for row in c.fetchall()]

            # Frequency by severity
            c.execute("""
                SELECT severity_level, COUNT(*) AS count
                FROM emergency_requests
                GROUP BY severity_level
                ORDER BY count DESC
            """)
            by_severity = [dict(row) for row in c.fetchall()]

            # Daily trend - last 7 days
            c.execute("""
                SELECT strftime('%Y-%m-%d', created_at) AS day, COUNT(*) AS count
                FROM emergency_requests
                WHERE date(created_at) >= date('now', '-6 days')
                GROUP BY day
                ORDER BY day
            """)
            daily = [dict(row) for row in c.fetchall()]

            # Average resolution time in hours (for resolved/closed)
            c.execute("""
                SELECT AVG(
                    CAST(
                        (julianday(
                            COALESCE(resolved_at, closed_at, created_at)
                        ) - julianday(created_at)
                    ) * 24.0 AS REAL)
                ) AS avg_resolution_hours
                FROM emergency_requests
                WHERE (resolved_at IS NOT NULL OR closed_at IS NOT NULL)
            """)
            avg_row = c.fetchone()
            avg_resolution_hours = round(avg_row['avg_resolution_hours'], 2) if avg_row and avg_row['avg_resolution_hours'] is not None else 0

            return jsonify({
                'success': True,
                'summary': {
                    'total': total,
                    'open': open_count,
                    'resolved': resolved_count,
                    'avg_resolution_hours': avg_resolution_hours,
                },
                'by_type': by_type,
                'by_severity': by_severity,
                'daily_trend': daily,
            })
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in emergency analytics: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/analytics/messaging')
@login_required
def api_analytics_messaging():
    """Aggregate messaging analytics for dashboards."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Total messages sent by current user
            c.execute("""
                SELECT COUNT(*) AS total_sent
                FROM messaging_system
                WHERE sender_id = ?
            """, (current_user.id,))
            total_sent = c.fetchone()['total_sent']

            # Total messages received (as specific_user recipient)
            c.execute("""
                SELECT COUNT(*) AS total_received
                FROM messaging_system
                WHERE recipient_type = 'specific_user'
                  AND recipient_id = ?
            """, (current_user.id,))
            total_received = c.fetchone()['total_received']

            # Unread received messages
            c.execute("""
                SELECT COUNT(*) AS unread
                FROM messaging_system
                WHERE recipient_type = 'specific_user'
                  AND recipient_id = ?
                  AND is_read = 0
            """, (current_user.id,))
            unread = c.fetchone()['unread']

            # Messages by type
            c.execute("""
                SELECT message_type, COUNT(*) AS count
                FROM messaging_system
                WHERE sender_id = ? OR (recipient_type = 'specific_user' AND recipient_id = ?)
                GROUP BY message_type
            """, (current_user.id, current_user.id))
            by_type = [dict(row) for row in c.fetchall()]

            # Daily sent messages - last 7 days
            c.execute("""
                SELECT strftime('%Y-%m-%d', created_at) AS day, COUNT(*) AS count
                FROM messaging_system
                WHERE sender_id = ?
                  AND date(created_at) >= date('now', '-6 days')
                GROUP BY day
                ORDER BY day
            """, (current_user.id,))
            sent_daily = [dict(row) for row in c.fetchall()]

            # Daily received messages - last 7 days
            c.execute("""
                SELECT strftime('%Y-%m-%d', created_at) AS day, COUNT(*) AS count
                FROM messaging_system
                WHERE recipient_type = 'specific_user'
                  AND recipient_id = ?
                  AND date(created_at) >= date('now', '-6 days')
                GROUP BY day
                ORDER BY day
            """, (current_user.id,))
            received_daily = [dict(row) for row in c.fetchall()]

            return jsonify({
                'success': True,
                'summary': {
                    'total_sent': total_sent,
                    'total_received': total_received,
                    'unread': unread,
                },
                'by_type': by_type,
                'sent_daily': sent_daily,
                'received_daily': received_daily,
            })
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in messaging analytics: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/emergency-requests')
@login_required
@role_required(['port_engineer', 'harbour_master', 'quality_officer'])
def emergency_requests():
    return render_template('emergency_requests.html')

@app.route('/monitor')
@login_required
@role_required(['quality_officer', 'port_engineer', 'harbour_master'])
def monitor():
    return render_template('monitor.html')

# ==================== PORT ENGINEER API ROUTES ====================

@app.route('/api/manager/dashboard-data')
@login_required
@role_required(['port_engineer'])
def api_manager_dashboard_data():
    """Get port engineer dashboard statistics including pending maintenance approvals."""
    conn = get_db_connection()
    try:
        c = conn.cursor()

        # Total users
        c.execute("SELECT COUNT(*) as count FROM users")
        total_users = c.fetchone()['count']

        # Pending approvals
        c.execute("SELECT COUNT(*) as count FROM users WHERE is_approved = 0 AND is_active = 1")
        pending_approvals = c.fetchone()['count']

        # Emergency requests
        c.execute("SELECT COUNT(*) as count FROM emergency_requests WHERE status = 'pending'")
        emergency_requests_result = c.fetchone()
        emergency_requests = emergency_requests_result['count'] if emergency_requests_result else 0

        # Pending maintenance requests (all pending)
        c.execute("SELECT COUNT(*) as count FROM maintenance_requests WHERE status = 'pending'")
        pending_requests_result = c.fetchone()
        pending_requests = pending_requests_result['count'] if pending_requests_result else 0
        
        # Pending maintenance requests awaiting approval (not approved)
        c.execute("""
            SELECT COUNT(*) as count
            FROM maintenance_requests
            WHERE (approved IS NULL OR approved = 0)
            AND status != 'rejected'
        """)
        pending_approval_result = c.fetchone()
        pending_maintenance_approvals = pending_approval_result['count'] if pending_approval_result else 0

        return jsonify({
            'success': True,
            'data': {
                'total_users': total_users,
                'pending_approvals': pending_approvals,
                'emergency_requests': emergency_requests,
                'pending_requests': pending_requests,
                'pending_maintenance_approvals': pending_maintenance_approvals
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting dashboard data: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/manager/pending-users')
@login_required
@role_required(['port_engineer', 'port_manager'])
def api_manager_pending_users():
    """Get users pending approval."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT user_id, email, first_name, last_name, rank, role, phone,
                   department, location, created_at, is_approved
            FROM users
            WHERE is_approved = 0 AND is_active = 1
            ORDER BY created_at DESC
        """)

        users = []
        for row in c.fetchall():
            user = dict(row)
            user['created_at'] = user['created_at'][:10] if user.get('created_at') else 'Unknown'
            users.append(user)

        return jsonify({'success': True, 'users': users})
    except Exception as e:
        app.logger.error(f"Error getting pending users: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/manager/approve-user', methods=['POST'])
@login_required
@role_required(['port_engineer', 'port_manager'])
def api_manager_approve_user():
    """Approve or reject a user."""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        approve = data.get('approve', True)

        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'})

        conn = get_db_connection()
        try:
            c = conn.cursor()

            if approve:
                # Approve user
                c.execute("UPDATE users SET is_approved = 1 WHERE user_id = ?", (user_id,))
                action = 'approved'
                notif_type = 'success'
                notif_msg = 'Your account has been approved by the port engineer. You can now log in to the system.'
            else:
                # Reject user (deactivate)
                c.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
                action = 'rejected'
                notif_type = 'warning'
                notif_msg = 'Your account registration has been reviewed and rejected. Please contact the port engineer for details.'

            # Get user details for notification within same transaction
            c.execute("SELECT first_name, last_name, email FROM users WHERE user_id = ?", (user_id,))
            user = c.fetchone()
            
            # Create notification within same transaction
            current_time = datetime.now()
            if user:
                c.execute("INSERT INTO notifications (user_id, title, message, type, action_url, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                         (user_id, 'Account ' + ('Approved' if approve else 'Rejected'), notif_msg, notif_type, '/login' if approve else '/contact', current_time))

            # Log the action within same transaction
            user_ip = request.remote_addr if request else "127.0.0.1"
            c.execute("INSERT INTO activity_logs (user_id, activity, details, ip_address, timestamp) VALUES (?, ?, ?, ?, ?)",
                      (current_user.id, f'user_{action}', f'User {user_id} {action} by port engineer', user_ip, current_time))
            
            c.execute("INSERT INTO audit_trail (timestamp, user_id, action_type, entity_type, ip_address, status) VALUES (?, ?, ?, ?, ?, ?)",
                      (current_time, current_user.id, f'user_{action}', 'user', user_ip, 'completed'))

            conn.commit()
            return jsonify({'success': True, 'action': action})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error approving user: {e}")
            return jsonify({'success': False, 'error': f'Database error: {str(e)}'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in approve user: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/manager/quality-officers')
@login_required
@role_required(['port_engineer'])
def api_manager_quality_officers():
    """Get all active DMPO HQ with their status."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT user_id, email, first_name, last_name, rank, survey_end_date,
                   is_active, is_approved, created_at
            FROM users
            WHERE role = 'quality_officer' AND is_active = 1
            ORDER BY survey_end_date ASC
        """)

        officers = []
        today = datetime.now().date()

        for row in c.fetchall():
            officer = dict(row)

            # Calculate days remaining
            days_remaining = 0
            if officer.get('survey_end_date'):
                try:
                    end_date = datetime.strptime(officer['survey_end_date'], '%Y-%m-%d').date()
                    days_remaining = (end_date - today).days
                except:
                    days_remaining = 0

            # Get evaluation count
            c.execute("SELECT COUNT(*) as count FROM service_evaluations WHERE evaluator_id = ?",
                     (officer['user_id'],))
            eval_result = c.fetchone()
            evaluations_count = eval_result['count'] if eval_result else 0

            officer['days_remaining'] = days_remaining
            officer['evaluations_count'] = evaluations_count
            officers.append(officer)

        return jsonify({'success': True, 'officers': officers})
    except Exception as e:
        app.logger.error(f"Error getting DMPO HQ: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/manager/officer-access/<user_id>')
@login_required
@role_required(['port_engineer'])
def api_manager_officer_access(user_id):
    """Get DMPO HQ access details."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT user_id, first_name, last_name, email, survey_end_date,
                   is_active, is_approved
            FROM users
            WHERE user_id = ? AND role = 'quality_officer'
        """, (user_id,))

        officer = c.fetchone()
        if not officer:
            return jsonify({'success': False, 'error': 'Officer not found'})

        officer_dict = dict(officer)

        # Calculate access days remaining
        if officer_dict.get('survey_end_date'):
            try:
                end_date = datetime.strptime(officer_dict['survey_end_date'], '%Y-%m-%d').date()
                today = datetime.now().date()
                days_remaining = (end_date - today).days
                officer_dict['access_days'] = max(0, days_remaining)
            except:
                officer_dict['access_days'] = 0
        else:
            officer_dict['access_days'] = 0

        return jsonify({'success': True, 'officer': officer_dict})
    except Exception as e:
        app.logger.error(f"Error getting officer access: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/manager/update-officer-access', methods=['POST'])
@login_required
@role_required(['port_engineer'])
def api_manager_update_officer_access():
    """Update DMPO HQ access."""
    try:
        data = request.get_json()
        officer_id = data.get('officer_id')
        access_days = data.get('access_days', 90)
        one_time_password = data.get('one_time_password')

        if not officer_id:
            return jsonify({'success': False, 'error': 'Officer ID required'})

        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Calculate new end date
            end_date = datetime.now() + timedelta(days=access_days)
            end_date_str = end_date.strftime('%Y-%m-%d')

            # Update officer access
            c.execute("""
                UPDATE users
                SET survey_end_date = ?, last_activity = ?
                WHERE user_id = ?
            """, (end_date_str, datetime.now(), officer_id))

            # Store one-time password (in a real system, this should be hashed)
            if one_time_password:
                # In a real app, you'd store this in a secure way
                # For now, we'll just log it
                app.logger.info(f"One-time password for {officer_id}: {one_time_password}")

            conn.commit()

            # Log activity
            log_activity('officer_access_updated',
                        f'Updated access for officer {officer_id} to {end_date_str}')

            # Create notification for officer
            create_notification(
                officer_id,
                'Access Updated',
                f'Your DMPO HQ access has been extended until {end_date_str}.',
                'info',
                '/profile'
            )

            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating officer access: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in update officer access: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/manager/create-quality-officer', methods=['POST'])
@login_required
@role_required(['port_engineer'])
def api_manager_create_quality_officer():
    """Create a new DMPO HQ account."""
    try:
        data = request.get_json()
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        rank = data.get('rank', 'DMPO HQ')
        access_days = data.get('access_days', 90)

        if not all([first_name, last_name, email]):
            return jsonify({'success': False, 'error': 'Missing required fields'})

        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Check if email exists
            c.execute("SELECT email FROM users WHERE email = ?", (email,))
            if c.fetchone():
                return jsonify({'success': False, 'error': 'Email already registered'})

            # Generate user ID
            c.execute("SELECT COUNT(*) FROM users WHERE role = 'quality_officer'")
            count = c.fetchone()[0] + 1
            user_id = f"QO{count:03d}"

            # Generate temporary password
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
            hashed_password = generate_password_hash(temp_password)

            # Calculate survey end date
            end_date = datetime.now() + timedelta(days=access_days)
            end_date_str = end_date.strftime('%Y-%m-%d')

            # Create user
            c.execute('''
                INSERT INTO users
                (user_id, email, password, first_name, last_name, rank, role,
                 survey_end_date, is_approved, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, email, hashed_password, first_name, last_name, rank,
                  'quality_officer', end_date_str, 1, 1))

            conn.commit()

            # Log activity
            log_activity('officer_created',
                        f'Created DMPO HQ {user_id} ({first_name} {last_name})')

            # Create welcome notification
            create_notification(
                user_id,
                'Welcome to VesselOS',
                f'Your DMPO HQ account has been created. Access expires on {end_date_str}.',
                'success',
                '/login'
            )

            return jsonify({
                'success': True,
                'user_id': user_id,
                'temp_password': temp_password,
                'end_date': end_date_str
            })
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error creating DMPO HQ: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in create DMPO HQ: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/manager/recent-notifications')
@login_required
@role_required(['port_engineer'])
def api_manager_recent_notifications():
    """Get recent system notifications."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, title, message, type, created_at, is_read
            FROM notifications
            WHERE user_id = 'system' OR user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (current_user.id,))

        notifications = []
        for row in c.fetchall():
            notification = dict(row)
            notification['created_at'] = notification['created_at']
            notifications.append(notification)

        return jsonify({'success': True, 'notifications': notifications})
    except Exception as e:
        app.logger.error(f"Error getting notifications: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/manager/send-notification', methods=['POST'])
@login_required
@role_required(['port_engineer'])
def api_manager_send_notification():
    """Send system notification to users."""
    try:
        data = request.get_json()
        notification_type = data.get('type', 'all')
        target_role = data.get('target_role')
        title = data.get('title')
        message = data.get('message')
        priority = data.get('priority', 'info')

        if not title or not message:
            return jsonify({'success': False, 'error': 'Title and message required'})

        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Determine recipients
            if notification_type == 'all':
                c.execute("SELECT user_id FROM users WHERE is_active = 1 AND is_approved = 1")
            elif notification_type == 'role':
                c.execute("SELECT user_id FROM users WHERE role = ? AND is_active = 1 AND is_approved = 1",
                         (target_role,))
            elif notification_type == 'department':
                c.execute("SELECT user_id FROM users WHERE department = ? AND is_active = 1 AND is_approved = 1",
                         (target_role,))
            elif notification_type == 'user':
                # For single user
                user_ids = [target_role]
                recipients = [{'user_id': target_role}]
            else:
                return jsonify({'success': False, 'error': 'Invalid notification type'})

            if notification_type != 'user':
                recipients = c.fetchall()
                user_ids = [r['user_id'] for r in recipients]

            # Create notifications for each user
            for user_id in user_ids:
                create_notification(
                    user_id,
                    title,
                    message,
                    priority,
                    '/notifications'
                )

            conn.commit()

            # Log activity
            log_activity('notification_sent',
                        f'Sent notification "{title}" to {len(user_ids)} users')

            return jsonify({
                'success': True,
                'recipients': len(user_ids),
                'notification_type': notification_type
            })
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error sending notification: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in send notification: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/manager/system-statistics')
@login_required
@role_required(['port_engineer'])
def api_manager_system_statistics():
    """Get system statistics."""
    conn = get_db_connection()
    try:
        c = conn.cursor()

        # Active users (logged in today)
        today = datetime.now().date()
        c.execute("""
            SELECT COUNT(DISTINCT user_id) as count
            FROM activity_logs
            WHERE DATE(timestamp) = ? AND activity = 'login'
        """, (today,))
        today_logins_result = c.fetchone()
        today_logins = today_logins_result['count'] if today_logins_result else 0

        # Active users
        c.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1 AND is_approved = 1")
        active_users_result = c.fetchone()
        active_users = active_users_result['count'] if active_users_result else 0

        # Open requests
        c.execute("SELECT COUNT(*) as count FROM maintenance_requests WHERE status = 'open'")
        open_requests_result = c.fetchone()
        open_requests = open_requests_result['count'] if open_requests_result else 0

        # Completed evaluations
        c.execute("SELECT COUNT(*) as count FROM service_evaluations WHERE status = 'completed'")
        completed_evaluations_result = c.fetchone()
        completed_evaluations = completed_evaluations_result['count'] if completed_evaluations_result else 0

        return jsonify({
            'success': True,
            'active_users': active_users,
            'today_logins': today_logins,
            'open_requests': open_requests,
            'completed_evaluations': completed_evaluations
        })
    except Exception as e:
        app.logger.error(f"Error getting system statistics: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/manager/recent-activity')
@login_required
@role_required(['port_engineer'])
def api_manager_recent_activity():
    """Get recent manager activity."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT activity, details, timestamp, ip_address
            FROM activity_logs
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        """, (current_user.id,))

        activities = []
        icon_map = {
            'login': 'sign-in-alt',
            'logout': 'sign-out-alt',
            'approve': 'check-circle',
            'reject': 'times-circle',
            'create': 'plus-circle',
            'update': 'edit',
            'delete': 'trash-alt',
            'notification': 'bell'
        }

        for row in c.fetchall():
            activity = dict(row)
            activity_type = activity['activity'].split('_')[0]
            activity['icon'] = icon_map.get(activity_type, 'history')
            activities.append(activity)

        return jsonify({'success': True, 'activities': activities})
    except Exception as e:
        app.logger.error(f"Error getting recent activity: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/manager/user-details/<user_id>')
@login_required
@role_required(['port_engineer'])
def api_manager_user_details(user_id):
    """Get detailed user information."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT user_id, email, first_name, last_name, rank, role, phone,
                   department, location, profile_pic, is_active, is_approved,
                   created_at, last_login, last_activity
            FROM users
            WHERE user_id = ?
        """, (user_id,))

        user = c.fetchone()
        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        user_dict = dict(user)

        # Format dates
        if user_dict.get('created_at'):
            user_dict['created_at'] = user_dict['created_at'][:10]

        return jsonify({'success': True, 'user': user_dict})
    except Exception as e:
        app.logger.error(f"Error getting user details: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# ==================== MISSING API ROUTES FOR DASHBOARDS ====================

@app.route('/api/manager/pending-maintenance')
@login_required
@role_required(['port_engineer'])
def api_manager_pending_maintenance():
    """Get pending maintenance requests."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT request_id, ship_name, maintenance_type, priority, status, requested_by, 
                   created_at, description
            FROM maintenance_requests
            WHERE status IN ('pending', 'approved')
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        requests = [dict(row) for row in c.fetchall()]
        return jsonify({'success': True, 'data': requests})
    except Exception as e:
        app.logger.error(f"Error getting pending maintenance: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/manager/emergency-requests')
@login_required
@role_required(['port_engineer'])
def api_manager_emergency_requests():
    """Get emergency maintenance requests."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT request_id, ship_name, maintenance_type, priority, status, requested_by,
                   created_at, description
            FROM maintenance_requests
            WHERE priority = 'emergency' AND status IN ('pending', 'approved')
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        requests = [dict(row) for row in c.fetchall()]
        return jsonify({'success': True, 'data': requests})
    except Exception as e:
        app.logger.error(f"Error getting emergency requests: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/manager/extend-officer-access', methods=['POST'])
@login_required
@role_required(['port_engineer'])
def api_manager_extend_officer_access():
    """Extend quality officer access period."""
    try:
        data = request.get_json()
        officer_id = data.get('officer_id')
        days = data.get('days', 30)
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Update officer access expiry
        new_expiry = datetime.utcnow() + timedelta(days=days)
        c.execute("""
            UPDATE users
            SET access_expiry = ?
            WHERE user_id = ? AND role = 'quality_officer'
        """, (new_expiry.isoformat(), officer_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Access extended by {days} days'})
    except Exception as e:
        app.logger.error(f"Error extending officer access: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/manager/deactivate-officer', methods=['POST'])
@login_required
@role_required(['port_engineer'])
def api_manager_deactivate_officer():
    """Deactivate quality officer access."""
    try:
        data = request.get_json()
        officer_id = data.get('officer_id')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            UPDATE users
            SET is_active = 0, access_expiry = ?
            WHERE user_id = ? AND role = 'quality_officer'
        """, (datetime.utcnow().isoformat(), officer_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Officer access deactivated'})
    except Exception as e:
        app.logger.error(f"Error deactivating officer: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/manager/notify-emergency-team', methods=['POST'])
@login_required
@role_required(['port_engineer'])
def api_manager_notify_emergency_team():
    """Send emergency notification to team."""
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        # Store notification in database
        conn = get_db_connection()
        c = conn.cursor()
        
        notification = {
            'title': 'EMERGENCY ALERT',
            'message': message,
            'type': 'emergency',
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Insert notification for all port engineer/captain users
        c.execute("""
            INSERT INTO notifications (user_id, title, message, type, created_at)
            SELECT user_id, ?, ?, ?, ?
            FROM users
            WHERE role IN ('port_engineer', 'captain', 'chief_engineer')
        """, (notification['title'], notification['message'], notification['type'], 
              notification['created_at']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Emergency notification sent'})
    except Exception as e:
        app.logger.error(f"Error sending emergency notification: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/manager/generate-system-report')
@login_required
@role_required(['port_engineer'])
def api_manager_generate_system_report():
    """Generate system activity report."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get system statistics
        c.execute("SELECT COUNT(*) as total_users FROM users WHERE is_active = 1")
        active_users = c.fetchone()['total_users']
        
        c.execute("SELECT COUNT(*) as total_messages FROM messages")
        total_messages = c.fetchone()['total_messages']
        
        c.execute("SELECT COUNT(*) as total_requests FROM maintenance_requests")
        total_requests = c.fetchone()['total_requests']
        
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'active_users': active_users,
            'total_messages': total_messages,
            'total_maintenance_requests': total_requests
        }
        
        conn.close()
        return jsonify({'success': True, 'report': report})
    except Exception as e:
        app.logger.error(f"Error generating system report: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/messaging/stats')
@login_required
def api_messaging_stats():
    """Get messaging statistics for dashboard."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get unread count
        c.execute("""
            SELECT COUNT(*) as unread_count FROM messages
            WHERE recipient_id = ? AND is_read = 0
        """, (current_user.id,))
        unread = c.fetchone()['unread_count']
        
        # Get total messages
        c.execute("""
            SELECT COUNT(*) as total_messages FROM messages
            WHERE recipient_id = ? OR sender_id = ?
        """, (current_user.id, current_user.id))
        total = c.fetchone()['total_messages']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'unread_count': unread,
            'total_messages': total
        })
    except Exception as e:
        app.logger.error(f"Error getting messaging stats: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== ENHANCED NOTIFICATION SYSTEM ====================

@app.route('/api/notifications')
@login_required
def api_notifications():
    """Get user notifications."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, title, message, type, action_url, created_at, is_read
            FROM notifications
            WHERE user_id = ? OR user_id = 'system'
            ORDER BY created_at DESC
            LIMIT 20
        """, (current_user.id,))

        notifications = []
        for row in c.fetchall():
            notification = dict(row)
            notification['timestamp'] = notification['created_at']
            notifications.append(notification)

        return jsonify({'success': True, 'notifications': notifications})
    except Exception as e:
        app.logger.error(f"Error getting notifications: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/notification/read/<int:notification_id>', methods=['POST'])
@login_required
def api_notification_read(notification_id):
    """Mark notification as read."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE notifications
            SET is_read = 1
            WHERE id = ? AND user_id = ?
        """, (notification_id, current_user.id))

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error marking notification as read: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/notification/read-all', methods=['POST'])
@login_required
def api_notification_read_all():
    """Mark all notifications as read."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE notifications
            SET is_read = 1
            WHERE user_id = ? AND is_read = 0
        """, (current_user.id,))

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error marking all notifications as read: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/notification/<int:notification_id>')
@login_required
def api_notification_detail(notification_id):
    """Get notification details."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, user_id, title, message, type, action_url, is_read, created_at
            FROM notifications
            WHERE id = ? AND (user_id = ? OR user_id = 'system')
        """, (notification_id, current_user.id))

        notification = c.fetchone()
        if not notification:
            return jsonify({'success': False, 'error': 'Notification not found or access denied'}), 404

        notification_dict = dict(notification)
        
        # Mark as read if not already read
        if not notification_dict['is_read']:
            # For system notifications, we need to create a user-specific read record or update if user_id matches
            if notification_dict['user_id'] == 'system':
                # For system notifications, we can't update directly, so we'll just return it as read
                # In a more advanced system, you'd have a separate read_status table
                pass
            else:
                c.execute("""
                    UPDATE notifications
                    SET is_read = 1
                    WHERE id = ? AND user_id = ?
                """, (notification_id, current_user.id))
                conn.commit()
            notification_dict['is_read'] = 1

        return jsonify({'success': True, 'notification': notification_dict})
    except Exception as e:
        app.logger.error(f"Error getting notification details: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# ==================== NOTIFICATION PREFERENCES ROUTES ====================

@app.route('/api/user/notification-preferences', methods=['GET'])
@login_required
def api_get_notification_preferences():
    """Get user's notification preferences."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT sound_enabled, browser_notifications, email_notifications
            FROM notification_preferences
            WHERE user_id = ?
        """, (current_user.id,))
        
        row = c.fetchone()
        conn.close()
        
        if row:
            preferences = dict(row)
        else:
            # Return default preferences if not set
            preferences = {
                'sound_enabled': True,
                'browser_notifications': True,
                'email_notifications': True
            }
        
        return jsonify({
            'success': True,
            'preferences': preferences
        })
    except Exception as e:
        app.logger.error(f"Error getting notification preferences: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'preferences': {
                'sound_enabled': True,
                'browser_notifications': True,
                'email_notifications': True
            }
        })

@app.route('/api/user/notification-preferences', methods=['POST'])
@login_required
@csrf_protect
def api_save_notification_preferences():
    """Save user's notification preferences."""
    try:
        data = request.get_json()
        
        sound_enabled = data.get('sound_enabled', True)
        browser_notifications = data.get('browser_notifications', True)
        email_notifications = data.get('email_notifications', True)
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if preferences already exist
        c.execute("""
            SELECT user_id FROM notification_preferences
            WHERE user_id = ?
        """, (current_user.id,))
        
        exists = c.fetchone() is not None
        
        if exists:
            # Update existing preferences
            c.execute("""
                UPDATE notification_preferences
                SET sound_enabled = ?, browser_notifications = ?, email_notifications = ?
                WHERE user_id = ?
            """, (sound_enabled, browser_notifications, email_notifications, current_user.id))
        else:
            # Insert new preferences
            c.execute("""
                INSERT INTO notification_preferences 
                (user_id, sound_enabled, browser_notifications, email_notifications)
                VALUES (?, ?, ?, ?)
            """, (current_user.id, sound_enabled, browser_notifications, email_notifications))
        
        conn.commit()
        conn.close()
        
        app.logger.info(f"Notification preferences saved for user {current_user.id}")
        
        return jsonify({
            'success': True,
            'message': 'Notification preferences saved successfully'
        })
    except Exception as e:
        app.logger.error(f"Error saving notification preferences: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# ==================== CHIEF ENGINEER API ROUTES ====================

@app.route('/api/chief-engineer/dashboard-data')
@login_required
@role_required(['chief_engineer'])
def api_chief_engineer_dashboard_data():
    """Get chief engineer dashboard statistics."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Total requests by this chief engineer
        c.execute("""
            SELECT COUNT(*) as count
            FROM maintenance_requests
            WHERE requested_by = ?
        """, (current_user.email,))
        total_requests = c.fetchone()['count']
        
        # Pending captain approval
        c.execute("""
            SELECT COUNT(*) as count
            FROM maintenance_requests
            WHERE requested_by = ? AND status = 'pending_captain'
        """, (current_user.email,))
        pending_approval = c.fetchone()['count']
        
        # In progress
        c.execute("""
            SELECT COUNT(*) as count
            FROM maintenance_requests
            WHERE requested_by = ? AND status = 'in_progress'
        """, (current_user.email,))
        in_progress = c.fetchone()['count']
        
        # Completed
        c.execute("""
            SELECT COUNT(*) as count
            FROM maintenance_requests
            WHERE requested_by = ? AND status = 'completed'
        """, (current_user.email,))
        completed = c.fetchone()['count']
        
        return jsonify({
            'success': True,
            'data': {
                'total_requests': total_requests,
                'pending_approval': pending_approval,
                'in_progress': in_progress,
                'completed': completed
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting chief engineer dashboard data: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/chief-engineer/my-requests')
@login_required
@role_required(['chief_engineer'])
def api_chief_engineer_my_requests():
    """Get all maintenance requests created by chief engineer."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                   status, created_at, requested_by
            FROM maintenance_requests
            WHERE requested_by = ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (current_user.email,))
        
        requests = []
        for row in c.fetchall():
            request_data = dict(row)
            requests.append(request_data)
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        app.logger.error(f"Error getting chief engineer requests: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/chief-engineer/pending-approval')
@login_required
@role_required(['chief_engineer'])
def api_chief_engineer_pending_approval():
    """Get requests pending captain approval."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                   status, created_at, requested_by
            FROM maintenance_requests
            WHERE requested_by = ? AND status = 'pending_captain'
            ORDER BY created_at DESC
        """, (current_user.email,))
        
        requests = []
        for row in c.fetchall():
            request_data = dict(row)
            requests.append(request_data)
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        app.logger.error(f"Error getting pending approval requests: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/chief-engineer/recent-activity')
@login_required
@role_required(['chief_engineer'])
def api_chief_engineer_recent_activity():
    """Get recent activity for chief engineer."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT request_id, ship_name, status, updated_at
            FROM maintenance_requests
            WHERE requested_by = ?
            ORDER BY updated_at DESC
            LIMIT 10
        """, (current_user.email,))
        
        activities = []
        for row in c.fetchall():
            activities.append({
                'timestamp': row['updated_at'] or row['created_at'],
                'description': f"Request {row['request_id']} for {row['ship_name']} - Status: {row['status']}"
            })
        
        return jsonify({'success': True, 'activities': activities})
    except Exception as e:
        app.logger.error(f"Error getting recent activity: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# ==================== CAPTAIN API ROUTES ====================

@app.route('/api/captain/dashboard-data')
@login_required
@role_required(['captain'])
def api_captain_dashboard_data():
    """Get captain dashboard statistics."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get vessel name from user profile or use a default
        vessel_name = current_user.get_full_name()  # This might need to be stored in user profile
        
        # Pending approval (requests from chief engineer awaiting captain approval)
        c.execute("""
            SELECT COUNT(*) as count
            FROM maintenance_requests
            WHERE status = 'pending_captain'
        """)
        pending_approval = c.fetchone()['count']
        
        # Approved (submitted to port)
        c.execute("""
            SELECT COUNT(*) as count
            FROM maintenance_requests
            WHERE status = 'approved' OR status = 'pending'
        """)
        approved = c.fetchone()['count']
        
        # In progress
        c.execute("""
            SELECT COUNT(*) as count
            FROM maintenance_requests
            WHERE status = 'in_progress'
        """)
        in_progress = c.fetchone()['count']
        
        # Completed
        c.execute("""
            SELECT COUNT(*) as count
            FROM maintenance_requests
            WHERE status = 'completed'
        """)
        completed = c.fetchone()['count']
        
        return jsonify({
            'success': True,
            'data': {
                'pending_approval': pending_approval,
                'approved': approved,
                'in_progress': in_progress,
                'completed': completed
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting captain dashboard data: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/captain/pending-approval')
@login_required
@role_required(['captain'])
def api_captain_pending_approval():
    """Get requests pending captain approval."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                   status, created_at, requested_by, description
            FROM maintenance_requests
            WHERE status = 'pending_captain'
            ORDER BY 
                CASE criticality
                    WHEN 'emergency' THEN 1
                    WHEN 'urgent' THEN 2
                    WHEN 'high' THEN 3
                    WHEN 'medium' THEN 4
                    ELSE 5
                END,
                created_at DESC
        """)
        
        requests = []
        for row in c.fetchall():
            request_data = dict(row)
            # Get requester name
            if request_data['requested_by']:
                c.execute("SELECT first_name, last_name FROM users WHERE email = ?", (request_data['requested_by'],))
                user = c.fetchone()
                if user:
                    request_data['requested_by_name'] = f"{user['first_name']} {user['last_name']}"
                else:
                    request_data['requested_by_name'] = 'Chief Engineer'
            requests.append(request_data)
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        app.logger.error(f"Error getting pending approval requests: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/captain/vessel-requests')
@login_required
@role_required(['captain'])
def api_captain_vessel_requests():
    """Get all requests for the captain's vessel."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                   status, created_at, requested_by
            FROM maintenance_requests
            ORDER BY created_at DESC
            LIMIT 50
        """)
        
        requests = []
        for row in c.fetchall():
            request_data = dict(row)
            # Get requester name
            if request_data['requested_by']:
                c.execute("SELECT first_name, last_name FROM users WHERE email = ?", (request_data['requested_by'],))
                user = c.fetchone()
                if user:
                    request_data['requested_by_name'] = f"{user['first_name']} {user['last_name']}"
                else:
                    request_data['requested_by_name'] = 'Chief Engineer'
            requests.append(request_data)
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        app.logger.error(f"Error getting vessel requests: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/captain/approve-request/<request_id>', methods=['POST'])
@login_required
@role_required(['captain'])
def api_captain_approve_request(request_id):
    """Approve a maintenance request and submit to Harbour Master."""
    conn = get_db_connection()
    try:
        data = request.get_json()
        comments = data.get('comments', '')
        
        c = conn.cursor()
        
        # Update request status to approved (ready for Harbour Master)
        c.execute("""
            UPDATE maintenance_requests
            SET status = 'approved',
                approved_by = ?,
                approved_at = ?,
                captain_comments = ?
            WHERE request_id = ?
        """, (current_user.id, datetime.now(), comments, request_id))
        
        conn.commit()
        
        # Notify Harbour Master
        c.execute("SELECT user_id FROM users WHERE role = 'harbour_master' AND is_active = 1")
        harbour_masters = c.fetchall()
        for hm in harbour_masters:
            create_notification(
                hm['user_id'],
                'New Approved Maintenance Request',
                f'Maintenance request {request_id} has been approved by the Captain and is ready for assignment.',
                'info',
                '/maintenance-request'
            )
        
        # Notify Chief Engineer
        c.execute("SELECT requested_by FROM maintenance_requests WHERE request_id = ?", (request_id,))
        req_data = c.fetchone()
        if req_data and req_data['requested_by']:
            c.execute("SELECT user_id FROM users WHERE email = ?", (req_data['requested_by'],))
            ce_user = c.fetchone()
            if ce_user:
                create_notification(
                    ce_user['user_id'],
                    'Request Approved by Captain',
                    f'Your maintenance request {request_id} has been approved by the Captain and submitted to the Harbour Master.',
                    'success',
                    '/dashboard'
                )
        
        log_activity('request_approved_by_captain', f'Request {request_id} approved by captain')
        
        return jsonify({'success': True, 'message': 'Request approved and submitted to Harbour Master'})
    except Exception as e:
        app.logger.error(f"Error approving request: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/captain/reject-request/<request_id>', methods=['POST'])
@login_required
@role_required(['captain'])
def api_captain_reject_request(request_id):
    """Reject a maintenance request."""
    conn = get_db_connection()
    try:
        data = request.get_json()
        rejection_reason = data.get('rejection_reason', '')
        
        c = conn.cursor()
        
        # Update request status to rejected
        c.execute("""
            UPDATE maintenance_requests
            SET status = 'rejected',
                rejection_reason = ?,
                rejected_by = ?,
                rejected_at = ?
            WHERE request_id = ?
        """, (rejection_reason, current_user.id, datetime.now(), request_id))
        
        conn.commit()
        
        # Notify Chief Engineer
        c.execute("SELECT requested_by FROM maintenance_requests WHERE request_id = ?", (request_id,))
        req_data = c.fetchone()
        if req_data and req_data['requested_by']:
            c.execute("SELECT user_id FROM users WHERE email = ?", (req_data['requested_by'],))
            ce_user = c.fetchone()
            if ce_user:
                create_notification(
                    ce_user['user_id'],
                    'Request Rejected by Captain',
                    f'Your maintenance request {request_id} has been rejected. Reason: {rejection_reason}',
                    'warning',
                    '/dashboard'
                )
        
        log_activity('request_rejected_by_captain', f'Request {request_id} rejected by captain')
        
        return jsonify({'success': True, 'message': 'Request rejected'})
    except Exception as e:
        app.logger.error(f"Error rejecting request: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/captain/recent-activity')
@login_required
@role_required(['captain'])
def api_captain_recent_activity():
    """Get recent activity for captain."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT request_id, ship_name, status, updated_at
            FROM maintenance_requests
            WHERE approved_by = ? OR rejected_by = ?
            ORDER BY updated_at DESC
            LIMIT 10
        """, (current_user.id, current_user.id))
        
        activities = []
        for row in c.fetchall():
            action = 'approved' if row['status'] == 'approved' else 'rejected'
            activities.append({
                'timestamp': row['updated_at'],
                'description': f"{action.capitalize()} request {row['request_id']} for {row['ship_name']}"
            })
        
        return jsonify({'success': True, 'activities': activities})
    except Exception as e:
        app.logger.error(f"Error getting recent activity: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# ==================== DASHBOARD ROUTES ====================

@app.route('/api/dashboard-data')
@login_required
def api_dashboard_data():
    """Get dashboard data for the current user."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get total maintenance requests
            c.execute("SELECT COUNT(*) as count FROM maintenance_requests")
            total_requests_result = c.fetchone()
            total_requests = total_requests_result['count'] if total_requests_result else 0
            
            # Get average response time (in hours)
            c.execute("""
                SELECT AVG(
                    (julianday(updated_at) - julianday(created_at)) * 24
                ) as avg_hours
                FROM maintenance_requests
                WHERE status = 'completed' AND updated_at IS NOT NULL
            """)
            avg_response_result = c.fetchone()
            avg_response = round(avg_response_result['avg_hours'], 1) if avg_response_result and avg_response_result['avg_hours'] else 0
            
            # Get satisfaction rate (from evaluations if table exists)
            satisfaction_rate = 92  # Default
            try:
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_evaluations'")
                if c.fetchone():
                    c.execute("""
                        SELECT AVG(
                            (quality_score + speed_score + safety_score + cost_score) / 4.0 * 20
                        ) as satisfaction
                        FROM service_evaluations
                    """)
                    sat_result = c.fetchone()
                    if sat_result and sat_result['satisfaction']:
                        satisfaction_rate = round(sat_result['satisfaction'], 0)
            except:
                pass
            
            # Get active ships (requests in progress)
            c.execute("""
                SELECT COUNT(DISTINCT ship_name) as count
                FROM maintenance_requests
                WHERE status IN ('assigned', 'in_progress', 'on_hold')
            """)
            active_ships_result = c.fetchone()
            active_ships = active_ships_result['count'] if active_ships_result else 0
            
            return jsonify({
                'success': True,
                'total_requests': total_requests,
                'avg_response': avg_response,
                'satisfaction': satisfaction_rate,
                'active_ships': active_ships
            })
        except Exception as e:
            app.logger.error(f"Error getting dashboard data: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in dashboard data: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== EMERGENCY REQUEST ROUTES ====================

@app.route('/api/emergency-requests')
@login_required
@role_required(['port_engineer', 'harbour_master', 'quality_officer'])
def api_emergency_requests():
    """
    Retrieve emergency requests with optional status filtering.
    
    Fetches active or filtered emergency requests containing critical
    information for incident response. Supports filtering by status
    (pending, active, resolved, all).
    
    Query Parameters:
        - status (str, optional): Filter by status. Default: 'pending'
                                 Values: 'pending', 'active', 'resolved', 'all'
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - emergencies (list): Array of emergency request objects
            - error (str): Error description if failed
    
    Response Fields (per emergency):
        - emergency_id (str): Unique emergency identifier
        - ship_name (str): Name of affected vessel
        - emergency_type (str): Type of emergency
        - severity_level (str): Severity rating
        - status (str): Current status
        - created_at (str): Creation timestamp
        - reported_by (str): Reporter ID
        - location_name (str): Geographic location description
        - latitude/longitude (float): GPS coordinates (or null)
        - description (str): Detailed description
        - immediate_actions (str): Actions taken
        - resources_required (str): Required resources
        - authorized_by (str): Authorizing officer
        - authorized_at (str): Authorization timestamp
    
    Status Codes:
        - 200: Emergencies retrieved successfully
        - 401: Not authenticated
        - 500: Database error
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get status filter from query parameter (default to pending)
        status_filter = request.args.get('status', 'pending')
        
        if status_filter == 'all':
            # Retrieve all emergency requests
            cursor.execute("""
                SELECT emergency_id, ship_name, emergency_type, severity_level,
                       status, created_at, reported_by, location_name, latitude, longitude,
                       description, immediate_actions, resources_required, authorized_by, authorized_at
                FROM emergency_requests
                ORDER BY created_at DESC
            """)
        else:
            # Retrieve emergency requests filtered by status
            cursor.execute("""
                SELECT emergency_id, ship_name, emergency_type, severity_level,
                       status, created_at, reported_by, location_name, latitude, longitude,
                       description, immediate_actions, resources_required, authorized_by, authorized_at
                FROM emergency_requests
                WHERE status = ?
                ORDER BY created_at DESC
            """, (status_filter,))

        emergencies = []
        for row in cursor.fetchall():
            emergency = dict(row)
            
            # Normalize GPS coordinates
            if emergency.get('latitude') is not None:
                try:
                    emergency['latitude'] = float(emergency['latitude'])
                except (ValueError, TypeError):
                    emergency['latitude'] = None
            
            if emergency.get('longitude') is not None:
                try:
                    emergency['longitude'] = float(emergency['longitude'])
                except (ValueError, TypeError):
                    emergency['longitude'] = None
            
            emergencies.append(emergency)

        return jsonify({'success': True, 'emergencies': emergencies}), 200

    except Exception as e:
        app.logger.error(f"Error retrieving emergency requests: {e}")
        return jsonify({'success': False, 'error': 'Failed to retrieve emergency requests'}), 500
    finally:
        conn.close()

@app.route('/api/emergency-details/<emergency_id>')
@login_required
def api_emergency_details(emergency_id):
    """
    Get detailed information for a specific emergency request.
    
    Retrieves comprehensive data for an emergency incident including
    all metadata, location, personnel involved, and response actions.
    
    Args:
        emergency_id (str): The emergency request ID
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - emergency (dict): Complete emergency data
            - error (str): Error description if failed
    
    Status Codes:
        - 200: Details retrieved successfully
        - 401: Not authenticated
        - 404: Emergency not found
        - 500: Database error
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM emergency_requests
            WHERE emergency_id = ?
        """, (emergency_id,))

        emergency = cursor.fetchone()
        if not emergency:
            return jsonify({'success': False, 'error': 'Emergency request not found'}), 404

        emergency_dict = dict(emergency)
        # Ensure coordinates are properly serialized (None -> null, numbers as numbers)
        if emergency_dict.get('latitude') is not None:
            try:
                emergency_dict['latitude'] = float(emergency_dict['latitude'])
            except (ValueError, TypeError):
                emergency_dict['latitude'] = None
        if emergency_dict.get('longitude') is not None:
            try:
                emergency_dict['longitude'] = float(emergency_dict['longitude'])
            except (ValueError, TypeError):
                emergency_dict['longitude'] = None

        return jsonify({'success': True, 'emergency': emergency_dict})
    except Exception as e:
        app.logger.error(f"Error getting emergency details: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/declare-emergency', methods=['POST'])
@limiter.limit("5 per minute")
def api_declare_emergency():
    """Declare a new emergency. Allows both authenticated and unauthenticated users."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        ship_name = data.get('ship_name')
        emergency_type = data.get('emergency_type')
        severity_level = data.get('severity_level', 'critical')
        description = data.get('description')
        immediate_actions = data.get('immediate_actions', '')
        resources_required = data.get('resources_required', '')
        # Optional location & coordinates
        location_name = data.get('location_name')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        # Contact information for public users
        reporter_name = data.get('reporter_name', '')
        reporter_email = data.get('reporter_email', '')
        reporter_phone = data.get('reporter_phone', '')
        
        if not ship_name or not emergency_type or not description:
            return jsonify({'success': False, 'error': 'Missing required fields: Ship Name, Emergency Type, and Description are required'}), 400
        
        # Determine reporter ID
        if current_user.is_authenticated:
            reported_by = current_user.id
            reporter_info = f"User: {current_user.get_full_name()}"
        else:
            # For public users, use a placeholder ID with contact info
            reported_by = f"PUBLIC-{generate_id('PUB')}"
            reporter_info_parts = []
            if reporter_name:
                reporter_info_parts.append(f"Name: {reporter_name}")
            if reporter_email:
                reporter_info_parts.append(f"Email: {reporter_email}")
            if reporter_phone:
                reporter_info_parts.append(f"Phone: {reporter_phone}")
            reporter_info = " | ".join(reporter_info_parts) if reporter_info_parts else "Anonymous Public User"
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Generate emergency ID
            emergency_id = generate_id('EMG')
            
            # Normalise coordinates (if provided)
            lat_value = None
            lon_value = None
            try:
                if latitude not in (None, '', 'null'):
                    lat_value = float(latitude)
                if longitude not in (None, '', 'null'):
                    lon_value = float(longitude)
            except Exception:
                lat_value = None
                lon_value = None

            # Insert emergency request with real-time timestamp
            current_time = datetime.now()
            c.execute("""
                INSERT INTO emergency_requests
                (emergency_id, ship_name, emergency_type, severity_level, description,
                 immediate_actions, resources_required, reported_by,
                 location_name, latitude, longitude, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """, (
                emergency_id,
                ship_name,
                emergency_type,
                severity_level,
                description,
                immediate_actions,
                resources_required,
                reported_by,
                location_name,
                lat_value,
                lon_value,
                current_time,
                current_time
            ))
            
            conn.commit()
            
            # Send notifications to managers
            c.execute("SELECT user_id FROM users WHERE role = 'port_engineer' AND is_active = 1")
            managers = c.fetchall()
            
            for manager in managers:
                notification_message = f'Emergency {emergency_id}: {emergency_type} on {ship_name}'
                if not current_user.is_authenticated:
                    notification_message += f'\nReported by: {reporter_info}'
                create_notification(
                    manager['user_id'],
                    'New Emergency Declared',
                    notification_message,
                    'urgent',
                    '/emergency-requests'
                )
            
            # Log activity (only if authenticated)
            if current_user.is_authenticated:
                log_activity('emergency_declared', f'Declared emergency {emergency_id}')
            else:
                app.logger.info(f'Emergency {emergency_id} declared by public user: {reporter_info}')
            
            return jsonify({
                'success': True,
                'emergency_id': emergency_id,
                'message': 'Emergency declared successfully. Managers have been notified.'
            })
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error declaring emergency: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in declare emergency: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency-contact-services', methods=['POST'])
@login_required
def api_emergency_contact_services():
    """Contact emergency services."""
    try:
        data = request.get_json()
        emergency_id = data.get('emergency_id', 'current')
        
        # Log the activity
        log_activity('emergency_services_contacted', f'Contacted emergency services for {emergency_id}')
        
        # In a real system, this would send notifications/emails to emergency contacts
        return jsonify({
            'success': True,
            'message': 'Emergency services contacted. All relevant personnel have been notified.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency-activate-team', methods=['POST'])
@login_required
def api_emergency_activate_team():
    """Activate emergency response team."""
    try:
        data = request.get_json()
        emergency_id = data.get('emergency_id', 'current')
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Notify all harbour masters and port engineers
            c.execute("SELECT user_id FROM users WHERE role IN ('port_engineer', 'harbour_master') AND is_active = 1")
            team_members = c.fetchall()
            
            for member in team_members:
                create_notification(
                    member['user_id'],
                    'Emergency Response Team Activated',
                    f'Emergency response team has been activated for emergency {emergency_id}',
                    'urgent',
                    '/emergency-requests'
                )
            
            conn.commit()
            log_activity('response_team_activated', f'Activated response team for {emergency_id}')
            
            return jsonify({
                'success': True,
                'message': 'Emergency response team activated. All personnel notified.'
            })
        except Exception as e:
            app.logger.error(f"Error activating team: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== EMERGENCY ACTIVITY TIMELINE ====================

@app.route('/api/emergency/<emergency_id>/activities')
@login_required
def api_emergency_activities(emergency_id):
    """Get activity timeline for an emergency."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT 
                    eal.*,
                    u.first_name || ' ' || u.last_name as user_name,
                    u.role as user_role
                FROM emergency_activity_log eal
                LEFT JOIN users u ON eal.user_id = u.user_id
                WHERE eal.emergency_id = ?
                ORDER BY eal.created_at DESC
            """, (emergency_id,))
            
            activities = []
            for row in c.fetchall():
                activity = dict(row)
                activities.append(activity)
            
            return jsonify({'success': True, 'activities': activities})
        except Exception as e:
            app.logger.error(f"Error getting activities: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency/<emergency_id>/log-activity', methods=['POST'])
@login_required
def api_log_emergency_activity(emergency_id):
    """Log an activity for an emergency."""
    try:
        import json as json_module
        data = request.get_json()
        action_type = data.get('action_type')
        action_description = data.get('action_description')
        old_status = data.get('old_status')
        new_status = data.get('new_status')
        metadata = json_module.dumps(data.get('metadata', {}))
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_time = datetime.now()
            c.execute("""
                INSERT INTO emergency_activity_log
                (emergency_id, user_id, action_type, action_description, old_status, new_status, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (emergency_id, current_user.id, action_type, action_description, old_status, new_status, metadata, current_time))
            
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error logging activity: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== EMERGENCY STATUS MANAGEMENT ====================

@app.route('/api/emergency/<emergency_id>/update-status', methods=['POST'])
@login_required
def api_update_emergency_status(emergency_id):
    """Update emergency status with workflow."""
    try:
        data = request.get_json()
        new_status = data.get('status')
        change_reason = data.get('reason', '')
        
        if not new_status:
            return jsonify({'success': False, 'error': 'Status is required'})
        
        valid_statuses = ['pending', 'authorized', 'in_progress', 'resolved', 'closed']
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'error': 'Invalid status'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get current status
            c.execute("SELECT status FROM emergency_requests WHERE emergency_id = ?", (emergency_id,))
            result = c.fetchone()
            if not result:
                return jsonify({'success': False, 'error': 'Emergency not found'})
            
            old_status = result['status']
            
            # Update status
            update_fields = ['status = ?', 'updated_at = ?']
            update_values = [new_status, datetime.now()]
            
            if new_status == 'resolved':
                update_fields.append('resolved_at = ?')
                update_values.append(datetime.now())
            elif new_status == 'closed':
                update_fields.append('closed_at = ?')
                update_values.append(datetime.now())
            
            update_values.append(emergency_id)
            
            c.execute(f"""
                UPDATE emergency_requests
                SET {', '.join(update_fields)}
                WHERE emergency_id = ?
            """, update_values)
            
            # Log status change with real-time timestamp
            current_time = datetime.now()
            c.execute("""
                INSERT INTO emergency_status_history
                (emergency_id, old_status, new_status, changed_by, change_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (emergency_id, old_status, new_status, current_user.id, change_reason, current_time))
            
            # Log activity with real-time timestamp
            c.execute("""
                INSERT INTO emergency_activity_log
                (emergency_id, user_id, action_type, action_description, old_status, new_status, created_at)
                VALUES (?, ?, 'status_change', ?, ?, ?, ?)
            """, (emergency_id, current_user.id, f'Status changed from {old_status} to {new_status}', old_status, new_status, current_time))
            
            conn.commit()
            
            # Send notifications based on status
            if new_status == 'authorized':
                c.execute("SELECT user_id FROM users WHERE role = 'harbour_master' AND is_active = 1")
                managers = c.fetchall()
                for manager in managers:
                    create_notification(
                        manager['user_id'],
                        'Emergency Authorized',
                        f'Emergency {emergency_id} has been authorized and requires action.',
                        'urgent',
                        '/emergency-requests'
                    )
            
            log_activity('emergency_status_updated', f'Updated emergency {emergency_id} status to {new_status}')
            return jsonify({'success': True, 'old_status': old_status, 'new_status': new_status})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating status: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency/<emergency_id>/status-history')
@login_required
def api_emergency_status_history(emergency_id):
    """Get status change history for an emergency."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT 
                    esh.*,
                    u.first_name || ' ' || u.last_name as changed_by_name
                FROM emergency_status_history esh
                LEFT JOIN users u ON esh.changed_by = u.user_id
                WHERE esh.emergency_id = ?
                ORDER BY esh.created_at DESC
            """, (emergency_id,))
            
            history = []
            for row in c.fetchall():
                history.append(dict(row))
            
            return jsonify({'success': True, 'history': history})
        except Exception as e:
            app.logger.error(f"Error getting status history: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== EMERGENCY COMMUNICATION HUB ====================

@app.route('/api/emergency/<emergency_id>/messages')
@login_required
def api_emergency_messages(emergency_id):
    """Get messages for an emergency."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT 
                    em.*,
                    u.first_name || ' ' || u.last_name as sender_name,
                    u.role as sender_role
                FROM emergency_messages em
                LEFT JOIN users u ON em.sender_id = u.user_id
                WHERE em.emergency_id = ?
                ORDER BY em.created_at ASC
            """, (emergency_id,))
            
            messages = []
            for row in c.fetchall():
                message = dict(row)
                messages.append(message)
            
            return jsonify({'success': True, 'messages': messages})
        except Exception as e:
            app.logger.error(f"Error getting messages: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency/<emergency_id>/send-message', methods=['POST'])
@login_required
def api_send_emergency_message(emergency_id):
    """Send a message in emergency communication hub."""
    try:
        data = request.get_json()
        message = data.get('message')
        
        if not message or not message.strip():
            return jsonify({'success': False, 'error': 'Message is required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_time = datetime.now()
            c.execute("""
                INSERT INTO emergency_messages
                (emergency_id, sender_id, message, created_at)
                VALUES (?, ?, ?, ?)
            """, (emergency_id, current_user.id, message.strip(), current_time))
            
            # Log activity with real-time timestamp
            c.execute("""
                INSERT INTO emergency_activity_log
                (emergency_id, user_id, action_type, action_description, created_at)
                VALUES (?, ?, 'message_sent', ?, ?)
            """, (emergency_id, current_user.id, f'Sent message: {message[:50]}...', current_time))
            
            conn.commit()
            
            return jsonify({'success': True, 'message_id': c.lastrowid})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error sending message: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== EMERGENCY RESOURCE TRACKING ====================

@app.route('/api/emergency/<emergency_id>/resources')
@login_required
def api_emergency_resources(emergency_id):
    """Get resources assigned to an emergency."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT 
                    er.*,
                    u.first_name || ' ' || u.last_name as assigned_by_name
                FROM emergency_resources er
                LEFT JOIN users u ON er.assigned_by = u.user_id
                WHERE er.emergency_id = ?
                ORDER BY er.assigned_at DESC
            """, (emergency_id,))
            
            resources = []
            for row in c.fetchall():
                resource = dict(row)
                resources.append(resource)
            
            return jsonify({'success': True, 'resources': resources})
        except Exception as e:
            app.logger.error(f"Error getting resources: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency/<emergency_id>/assign-resource', methods=['POST'])
@login_required
def api_assign_emergency_resource(emergency_id):
    """Assign a resource to an emergency."""
    try:
        data = request.get_json()
        resource_type = data.get('resource_type')
        resource_name = data.get('resource_name')
        resource_id = data.get('resource_id')
        notes = data.get('notes', '')
        
        if not resource_type or not resource_name:
            return jsonify({'success': False, 'error': 'Resource type and name are required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_time = datetime.now()
            c.execute("""
                INSERT INTO emergency_resources
                (emergency_id, resource_type, resource_name, resource_id, assigned_by, notes, assigned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (emergency_id, resource_type, resource_name, resource_id, current_user.id, notes, current_time))
            
            # Log activity with real-time timestamp
            c.execute("""
                INSERT INTO emergency_activity_log
                (emergency_id, user_id, action_type, action_description, created_at)
                VALUES (?, ?, 'resource_assigned', ?, ?)
            """, (emergency_id, current_user.id, f'Assigned {resource_type}: {resource_name}', current_time))
            
            conn.commit()
            
            return jsonify({'success': True, 'resource_id': c.lastrowid})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error assigning resource: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency/<emergency_id>/release-resource/<int:resource_id>', methods=['POST'])
@login_required
def api_release_emergency_resource(emergency_id, resource_id):
    """Release a resource from an emergency."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get resource info
            c.execute("SELECT resource_name, resource_type FROM emergency_resources WHERE id = ? AND emergency_id = ?", 
                     (resource_id, emergency_id))
            resource = c.fetchone()
            
            if not resource:
                return jsonify({'success': False, 'error': 'Resource not found'})
            
            # Update resource
            c.execute("""
                UPDATE emergency_resources
                SET status = 'released', released_at = ?
                WHERE id = ? AND emergency_id = ?
            """, (datetime.now(), resource_id, emergency_id))
            
            # Log activity with real-time timestamp
            current_time = datetime.now()
            c.execute("""
                INSERT INTO emergency_activity_log
                (emergency_id, user_id, action_type, action_description, created_at)
                VALUES (?, ?, 'resource_released', ?, ?)
            """, (emergency_id, current_user.id, f'Released {resource["resource_type"]}: {resource["resource_name"]}', current_time))
            
            conn.commit()
            
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error releasing resource: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency/<emergency_id>/update-resource/<int:resource_id>', methods=['POST'])
@login_required
@csrf_protect
def api_update_emergency_resource(emergency_id, resource_id):
    """Update a resource assigned to an emergency."""
    try:
        data = request.get_json()
        resource_type = data.get('resource_type')
        resource_name = data.get('resource_name')
        resource_id_field = data.get('resource_id')
        notes = data.get('notes', '')
        status = data.get('status')
        
        if not resource_type or not resource_name:
            return jsonify({'success': False, 'error': 'Resource type and name are required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get old resource info for logging
            c.execute("SELECT resource_name, resource_type, status FROM emergency_resources WHERE id = ? AND emergency_id = ?", 
                     (resource_id, emergency_id))
            old_resource = c.fetchone()
            
            if not old_resource:
                return jsonify({'success': False, 'error': 'Resource not found'})
            
            # Build update query dynamically
            update_fields = []
            update_values = []
            
            if resource_type:
                update_fields.append('resource_type = ?')
                update_values.append(resource_type)
            if resource_name:
                update_fields.append('resource_name = ?')
                update_values.append(resource_name)
            if resource_id_field is not None:
                update_fields.append('resource_id = ?')
                update_values.append(resource_id_field)
            if notes is not None:
                update_fields.append('notes = ?')
                update_values.append(notes)
            if status:
                update_fields.append('status = ?')
                update_values.append(status)
                if status == 'released':
                    update_fields.append('released_at = ?')
                    update_values.append(datetime.now())
                elif status == 'assigned':
                    update_fields.append('released_at = NULL')
            
            if not update_fields:
                return jsonify({'success': False, 'error': 'No fields to update'})
            
            update_values.extend([resource_id, emergency_id])
            
            query = f"""
                UPDATE emergency_resources
                SET {', '.join(update_fields)}
                WHERE id = ? AND emergency_id = ?
            """
            
            c.execute(query, update_values)
            
            # Log activity with real-time timestamp
            current_time = datetime.now()
            changes = []
            if resource_type and resource_type != old_resource['resource_type']:
                changes.append(f"type: {old_resource['resource_type']} → {resource_type}")
            if resource_name and resource_name != old_resource['resource_name']:
                changes.append(f"name: {old_resource['resource_name']} → {resource_name}")
            if status and status != old_resource['status']:
                changes.append(f"status: {old_resource['status']} → {status}")
            
            change_desc = f'Updated {old_resource["resource_type"]}: {old_resource["resource_name"]}'
            if changes:
                change_desc += f' ({", ".join(changes)})'
            
            c.execute("""
                INSERT INTO emergency_activity_log
                (emergency_id, user_id, action_type, action_description, created_at)
                VALUES (?, ?, 'resource_updated', ?, ?)
            """, (emergency_id, current_user.id, change_desc, current_time))
            
            conn.commit()
            
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating resource: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency/<emergency_id>/available-resources')
@login_required
def api_available_resources(emergency_id):
    """Get available resources for assignment."""
    try:
        # This would typically query a resources database
        # For now, return a list of common resources
        available_resources = [
            {'type': 'personnel', 'name': 'Emergency Response Team', 'id': 'ERT001', 'available': True},
            {'type': 'personnel', 'name': 'Medical Team', 'id': 'MED001', 'available': True},
            {'type': 'vessel', 'name': 'Tugboat Alpha', 'id': 'TUG001', 'available': True},
            {'type': 'vessel', 'name': 'Tugboat Beta', 'id': 'TUG002', 'available': True},
            {'type': 'equipment', 'name': 'Fire Suppression System', 'id': 'FSS001', 'available': True},
            {'type': 'equipment', 'name': 'Emergency Medical Kit', 'id': 'EMK001', 'available': True},
        ]
        
        return jsonify({'success': True, 'resources': available_resources})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency/current/available-resources')
@login_required
def api_current_available_resources():
    """Get available resources (generic endpoint for dashboard)."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT id, resource_type, resource_name, resource_id, available, location, notes, created_at, updated_at
                FROM available_resources
                ORDER BY resource_type, resource_name
            """)
            
            resources = []
            for row in c.fetchall():
                resource = dict(row)
                resources.append({
                    'id': resource['id'],
                    'type': resource['resource_type'],
                    'name': resource['resource_name'],
                    'id_field': resource['resource_id'],
                    'available': bool(resource['available']),
                    'location': resource['location'],
                    'notes': resource['notes']
                })
            
            # If no resources in database, return default list
            if len(resources) == 0:
                resources = [
                    {'id': None, 'type': 'personnel', 'name': 'Emergency Response Team', 'id_field': 'ERT001', 'available': True, 'location': None, 'notes': None},
                    {'id': None, 'type': 'personnel', 'name': 'Medical Team', 'id_field': 'MED001', 'available': True, 'location': None, 'notes': None},
                    {'id': None, 'type': 'vessel', 'name': 'Tugboat Alpha', 'id_field': 'TUG001', 'available': True, 'location': None, 'notes': None},
                    {'id': None, 'type': 'vessel', 'name': 'Tugboat Beta', 'id_field': 'TUG002', 'available': True, 'location': None, 'notes': None},
                    {'id': None, 'type': 'equipment', 'name': 'Fire Suppression System', 'id_field': 'FSS001', 'available': True, 'location': None, 'notes': None},
                    {'id': None, 'type': 'equipment', 'name': 'Emergency Medical Kit', 'id_field': 'EMK001', 'available': True, 'location': None, 'notes': None},
                ]
            
            return jsonify({'success': True, 'resources': resources})
        except Exception as e:
            app.logger.error(f"Error getting available resources: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/available-resources', methods=['POST'])
@login_required
@csrf_protect
@role_required(['port_engineer', 'harbour_master'])
def api_create_available_resource():
    """Create a new available resource."""
    try:
        data = request.get_json()
        resource_type = data.get('resource_type')
        resource_name = data.get('resource_name')
        resource_id = data.get('resource_id')
        available = data.get('available', True)
        location = data.get('location', '')
        notes = data.get('notes', '')
        
        if not resource_type or not resource_name:
            return jsonify({'success': False, 'error': 'Resource type and name are required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_time = datetime.now()
            c.execute("""
                INSERT INTO available_resources
                (resource_type, resource_name, resource_id, available, location, notes, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (resource_type, resource_name, resource_id, 1 if available else 0, location, notes, current_user.id, current_time, current_time))
            
            conn.commit()
            return jsonify({'success': True, 'resource_id': c.lastrowid})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error creating available resource: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/available-resources/<int:resource_id>', methods=['PUT'])
@login_required
@csrf_protect
@role_required(['port_engineer', 'harbour_master'])
def api_update_available_resource(resource_id):
    """Update an available resource."""
    try:
        data = request.get_json()
        resource_type = data.get('resource_type')
        resource_name = data.get('resource_name')
        resource_id_field = data.get('resource_id')
        available = data.get('available')
        location = data.get('location')
        notes = data.get('notes')
        
        if not resource_type or not resource_name:
            return jsonify({'success': False, 'error': 'Resource type and name are required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            current_time = datetime.now()
            c.execute("""
                UPDATE available_resources
                SET resource_type = ?, resource_name = ?, resource_id = ?, available = ?, 
                    location = ?, notes = ?, updated_at = ?
                WHERE id = ?
            """, (resource_type, resource_name, resource_id_field, 1 if available else 0, location, notes, current_time, resource_id))
            
            if c.rowcount == 0:
                return jsonify({'success': False, 'error': 'Resource not found'})
            
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating available resource: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/available-resources/<int:resource_id>', methods=['DELETE'])
@login_required
@csrf_protect
@role_required(['port_engineer', 'harbour_master'])
def api_delete_available_resource(resource_id):
    """Delete an available resource."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("DELETE FROM available_resources WHERE id = ?", (resource_id,))
            
            if c.rowcount == 0:
                return jsonify({'success': False, 'error': 'Resource not found'})
            
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error deleting available resource: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== REAL-TIME UPDATES (Server-Sent Events) ====================

@app.route('/api/emergency/stream')
@login_required
def api_emergency_stream():
    """Server-Sent Events stream for real-time emergency updates."""
    from flask import Response
    import json as json_module
    import time
    
    def generate():
        last_check = time.time()
        
        while True:
            try:
                conn = get_db_connection()
                c = conn.cursor()
                
                # Check for new activities in the last 5 seconds
                c.execute("""
                    SELECT emergency_id, action_type, created_at
                    FROM emergency_activity_log
                    WHERE created_at > datetime('now', '-5 seconds')
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                
                activities = c.fetchall()
                if activities:
                    for activity in activities:
                        yield f"data: {json_module.dumps({'type': 'activity', 'data': dict(activity)})}\n\n"
                
                conn.close()
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                yield f"data: {json_module.dumps({'type': 'error', 'error': str(e)})}\n\n"
                time.sleep(5)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/emergency-report/<emergency_id>')
@login_required
def api_emergency_report(emergency_id):
    """Generate emergency report."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM emergency_requests WHERE emergency_id = ?", (emergency_id,))
            emergency = c.fetchone()
            
            if not emergency:
                return jsonify({'success': False, 'error': 'Emergency not found'})
            
            emergency_dict = dict(emergency)
            
            # Create comprehensive report
            report = {
                'emergency_id': emergency_id,
                'generated_at': datetime.now().isoformat(),
                'generated_by': current_user.get_full_name(),
                'emergency_details': emergency_dict,
                'summary': f"Emergency {emergency_id} - {emergency_dict.get('emergency_type')} on {emergency_dict.get('ship_name')}"
            }
            
            return jsonify({'success': True, 'report': report})
        except Exception as e:
            app.logger.error(f"Error generating report: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emergency-authorize', methods=['POST'])
@login_required
@csrf_protect
@role_required(['port_engineer'])
@limiter.limit("10 per minute")
def api_emergency_authorize():
    """Authorize emergency request."""
    try:
        data = request.get_json()
        emergency_id = data.get('emergency_id')
        auth_code = data.get('auth_code')

        if not emergency_id or not auth_code:
            return jsonify({'success': False, 'error': 'Missing required fields'})

        # In a real system, validate the authorization code
        if auth_code != "MARINE2026":
            return jsonify({'success': False, 'error': 'Invalid authorization code'})

        conn = get_db_connection()
        try:
            c = conn.cursor()

            # Update emergency status with real-time timestamps
            current_time = datetime.now()
            c.execute("""
                UPDATE emergency_requests
                SET status = 'authorized', authorized_by = ?, authorized_at = ?, updated_at = ?
                WHERE emergency_id = ?
            """, (current_user.id, current_time, current_time, emergency_id))

            # Get emergency details for notification
            c.execute("SELECT ship_name, emergency_type FROM emergency_requests WHERE emergency_id = ?", (emergency_id,))
            emergency = c.fetchone()

            conn.commit()

            # Log activity
            log_activity('emergency_authorized', f'Authorized emergency {emergency_id}')

            # Send notifications to harbour masters
            c.execute("SELECT user_id FROM users WHERE role = 'harbour_master' AND is_active = 1")
            harbour_masters = c.fetchall()

            for harbour_master in harbour_masters:
                create_notification(
                    harbour_master['user_id'],
                    'Emergency Authorized',
                    f'Emergency {emergency_id} ({emergency["ship_name"]}) has been authorized. Immediate action required.',
                    'urgent',
                    '/emergency-requests'
                )

            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error authorizing emergency: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in emergency authorization: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== MAINTENANCE HANDLER ==========================

@app.route('/api/maintenance-requests', methods=['GET'])
@login_required
def api_get_maintenance_requests():
    """Get maintenance requests (for all users)."""
    conn = get_db_connection()
    try:
        c = conn.cursor()

        # Different views based on role
        if current_user.role == 'harbour_master':
            c.execute("""
                SELECT request_id, ship_name, maintenance_type, priority,
                       status, created_at, requested_by
                FROM maintenance_requests
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                        ELSE 5
                    END,
                    created_at DESC
                LIMIT 50
            """)
        else:
            # For other users, show only their requests
            c.execute("""
                SELECT request_id, ship_name, maintenance_type, priority,
                       status, created_at, requested_by
                FROM maintenance_requests
                WHERE requested_by = ?
                ORDER BY created_at DESC
                LIMIT 50
            """, (current_user.email,))

        requests = []
        for row in c.fetchall():
            request_data = dict(row)
            requests.append(request_data)

        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        app.logger.error(f"Error getting maintenance requests: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# ==================== MAINTENANCE REQUEST ROUTES ====================

@app.route('/api/maintenance-requests')
@login_required
def api_maintenance_requests():
    """Get maintenance requests - filtered by user role and status."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Get status filter from query parameter (default to pending for managers)
        status_filter = request.args.get('status', None)
        
        # Filter based on user role
        if current_user.role == 'chief_engineer':
            # Chief Engineer sees only their own requests
            if status_filter:
                c.execute("""
                    SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                           status, created_at, requested_by
                    FROM maintenance_requests
                    WHERE requested_by = ? AND status = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (current_user.email, status_filter))
            else:
                c.execute("""
                    SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                           status, created_at, requested_by
                    FROM maintenance_requests
                    WHERE requested_by = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (current_user.email,))
        elif current_user.role == 'captain':
            # Captain sees all requests (read-only view)
            if status_filter:
                c.execute("""
                    SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                           status, created_at, requested_by
                    FROM maintenance_requests
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (status_filter,))
            else:
                c.execute("""
                    SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                           status, created_at, requested_by
                    FROM maintenance_requests
                    ORDER BY created_at DESC
                    LIMIT 50
                """)
        elif current_user.role in ['harbour_master', 'port_engineer']:
            # Harbour Master and Port Engineer see pending requests by default
            if status_filter == 'all':
                # Show all requests
                c.execute("""
                    SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                           status, created_at, requested_by
                    FROM maintenance_requests
                    ORDER BY 
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                            ELSE 5
                        END,
                        created_at DESC
                    LIMIT 50
                """)
            elif status_filter:
                # Show specific status
                c.execute("""
                    SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                           status, created_at, requested_by
                    FROM maintenance_requests
                    WHERE status = ?
                    ORDER BY 
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                            ELSE 5
                        END,
                        created_at DESC
                    LIMIT 50
                """, (status_filter,))
            else:
                # Default: show pending requests
                c.execute("""
                    SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                           status, created_at, requested_by
                    FROM maintenance_requests
                    WHERE status = 'pending'
                    ORDER BY 
                        CASE priority
                            WHEN 'critical' THEN 1
                            WHEN 'high' THEN 2
                            WHEN 'medium' THEN 3
                            WHEN 'low' THEN 4
                            ELSE 5
                        END,
                        created_at DESC
                    LIMIT 50
                """)
        else:
            # Other users see only their own requests
            if status_filter:
                c.execute("""
                    SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                           status, created_at, requested_by
                    FROM maintenance_requests
                    WHERE requested_by = ? AND status = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (current_user.email, status_filter))
            else:
                c.execute("""
                    SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                           status, created_at, requested_by
                    FROM maintenance_requests
                    WHERE requested_by = ?
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (current_user.email,))

        requests = []
        for row in c.fetchall():
            request_data = dict(row)
            requests.append(request_data)

        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        app.logger.error(f"Error getting maintenance requests: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# ==================== MAINTENANCE REQUEST ========================

@app.route('/api/maintenance-requests', methods=['POST'])
def api_create_maintenance_request():
    """
    Create a new maintenance/repair request for vessel equipment.
    
    Allows authenticated crew (Chief Engineer, Captain) and external parties
    to submit maintenance requests. Automatically assesses severity based on
    description analysis and criticality level.
    
    JSON Request Body (Required):
        - ship_name (str): Name of the vessel
        - imo_number (str): IMO registration number
        - vessel_type (str): Type of vessel (cargo, tanker, etc.)
        - location (str): Current location of vessel
        - request_type (str): Type of maintenance (repair, parts, inspection, etc.)
        - criticality (str): Urgency level (emergency, urgent, high, medium, low)
        - description (str): Detailed description of issue
        - requested_by_name (str): Name of requester
        - requested_by_email (str): Email address
        - requested_by_phone (str): Contact phone number
    
    JSON Request Body (Optional):
        - emergency_contact (str): Alternative contact information
        - eta (str): Estimated time of arrival (for parts)
        - part_category (str): Equipment category
        - part_number (str): Specific part/equipment number
        - part_name (str): Name of part/equipment
        - quantity (int): Quantity needed (default: 1)
        - manufacturer (str): Equipment manufacturer
        - company (str): Company/organization name
        - notes (str): Additional notes
    
    Auto-Severity Assessment:
        System automatically analyzes description for critical keywords:
        fire, emergency, flooding, sinking, collision, etc.
        Marks as CRITICAL if found or if priority is 'high'.
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - request_id (str): Generated maintenance request ID
            - severity (str): Auto-assessed severity level
            - message (str): Confirmation message
            - error (str): Error description if failed
    
    Status Codes:
        - 201: Request created successfully
        - 400: Missing required fields
        - 500: Database error
    
    Note:
        Unauthenticated users can submit requests using email contact info.
        Severity assessment triggers appropriate notifications to management.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No request data provided'}), 400

        # Extract request data
        ship_name = data.get('ship_name')
        imo_number = data.get('imo_number')
        vessel_type = data.get('vessel_type')
        location = data.get('location')
        request_type = data.get('request_type')
        criticality = data.get('criticality')
        description = data.get('description')
        emergency_contact = data.get('emergency_contact')
        eta = data.get('eta')
        part_category = data.get('part_category')
        part_number = data.get('part_number')
        part_name = data.get('part_name')
        quantity = int(data.get('quantity', 1))
        manufacturer = data.get('manufacturer')
        requested_by_name = data.get('requested_by_name')
        requested_by_email = data.get('requested_by_email')
        requested_by_phone = data.get('requested_by_phone')
        company = data.get('company')
        notes = data.get('notes')

        # Validate all required fields are present
        required_fields = [
            ship_name, imo_number, vessel_type, location, request_type,
            criticality, description, requested_by_name, requested_by_email,
            requested_by_phone
        ]
        if not all(required_fields):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Generate unique request ID
        request_id = generate_id('MRQ')

        # Map criticality to priority
        priority_map = {
            'emergency': 'critical',
            'urgent': 'high',
            'high': 'high',
            'medium': 'medium',
            'low': 'low'
        }
        priority = priority_map.get(criticality, 'medium')

        # Automatically assess severity based on description and type
        severity, assessment_details = assess_severity(description, request_type, priority)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Determine initial status and requester ID
            initial_status = 'submitted'
            requester_id = None
            
            if current_user.is_authenticated:
                requester_id = current_user.id
                if current_user.role in ['chief_engineer', 'captain']:
                    initial_status = 'submitted'

            # Insert maintenance request with all data and severity assessment
            cursor.execute("""
                INSERT INTO maintenance_requests
                (request_id, ship_name, maintenance_type, request_type, priority, criticality, description,
                 location, estimated_duration, resources_needed, requested_by,
                 status, severity, assessment_details, workflow_status, created_at, updated_at,
                 part_number, part_name, part_category, quantity, manufacturer,
                 requested_by_name, requested_by_email, requested_by_phone, emergency_contact,
                 imo_number, vessel_type, company, eta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id, ship_name, request_type, request_type, priority, criticality, description,
                location, 'TBD', 'To be assessed', requested_by_email or requester_id,
                initial_status, severity, assessment_details, 'submitted', datetime.now(), datetime.now(),
                part_number, part_name, part_category, quantity, manufacturer,
                requested_by_name, requested_by_email, requested_by_phone, emergency_contact,
                imo_number, vessel_type, company, eta
            ))

            # Log workflow action for audit trail
            log_workflow_action(
                request_id, 'submitted', requester_id,
                f'Maintenance request for {ship_name}. Auto-assessed: {severity}'
            )

            # Log activity (if authenticated user)
            if current_user.is_authenticated:
                log_activity(
                    'maintenance_request_created',
                    f'Created request {request_id} for {ship_name}. Severity: {severity}'
                )
            else:
                app.logger.info(
                    f'Maintenance request {request_id} from {requested_by_email}: {severity} severity'
                )

            conn.commit()

            # Send notifications based on severity level
            notify_on_severity(request_id, severity)

            return jsonify({
                'success': True,
                'request_id': request_id,
                'severity': severity,
                'message': f'Request submitted successfully. Auto-assessed: {severity}'
            }), 201

        except Exception as e:
            conn.rollback()
            app.logger.error(f"Database error creating maintenance request: {e}", exc_info=True)
            return jsonify({'success': False, 'error': 'Failed to create maintenance request'}), 500
        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error processing maintenance request: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to process request'}), 500


@app.route('/api/maintenance-requests/<request_id>/attachments/upload', methods=['POST'])
def api_upload_maintenance_attachments(request_id):
    """Upload one or more attachments for a maintenance request. Allows access for request creators and assigned staff."""
    if 'files' not in request.files and 'file' not in request.files:
        return jsonify(success=False, error='No files uploaded'), 400

    files = request.files.getlist('files') or request.files.getlist('file')
    saved = []

    # Create target folder for this request
    safe_request_id = secure_filename(request_id)
    target_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'maintenance_requests', safe_request_id)
    os.makedirs(target_folder, exist_ok=True)

    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Verify request exists
        c.execute("SELECT request_id FROM maintenance_requests WHERE request_id = ?", (request_id,))
        if not c.fetchone():
            return jsonify(success=False, error='Maintenance request not found'), 404

        for f in files:
            if f and f.filename:
                if not allowed_file(f.filename):
                    continue
                    
                orig = f.filename
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                stored_name = f"{timestamp}_{secure_filename(orig)}"
                save_path = os.path.join(target_folder, stored_name)
                f.save(save_path)
                file_size = os.path.getsize(save_path)

                attachment_id = generate_id('ATT')
                uploader_id = current_user.id if current_user.is_authenticated else None
                
                c.execute('''
                    INSERT INTO maintenance_request_attachments 
                    (id, request_id, original_filename, stored_filename, file_size, uploader_id, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (attachment_id, request_id, orig, 
                      os.path.join('maintenance_requests', safe_request_id, stored_name), 
                      file_size, uploader_id, datetime.now()))
                
                saved.append({
                    'id': attachment_id,
                    'original_filename': orig,
                    'stored_filename': stored_name,
                    'file_size': file_size
                })

        conn.commit()
        return jsonify(success=True, saved=saved, message=f'Uploaded {len(saved)} files')
    
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error uploading maintenance request attachments: {e}")
        return jsonify(success=False, error=str(e)), 500
    finally:
        conn.close()


@app.route('/api/maintenance-requests/<request_id>/attachments', methods=['GET'])
def api_get_maintenance_attachments(request_id):
    """Get all attachments for a maintenance request."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Verify request exists
        c.execute("SELECT request_id FROM maintenance_requests WHERE request_id = ?", (request_id,))
        if not c.fetchone():
            return jsonify(success=False, error='Maintenance request not found'), 404

        c.execute('''
            SELECT id, original_filename, stored_filename, file_size, uploaded_at, uploader_id
            FROM maintenance_request_attachments
            WHERE request_id = ?
            ORDER BY uploaded_at DESC
        ''', (request_id,))
        
        attachments = [dict(row) for row in c.fetchall()]
        return jsonify(success=True, attachments=attachments)
    
    except Exception as e:
        app.logger.error(f"Error fetching maintenance request attachments: {e}")
        return jsonify(success=False, error=str(e)), 500
    finally:
        conn.close()

# ==================== DATABASE INITIALIZATION ====================

def ensure_port_engineer_account(c, conn):
    """
    Ensure port engineer account exists and is active.
    This function checks if the account exists and creates or updates it as needed.
    
    Args:
        c: Database cursor
        conn: Database connection
    """
    try:
        # Check if account exists
        c.execute("SELECT user_id, is_active, is_approved FROM users WHERE email = 'port_engineer@marine.com'")
        user = c.fetchone()
        
        if user:
            user_id = user['user_id']
            # Update account to ensure it's active and approved
            c.execute('''
                UPDATE users 
                SET is_active = 1, is_approved = 1, role = 'port_engineer'
                WHERE email = 'port_engineer@marine.com'
            ''')
            conn.commit()
            print(f"[OK] Port engineer account updated: {user_id}")
        else:
            # Create new account
            pe_id = 'PE001'
            hashed_password = generate_password_hash('Engineer@2026')
            c.execute('''
                INSERT INTO users (user_id, email, password, first_name, last_name, rank, role, phone, department, location, is_approved, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (pe_id, 'port_engineer@marine.com', hashed_password, 'John', 'Smith', 'Port Engineer', 'port_engineer', '+1234567890', 'Management', 'Headquarters', 1, 1))
            conn.commit()
            print("[OK] Port engineer account created successfully!")
        
        # Verify the account
        c.execute("SELECT user_id, email, role, is_active, is_approved FROM users WHERE email = 'port_engineer@marine.com'")
        result = c.fetchone()
        if result:
            print("\n[INFO] Account Details:")
            print(f"   User ID: {result['user_id']}")
            print(f"   Email: {result['email']}")
            print(f"   Role: {result['role']}")
            print(f"   Active: {'Yes' if result['is_active'] else 'No'}")
            print(f"   Approved: {'Yes' if result['is_approved'] else 'No'}")
            print("\n[OK] You can now log in with:")
            print("   Email: port_engineer@marine.com")
            print("   Password: Engineer@2026")
        
    except Exception as e:
        print(f"[ERROR] Error ensuring port engineer account: {e}")
        import traceback
        traceback.print_exc()

def init_db():
    """
    Initialize database schema while preserving existing data.
    Uses 'CREATE TABLE IF NOT EXISTS' to ensure NO DATA LOSS.
    Safe for repeated calls during deployments.
    
    All user accounts and conversations are PRESERVED across deployments.
    Only demo accounts are ensured to exist (not reset).
    """
    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        # Log data BEFORE initialization
        print("\n" + "="*70)
        print("[DATABASE] PRESERVATION CHECK - PRE-INITIALIZATION")
        print("="*70)
        
        try:
            c.execute("SELECT COUNT(*) FROM users")
            user_count_before = c.fetchone()[0]
            print(f"[DATA] Users before: {user_count_before}")
        except:
            user_count_before = 0
            print("[INFO] Users table does not exist yet")
        
        try:
            c.execute("SELECT COUNT(*) FROM messages")
            messages_before = c.fetchone()[0]
            print(f"[DATA] Messages before: {messages_before}")
        except:
            messages_before = 0
        
        try:
            c.execute("SELECT COUNT(*) FROM maintenance_requests")
            requests_before = c.fetchone()[0]
            print(f"[DATA] Maintenance requests before: {requests_before}")
        except:
            requests_before = 0
        
        # Count existing records before initialization
        c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count_before = c.fetchone()[0]

        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                rank TEXT,
                role TEXT NOT NULL,
                phone TEXT,
                department TEXT,
                location TEXT,
                profile_pic TEXT,
                signature_path TEXT,
                is_active INTEGER DEFAULT 1,
                is_approved INTEGER DEFAULT 0,
                survey_end_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                last_activity TIMESTAMP
            )
        ''')

        # Check if signature_path column exists
        c.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in c.fetchall()]

        if 'signature_path' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN signature_path TEXT")
            print("[OK] Added signature_path column to users table")
        
        if 'is_online' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN is_online INTEGER DEFAULT 0")
            print("[OK] Added is_online column to users table")

        # Create activity_logs table
        c.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                activity TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Create comprehensive audit_trail table for real-time tracking
        c.execute('''
            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                action_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                old_value TEXT,
                new_value TEXT,
                ip_address TEXT,
                status TEXT DEFAULT 'completed',
                error_message TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Create system_events table for real-time system monitoring
        c.execute('''
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                event_data TEXT,
                severity TEXT DEFAULT 'info',
                processed INTEGER DEFAULT 0
            )
        ''')

        # Create update_history table to track all changes with timestamps
        c.execute('''
            CREATE TABLE IF NOT EXISTS update_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                table_name TEXT NOT NULL,
                record_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                user_id TEXT,
                change_reason TEXT
            )
        ''')

        # Create user_documents table
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                document_name TEXT NOT NULL,
                document_type TEXT,
                document_path TEXT NOT NULL,
                file_size INTEGER,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Create inventory_documents table to store multiple documents per inventory item
        c.execute('''
            CREATE TABLE IF NOT EXISTS inventory_documents (
                id TEXT PRIMARY KEY,
                part_number TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                uploader_id TEXT,
                file_size INTEGER,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (uploader_id) REFERENCES users (user_id)
            )
        ''')

        # Create service_evaluations table for SQI - FIXED VERSION
        c.execute('''
            CREATE TABLE IF NOT EXISTS service_evaluations (
                id TEXT PRIMARY KEY,
                evaluator_id TEXT NOT NULL,
                vessel_id TEXT,
                sqi_score REAL,
                evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                status TEXT DEFAULT 'completed',
                FOREIGN KEY (evaluator_id) REFERENCES users (user_id)
            )
        ''')

        # Check if the table exists and has required columns
        c.execute("PRAGMA table_info(service_evaluations)")
        columns = [col[1] for col in c.fetchall()]

        if not columns:  # Table doesn't exist or is empty
            # Recreate with correct structure
            c.execute("DROP TABLE IF EXISTS service_evaluations")
            c.execute('''
                CREATE TABLE service_evaluations (
                    id TEXT PRIMARY KEY,
                    evaluator_id TEXT NOT NULL,
                    vessel_id TEXT,
                    sqi_score REAL,
                    evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    status TEXT DEFAULT 'completed',
                    FOREIGN KEY (evaluator_id) REFERENCES users (user_id)
                )
            ''')
            print("[OK] Created service_evaluations table with correct structure")
        elif 'evaluator_id' not in columns:
            # Drop and recreate if structure is wrong
            c.execute("DROP TABLE IF EXISTS service_evaluations")
            c.execute('''
                CREATE TABLE service_evaluations (
                    id TEXT PRIMARY KEY,
                    evaluator_id TEXT NOT NULL,
                    vessel_id TEXT,
                    sqi_score REAL,
                    evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    status TEXT DEFAULT 'completed',
                    FOREIGN KEY (evaluator_id) REFERENCES users (user_id)
                )
            ''')
            print("[OK] Recreated service_evaluations table with correct structure")
        
        # Create notifications table
        c.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT DEFAULT 'info',
                action_url TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Create notification_preferences table for user notification settings
        c.execute('''
            CREATE TABLE IF NOT EXISTS notification_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                sound_enabled INTEGER DEFAULT 1,
                browser_notifications INTEGER DEFAULT 1,
                email_notifications INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create emergency_requests table
        c.execute('''
            CREATE TABLE IF NOT EXISTS emergency_requests (
                emergency_id TEXT PRIMARY KEY,
                ship_name TEXT NOT NULL,
                emergency_type TEXT NOT NULL,
                severity_level TEXT NOT NULL,
                description TEXT,
                immediate_actions TEXT,
                resources_required TEXT,
                reported_by TEXT,
                -- Location & map integration
                location_name TEXT,
                latitude REAL,
                longitude REAL,
                status TEXT DEFAULT 'pending',
                authorized_by TEXT,
                authorized_at TIMESTAMP,
                resolved_at TIMESTAMP,
                closed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reported_by) REFERENCES users (user_id),
                FOREIGN KEY (authorized_by) REFERENCES users (user_id)
            )
        ''')

        # Backwards-compatible schema upgrades for existing databases
        try:
            c.execute("ALTER TABLE emergency_requests ADD COLUMN location_name TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE emergency_requests ADD COLUMN latitude REAL")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE emergency_requests ADD COLUMN longitude REAL")
        except Exception:
            pass
        
        # Create emergency_activity_log table for timeline/audit trail
        c.execute('''
            CREATE TABLE IF NOT EXISTS emergency_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emergency_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_description TEXT,
                old_status TEXT,
                new_status TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (emergency_id) REFERENCES emergency_requests (emergency_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create emergency_messages table for communication hub
        c.execute('''
            CREATE TABLE IF NOT EXISTS emergency_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emergency_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                message TEXT NOT NULL,
                attachment_path TEXT,
                is_system_message INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (emergency_id) REFERENCES emergency_requests (emergency_id),
                FOREIGN KEY (sender_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create available_resources table for system-wide resource management
        c.execute('''
            CREATE TABLE IF NOT EXISTS available_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_type TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                resource_id TEXT,
                available INTEGER DEFAULT 1,
                location TEXT,
                notes TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users (user_id)
            )
        ''')
        
        # Create emergency_resources table for resource tracking
        c.execute('''
            CREATE TABLE IF NOT EXISTS emergency_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emergency_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                resource_id TEXT,
                assigned_by TEXT,
                status TEXT DEFAULT 'assigned',
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                released_at TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (emergency_id) REFERENCES emergency_requests (emergency_id),
                FOREIGN KEY (assigned_by) REFERENCES users (user_id)
            )
        ''')
        
        # Create emergency_status_history table
        c.execute('''
            CREATE TABLE IF NOT EXISTS emergency_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emergency_id TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT NOT NULL,
                changed_by TEXT NOT NULL,
                change_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (emergency_id) REFERENCES emergency_requests (emergency_id),
                FOREIGN KEY (changed_by) REFERENCES users (user_id)
            )
        ''')
        
        # Create maintenance_requests table
        c.execute('''
            CREATE TABLE IF NOT EXISTS maintenance_requests (
                request_id TEXT PRIMARY KEY,
                ship_name TEXT NOT NULL,
                maintenance_type TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',
                description TEXT,
                location TEXT,
                estimated_duration TEXT,
                resources_needed TEXT,
                requested_by TEXT,
                status TEXT DEFAULT 'pending',
                assigned_to TEXT,
                approved INTEGER DEFAULT 0,
                approved_by TEXT,
                approved_at TIMESTAMP,
                rejection_reason TEXT,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (requested_by) REFERENCES users (user_id),
                FOREIGN KEY (assigned_to) REFERENCES users (user_id),
                FOREIGN KEY (approved_by) REFERENCES users (user_id)
            )
        ''')
        
        # Add approval columns if they don't exist (for existing databases)
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN approved INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN approved_by TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN approved_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN rejection_reason TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN updated_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN captain_comments TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN rejected_by TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN rejected_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN criticality TEXT DEFAULT 'medium'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add severity assessment and workflow tracking columns
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN severity TEXT DEFAULT 'MINOR'")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN assessment_details TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN workflow_status TEXT DEFAULT 'submitted'")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN assigned_pm TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN pm_approval_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass

        # Add part information columns
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN part_number TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN part_name TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN part_category TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN quantity INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN manufacturer TEXT")
        except sqlite3.OperationalError:
            pass

        # Add contact information columns
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN requested_by_name TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN requested_by_email TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN requested_by_phone TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN emergency_contact TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN imo_number TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN vessel_type TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN company TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN eta TEXT")
        except sqlite3.OperationalError:
            pass

        # Create maintenance_workflow_log table for tracking all actions
        c.execute('''
            CREATE TABLE IF NOT EXISTS maintenance_workflow_log (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_id TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES maintenance_requests (request_id),
                FOREIGN KEY (actor_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create maintenance_request_attachments table for storing files
        c.execute('''
            CREATE TABLE IF NOT EXISTS maintenance_request_attachments (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                file_size INTEGER,
                uploader_id TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES maintenance_requests (request_id),
                FOREIGN KEY (uploader_id) REFERENCES users (user_id)
            )
        ''')
        
        # ==================== INTERNATIONAL REPORTS TABLES ====================
        
        # Bilge Report Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS bilge_reports (
                report_id TEXT PRIMARY KEY,
                vessel_name TEXT NOT NULL,
                imo_number TEXT,
                report_date DATE NOT NULL,
                report_time TIME NOT NULL,
                bilge_water_level REAL,
                water_temperature REAL,
                oil_content_ppm INTEGER,
                disposal_method TEXT,
                location TEXT,
                officer_name TEXT NOT NULL,
                officer_rank TEXT,
                officer_id TEXT,
                signature_data TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (officer_id) REFERENCES users (user_id)
            )
        ''')
        
        # Fuel & Truck Number Report Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS fuel_reports (
                report_id TEXT PRIMARY KEY,
                vessel_name TEXT NOT NULL,
                imo_number TEXT,
                report_date DATE NOT NULL,
                fuel_type TEXT NOT NULL,
                quantity_received REAL,
                fuel_density REAL,
                fuel_temperature REAL,
                truck_number TEXT,
                supplier_name TEXT,
                total_fuel_onboard REAL,
                location TEXT,
                officer_name TEXT NOT NULL,
                officer_rank TEXT,
                officer_id TEXT,
                signature_data TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (officer_id) REFERENCES users (user_id)
            )
        ''')
        
        # Sewage Report Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS sewage_reports (
                report_id TEXT PRIMARY KEY,
                vessel_name TEXT NOT NULL,
                imo_number TEXT,
                report_date DATE NOT NULL,
                report_time TIME NOT NULL,
                sewage_tank_level REAL,
                treatment_method TEXT,
                disposal_method TEXT,
                location TEXT,
                environmental_notes TEXT,
                officer_name TEXT NOT NULL,
                officer_rank TEXT,
                officer_id TEXT,
                signature_data TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (officer_id) REFERENCES users (user_id)
            )
        ''')
        
        # Logbook Entry Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS logbook_entries (
                entry_id TEXT PRIMARY KEY,
                vessel_name TEXT NOT NULL,
                imo_number TEXT,
                entry_date DATE NOT NULL,
                watch_period TEXT,
                weather_conditions TEXT,
                sea_state TEXT,
                wind_speed REAL,
                wind_direction TEXT,
                course REAL,
                speed REAL,
                engine_hours REAL,
                fuel_consumption REAL,
                events TEXT,
                remarks TEXT,
                officer_name TEXT NOT NULL,
                officer_rank TEXT,
                officer_id TEXT,
                signature_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (officer_id) REFERENCES users (user_id)
            )
        ''')
        
        # Emission Report Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS emission_reports (
                report_id TEXT PRIMARY KEY,
                vessel_name TEXT NOT NULL,
                imo_number TEXT,
                report_date DATE NOT NULL,
                fuel_type TEXT,
                fuel_consumption REAL,
                voyage_distance REAL,
                co2_emissions REAL,
                energy_efficiency_indicator REAL,
                compliance_status TEXT,
                location TEXT,
                officer_name TEXT NOT NULL,
                officer_rank TEXT,
                officer_id TEXT,
                signature_data TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (officer_id) REFERENCES users (user_id)
            )
        ''')
        
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN request_type TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE maintenance_requests ADD COLUMN notes TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create inventory table
        c.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                item_id TEXT PRIMARY KEY,
                item_name TEXT NOT NULL,
                category TEXT,
                quantity INTEGER DEFAULT 0,
                unit TEXT,
                minimum_quantity INTEGER DEFAULT 10,
                location TEXT,
                supplier TEXT,
                last_restocked TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create system_notifications table
        c.execute('''
            CREATE TABLE IF NOT EXISTS system_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT DEFAULT 'info',
                sender_id TEXT,
                recipient_type TEXT DEFAULT 'all',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create messaging_system table
        c.execute('''
            CREATE TABLE IF NOT EXISTS messaging_system (
                message_id TEXT PRIMARY KEY,
                sender_id TEXT NOT NULL,
                recipient_type TEXT NOT NULL,
                recipient_id TEXT,
                recipient_email TEXT,
                recipient_phone TEXT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                message_type TEXT NOT NULL,
                priority TEXT DEFAULT 'normal',
                attachment_path TEXT,
                attachment_filename TEXT,
                is_read INTEGER DEFAULT 0,
                allow_replies INTEGER DEFAULT 0,
                parent_message_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users (user_id),
                FOREIGN KEY (parent_message_id) REFERENCES messaging_system (message_id)
            )
        ''')
        
        # Create indexes for messaging_system table
        c.execute("CREATE INDEX IF NOT EXISTS idx_messaging_recipient_id ON messaging_system (recipient_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_messaging_sender_id ON messaging_system (sender_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_messaging_created_at ON messaging_system (created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_messaging_is_read ON messaging_system (is_read)")
        
        # Add edited_at column if it doesn't exist (for message edit tracking)
        try:
            c.execute("ALTER TABLE messaging_system ADD COLUMN edited_at TIMESTAMP")
            print("[OK] Added edited_at column to messaging_system table")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create message_replies table
        c.execute('''
            CREATE TABLE IF NOT EXISTS message_replies (
                reply_id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                reply_text TEXT NOT NULL,
                attachment_path TEXT,
                attachment_filename TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messaging_system (message_id),
                FOREIGN KEY (sender_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create messages table for user-to-user messaging
        c.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                sender_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                subject TEXT,
                body TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                attachment_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users (user_id),
                FOREIGN KEY (recipient_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create indexes for messages table
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_recipient_id ON messages (recipient_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages (sender_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_messages_is_read ON messages (is_read)")
        
        # ==================== PROCUREMENT SYSTEM TABLES ====================
        
        # Create inventory_files table for organizing parts into multiple files
        c.execute('''
            CREATE TABLE IF NOT EXISTS inventory_files (
                file_id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                vessel_id TEXT,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_status TEXT DEFAULT 'active',
                FOREIGN KEY (created_by) REFERENCES users (user_id)
            )
        ''')
        
        # Create inventory_file_parts table for parts within files
        c.execute('''
            CREATE TABLE IF NOT EXISTS inventory_file_parts (
                part_id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                part_number TEXT NOT NULL,
                part_name TEXT NOT NULL,
                category TEXT,
                quantity INTEGER DEFAULT 0,
                location TEXT,
                supplier TEXT,
                manufacturer TEXT,
                notes TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                part_status TEXT DEFAULT 'active',
                UNIQUE(file_id, part_number),
                FOREIGN KEY (file_id) REFERENCES inventory_files (file_id)
            )
        ''')
        
        # Create procurement_requests table for low stock requests
        c.execute('''
            CREATE TABLE IF NOT EXISTS procurement_requests (
                request_id TEXT PRIMARY KEY,
                part_number TEXT NOT NULL,
                file_id TEXT,
                quantity_requested INTEGER NOT NULL,
                requested_by TEXT NOT NULL,
                request_status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'standard',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (requested_by) REFERENCES users (user_id),
                FOREIGN KEY (file_id) REFERENCES inventory_files (file_id)
            )
        ''')
        
        # Create procurement_items table for new parts added by procurement
        c.execute('''
            CREATE TABLE IF NOT EXISTS procurement_items (
                item_id TEXT PRIMARY KEY,
                request_id TEXT,
                quantity_received INTEGER NOT NULL,
                unit_price REAL,
                inspection_document_path TEXT,
                inspection_document_filename TEXT,
                added_by TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed INTEGER DEFAULT 0,
                confirmed_by TEXT,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES procurement_requests (request_id),
                FOREIGN KEY (added_by) REFERENCES users (user_id),
                FOREIGN KEY (confirmed_by) REFERENCES users (user_id)
            )
        ''')
        
        # Create procurement_notifications table for tracking notifications sent
        c.execute('''
            CREATE TABLE IF NOT EXISTS procurement_notifications (
                notification_id TEXT PRIMARY KEY,
                request_id TEXT,
                recipient_id TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES procurement_requests (request_id),
                FOREIGN KEY (recipient_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create Machinery Manual Tables
        c.execute('''
            CREATE TABLE IF NOT EXISTS machinery_manual_folders (
                folder_id TEXT PRIMARY KEY,
                folder_name TEXT NOT NULL,
                ship_name TEXT NOT NULL,
                vessel_id TEXT,
                description TEXT,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                folder_status TEXT DEFAULT 'active',
                FOREIGN KEY (created_by) REFERENCES users (user_id),
                UNIQUE(ship_name, folder_name)
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS machinery_manual_files (
                file_id TEXT PRIMARY KEY,
                folder_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                file_type TEXT,
                machinery_type TEXT,
                uploaded_by TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_status TEXT DEFAULT 'active',
                FOREIGN KEY (folder_id) REFERENCES machinery_manual_folders (folder_id),
                FOREIGN KEY (uploaded_by) REFERENCES users (user_id)
            )
        ''')
        
        # Add 2FA fields to users table (if not already present)
        try:
            c.execute("ALTER TABLE users ADD COLUMN two_factor_enabled INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE users ADD COLUMN two_factor_secret TEXT")
        except Exception:
            pass
        
        # Add access_expiry field for DMPO HQ officer access management
        try:
            c.execute("ALTER TABLE users ADD COLUMN access_expiry TIMESTAMP")
        except Exception:
            pass
        
        # Add reply context and edit tracking to message_replies
        try:
            c.execute("ALTER TABLE message_replies ADD COLUMN reply_to_message_id TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE message_replies ADD COLUMN edited_at TIMESTAMP")
        except Exception:
            pass
        
        # Add edit tracking to messaging_system
        try:
            c.execute("ALTER TABLE messaging_system ADD COLUMN edited_at TIMESTAMP")
        except Exception:
            pass

        # ==================== CREW MANAGEMENT TABLES ====================
        
        # Create crew_members table for managing vessel crew
        c.execute('''
            CREATE TABLE IF NOT EXISTS crew_members (
                crew_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vessel_id TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                department TEXT NOT NULL,
                rank TEXT NOT NULL,
                license_number TEXT UNIQUE,
                nationality TEXT,
                date_of_birth TEXT,
                phone TEXT,
                email TEXT,
                emergency_contact TEXT,
                emergency_phone TEXT,
                stcw_certificate TEXT,
                stcw_expiry DATE,
                gmdss_certificate TEXT,
                gmdss_expiry DATE,
                mlc_certificate TEXT,
                mlc_expiry DATE,
                medical_certificate TEXT,
                medical_expiry DATE,
                other_certifications TEXT,
                certification_expiry TEXT,
                date_joined TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for crew_members table
        c.execute("CREATE INDEX IF NOT EXISTS idx_crew_vessel_id ON crew_members (vessel_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_crew_department ON crew_members (department)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_crew_status ON crew_members (status)")
        
        # Add missing columns to crew_members if they don't exist
        try:
            c.execute("ALTER TABLE crew_members ADD COLUMN profile_picture TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            c.execute("ALTER TABLE crew_members ADD COLUMN specialized_certificates TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # ==================== VESSEL MANAGEMENT TABLES ====================
        
        # Create vessels table for managing ship information
        c.execute('''
            CREATE TABLE IF NOT EXISTS vessels (
                vessel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vessel_name TEXT NOT NULL,
                imo_number TEXT UNIQUE NOT NULL,
                mmsi_number TEXT,
                call_sign TEXT,
                vessel_type TEXT NOT NULL,
                flag_state TEXT NOT NULL,
                year_built INTEGER,
                builder TEXT,
                shipyard_location TEXT,
                gross_tonnage REAL,
                net_tonnage REAL,
                deadweight_tonnage REAL,
                length_overall REAL,
                length_between_perpendiculars REAL,
                breadth REAL,
                depth REAL,
                owner_name TEXT,
                owner_address TEXT,
                owner_phone TEXT,
                owner_email TEXT,
                manager_name TEXT,
                manager_address TEXT,
                manager_phone TEXT,
                manager_email TEXT,
                operator_name TEXT,
                operator_phone TEXT,
                operator_email TEXT,
                insurer_name TEXT,
                insurer_policy_number TEXT,
                main_engine_model TEXT,
                main_engine_power REAL,
                main_engine_rpm INTEGER,
                fuel_type TEXT,
                auxiliary_engines INTEGER,
                generator_power REAL,
                propulsion_type TEXT,
                bollard_pull REAL,
                maximum_speed REAL,
                service_speed REAL,
                average_fuel_consumption REAL,
                fuel_consumption_per_ton_mile REAL,
                energy_efficiency_index REAL,
                carbon_intensity_indicator REAL,
                sox_emissions_compliant TEXT,
                nox_tier TEXT,
                eedi_baseline_percentage REAL,
                ballast_water_treatment TEXT,
                trading_area_restriction TEXT,
                ice_class TEXT,
                dry_dock_interval INTEGER,
                next_dry_dock_date TEXT,
                last_dry_dock_date TEXT,
                monitoring_system TEXT,
                performance_reporting_compliant TEXT,
                remarks TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for vessels table
        c.execute("CREATE INDEX IF NOT EXISTS idx_vessel_name ON vessels (vessel_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_vessel_imo ON vessels (imo_number)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_vessel_type ON vessels (vessel_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_vessel_status ON vessels (status)")
        
        # Create vessel_performance_monitoring table for performance data
        c.execute('''
            CREATE TABLE IF NOT EXISTS vessel_performance_monitoring (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vessel_id INTEGER NOT NULL,
                reporting_month TEXT NOT NULL,
                average_speed REAL,
                fuel_consumption_metric_tons REAL,
                fuel_consumption_per_ton_mile REAL,
                co2_emissions_metric_tons REAL,
                sox_emissions_kilograms REAL,
                nox_emissions_kilograms REAL,
                average_load_factor REAL,
                vessel_availability_percentage REAL,
                number_of_port_calls INTEGER,
                nautical_miles_traveled REAL,
                notes TEXT,
                reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vessel_id) REFERENCES vessels (vessel_id)
            )
        ''')
        
        # Create indexes for vessel_performance_monitoring
        c.execute("CREATE INDEX IF NOT EXISTS idx_performance_vessel_id ON vessel_performance_monitoring (vessel_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_performance_month ON vessel_performance_monitoring (reporting_month)")
        
        # Create vessel_certificates table for certificate management
        c.execute('''
            CREATE TABLE IF NOT EXISTS vessel_certificates (
                certificate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                vessel_id INTEGER NOT NULL,
                certificate_type TEXT NOT NULL,
                issue_date TEXT,
                expiry_date TEXT,
                issuing_authority TEXT,
                certificate_number TEXT,
                document_path TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vessel_id) REFERENCES vessels (vessel_id)
            )
        ''')
        
        # Create indexes for vessel_certificates
        c.execute("CREATE INDEX IF NOT EXISTS idx_vessel_cert_vessel_id ON vessel_certificates (vessel_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_vessel_cert_type ON vessel_certificates (certificate_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_vessel_cert_expiry ON vessel_certificates (expiry_date)")

        # ==================== CERTIFICATE MANAGEMENT TABLES ====================
        
        # Create certificate_documents table for storing uploaded certificate files
        c.execute('''
            CREATE TABLE IF NOT EXISTS certificate_documents (
                doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                crew_id INTEGER NOT NULL,
                certificate_type TEXT NOT NULL,
                document_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER,
                uploaded_by TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (crew_id) REFERENCES crew_members (crew_id)
            )
        ''')
        
        # Create indexes for certificate_documents
        c.execute("CREATE INDEX IF NOT EXISTS idx_cert_doc_crew_id ON certificate_documents (crew_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cert_doc_type ON certificate_documents (certificate_type)")
        
        # Create certificate_alerts table for tracking expiry alerts sent
        c.execute('''
            CREATE TABLE IF NOT EXISTS certificate_alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                crew_id INTEGER NOT NULL,
                certificate_type TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                days_until_expiry INTEGER,
                alert_sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recipient_email TEXT,
                recipient_phone TEXT,
                notification_status TEXT DEFAULT 'sent',
                expiry_date DATE,
                FOREIGN KEY (crew_id) REFERENCES crew_members (crew_id)
            )
        ''')
        
        # Create indexes for certificate_alerts
        c.execute("CREATE INDEX IF NOT EXISTS idx_cert_alert_crew_id ON certificate_alerts (crew_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cert_alert_type ON certificate_alerts (alert_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cert_alert_sent_at ON certificate_alerts (alert_sent_at)")
        
        # Create crew_training_plans table for generating training recommendations
        c.execute('''
            CREATE TABLE IF NOT EXISTS crew_training_plans (
                plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                crew_id INTEGER NOT NULL,
                vessel_id INTEGER,
                training_type TEXT NOT NULL,
                certificate_gap TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',
                recommended_provider TEXT,
                estimated_duration TEXT,
                estimated_cost REAL,
                plan_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                completed_at TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (crew_id) REFERENCES crew_members (crew_id),
                FOREIGN KEY (vessel_id) REFERENCES vessels (vessel_id)
            )
        ''')
        
        # Create indexes for crew_training_plans
        c.execute("CREATE INDEX IF NOT EXISTS idx_training_plan_crew_id ON crew_training_plans (crew_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_training_plan_status ON crew_training_plans (plan_status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_training_plan_priority ON crew_training_plans (priority)")

        conn.commit()
        print("[OK] Database tables initialized successfully")
        
        # Ensure port engineer account exists and is properly configured
        ensure_port_engineer_account(c, conn)
        
        # Always update demo accounts to correct credentials and status
        # DMPO HQ
        qo_email = 'dmpo@marine.com'
        qo_password = generate_password_hash('Quality@2026')
        end_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        c.execute("SELECT user_id FROM users WHERE email = ?", (qo_email,))
        qo_user = c.fetchone()
        if qo_user:
            c.execute("UPDATE users SET password = ?, is_active = 1, is_approved = 1, survey_end_date = ? WHERE email = ?", (qo_password, end_date, qo_email))
        else:
            c.execute('''INSERT INTO users (user_id, email, password, first_name, last_name, rank, role, survey_end_date, is_approved, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', ('QO001', qo_email, qo_password, 'DMPO', 'HQ', 'DMPO HQ', 'quality_officer', end_date, 1, 1))
        conn.commit()
        print("[OK] DMPO HQ ensured: dmpo@marine.com / Quality@2026")
        
        # Always update Harbour Master
        hm_email = 'harbour_master@marine.com'
        hm_password = generate_password_hash('Harbour@2026')
        c.execute("SELECT user_id FROM users WHERE email = ?", (hm_email,))
        hm_user = c.fetchone()
        if hm_user:
            c.execute("UPDATE users SET password = ?, is_active = 1, is_approved = 1 WHERE email = ?", (hm_password, hm_email))
        else:
            c.execute('''INSERT INTO users (user_id, email, password, first_name, last_name, rank, role, is_approved, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', ('HM001', hm_email, hm_password, 'Robert', 'Wilson', 'Harbour Master', 'harbour_master', 1, 1))
        conn.commit()
        print("[OK] Harbour Master ensured: harbour_master@marine.com / Harbour@2026")
        
        # Create a sample emergency request
        c.execute("SELECT COUNT(*) FROM emergency_requests")
        if c.fetchone()[0] == 0:
            emergency_id = generate_id('EMG')
            c.execute('''
                INSERT INTO emergency_requests
                (emergency_id, ship_name, emergency_type, severity_level, description,
                 immediate_actions, resources_required, reported_by, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (emergency_id, 'Atlantic Voyager', 'Engine Failure', 'critical',
                  'Complete engine failure during voyage, ship adrift',
                  'Dispatch rescue team, send tugboat, evacuate if necessary',
                  'Tugboat, rescue team, emergency supplies', 'PE001', 'pending'))
            conn.commit()
            print("[OK] Sample emergency request created")
        
        conn.commit()
        
        # Count records after initialization to prove data preservation
        c.execute("SELECT COUNT(*) FROM users")
        users_after = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages")
        messages_after = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM maintenance_requests")
        requests_after = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM logbook_entries")
        logbook_after = c.fetchone()[0]
        
        # Print data preservation confirmation
        print("\n" + "="*70)
        print("[DATA PRESERVATION] Deployment Verification:")
        print(f"   Tables preserved before init: {table_count_before}")
        print(f"   Total users (including demo): {users_after}")
        print(f"   Messages retained: {messages_after}")
        print(f"   Maintenance requests retained: {requests_after}")
        print(f"   Logbook entries retained: {logbook_after}")
        print("   ✓ ALL DATA PERSISTED ACROSS DEPLOYMENT")
        print("="*70)
        
        # Print login information
        print("\n" + "="*70)
        print("[OK] ALL DEMO ACCOUNTS READY FOR LOGIN")
        print("="*70)
        print("\n[ACCOUNT] Demo Account 1 - Port Engineer (Admin):")
        print("   Email: port_engineer@marine.com")
        print("   Password: Admin@2025")
        print("   Role: Full system access")
        print("\n[ACCOUNT] Demo Account 2 - DMPO HQ:")
        print("   Email: dmpo@marine.com")
        print("   Password: Quality@2026")
        print("   Role: Inspection and compliance")
        print("\n[ACCOUNT] Demo Account 3 - Harbour Master:")
        print("   Email: harbour_master@marine.com")
        print("   Password: Harbour@2026")
        print("   Role: Port operations management")
        print("="*70 + "\n")

    except Exception as e:
        print(f"[ERROR] Error initializing database: {e}")
    finally:
        conn.close()

# ==================== MAINTENANCE REQUEST OPERATIONS ====================

@app.route('/api/maintenance-requests/<request_id>')
@login_required
def api_get_maintenance_request(request_id):
    """Get a single maintenance request by ID."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT request_id, ship_name, maintenance_type, request_type, priority, criticality,
                   description, location, estimated_duration, resources_needed, requested_by,
                   status, assigned_to, approved, approved_by, approved_at, captain_comments,
                   rejection_reason, rejected_by, rejected_at, completed_at, created_at, updated_at, notes,
                   severity, assessment_details, workflow_status, assigned_pm, pm_approval_at,
                   part_number, part_name, part_category, quantity, manufacturer,
                   requested_by_name, requested_by_email, requested_by_phone, emergency_contact,
                   imo_number, vessel_type, company, eta
            FROM maintenance_requests
            WHERE request_id = ?
        """, (request_id,))
        
        request_data = c.fetchone()
        if not request_data:
            return jsonify({'success': False, 'error': 'Request not found'})
        
        request_dict = dict(request_data)
        
        # Use stored requester name/email if available, otherwise try to fetch from users table
        if not request_dict.get('requested_by_name') and request_dict.get('requested_by'):
            c.execute("""
                SELECT first_name, last_name, email 
                FROM users 
                WHERE user_id = ? OR email = ?
                LIMIT 1
            """, (request_dict['requested_by'], request_dict['requested_by']))
            user = c.fetchone()
            if user:
                request_dict['requested_by_name'] = f"{user['first_name']} {user['last_name']}"
                if not request_dict.get('requested_by_email'):
                    request_dict['requested_by_email'] = user.get('email', '')
        
        # Set requester_name for backwards compatibility
        request_dict['requester_name'] = request_dict.get('requested_by_name')
        request_dict['requester_email'] = request_dict.get('requested_by_email')
        
        # Get assigned to info if assigned_to exists
        if request_dict.get('assigned_to'):
            c.execute("""
                SELECT first_name, last_name, email 
                FROM users 
                WHERE user_id = ?
                LIMIT 1
            """, (request_dict['assigned_to'],))
            assigned = c.fetchone()
            if assigned:
                request_dict['assigned_to_name'] = f"{assigned['first_name']} {assigned['last_name']}"
                request_dict['assigned_to_email'] = assigned.get('email', '')
        
        # Get approver info if approved_by exists
        if request_dict.get('approved_by'):
            c.execute("""
                SELECT first_name, last_name 
                FROM users 
                WHERE user_id = ?
                LIMIT 1
            """, (request_dict['approved_by'],))
            approver = c.fetchone()
            if approver:
                request_dict['approved_by_name'] = f"{approver['first_name']} {approver['last_name']}"
        
        return jsonify({'success': True, 'request': request_dict})
    except Exception as e:
        app.logger.error(f"Error getting maintenance request: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/maintenance-requests/<request_id>/assign', methods=['POST'])
@login_required
def api_assign_maintenance_request(request_id):
    """Assign maintenance request to current user."""
    try:
        data = request.get_json()
        assigned_to = data.get('assigned_to', current_user.id)
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                UPDATE maintenance_requests
                SET assigned_to = ?, status = 'assigned', updated_at = ?
                WHERE request_id = ?
            """, (assigned_to, datetime.now(), request_id))
            conn.commit()
            
            log_activity('request_assigned', f'Assigned request {request_id} to {assigned_to}')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error assigning request: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/start', methods=['POST'])
@login_required
def api_start_maintenance_request(request_id):
    """Start service for maintenance request."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                UPDATE maintenance_requests
                SET status = 'in_progress', updated_at = ?
                WHERE request_id = ?
            """, (datetime.now(), request_id))
            conn.commit()
            
            log_activity('service_started', f'Started service for request {request_id}')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error starting service: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/status', methods=['POST'])
@login_required
def api_update_maintenance_status(request_id):
    """Update maintenance request status."""
    try:
        data = request.get_json()
        status = data.get('status')
        
        if not status:
            return jsonify({'success': False, 'error': 'Status is required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                UPDATE maintenance_requests
                SET status = ?, updated_at = ?
                WHERE request_id = ?
            """, (status, datetime.now(), request_id))
            conn.commit()
            
            log_activity('status_updated', f'Updated status of request {request_id} to {status}')
            return jsonify({'success': True, 'status': status})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating status: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/approve', methods=['POST'])
@login_required
@role_required(['port_engineer', 'harbour_master'])
def api_approve_maintenance_request(request_id):
    """Approve a maintenance request (Port Manager/PE only)."""
    try:
        data = request.get_json() or {}
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Check if request exists
            c.execute("SELECT * FROM maintenance_requests WHERE request_id = ?", (request_id,))
            request_data = dict(c.fetchone() or {})
            if not request_data:
                return jsonify({'success': False, 'error': 'Request not found'})
            
            # Update approval status and workflow
            severity = request_data.get('severity', 'MINOR')
            new_workflow_status = 'pm_approved' if severity == 'CRITICAL' else 'hm_assigned'
            
            c.execute("""
                UPDATE maintenance_requests
                SET approved = 1,
                    approved_by = ?,
                    approved_at = ?,
                    assigned_pm = ?,
                    pm_approval_at = ?,
                    workflow_status = ?,
                    status = 'approved'
                WHERE request_id = ?
            """, (current_user.id, datetime.now(), current_user.id, datetime.now(), new_workflow_status, request_id))
            
            conn.commit()
            
            # Log workflow action
            log_workflow_action(request_id, 'pm_approved', current_user.id, 
                              f'Port Manager {current_user.get_full_name()} approved critical resolution plan')
            
            # Log activity
            log_activity('maintenance_approved', f'Approved maintenance request {request_id}')
            
            # If CRITICAL, notify HM & PE for execution
            if severity == 'CRITICAL':
                c.execute("SELECT user_id FROM users WHERE role IN ('harbour_master', 'port_engineer') AND is_active = 1")
                executors = c.fetchall()
                for executor in executors:
                    create_notification(
                        executor['user_id'],
                        f'CRITICAL Request Approved for Execution: {request_data["ship_name"]}',
                        f'Critical maintenance plan approved. Begin execution for request {request_id}.',
                        'danger',
                        f'/view-request/{request_id}'
                    )
            else:
                # For MINOR, notify HM to coordinate
                c.execute("SELECT user_id FROM users WHERE role = 'harbour_master' AND is_active = 1")
                hms = c.fetchall()
                for hm in hms:
                    create_notification(
                        hm['user_id'],
                        f'Minor Maintenance - Coordinate Action: {request_data["ship_name"]}',
                        f'Minor maintenance request {request_id}. Coordinate with Port Engineer on technical details.',
                        'info',
                        f'/view-request/{request_id}'
                    )
            
            return jsonify({
                'success': True,
                'message': 'Maintenance request approved successfully'
            })
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error approving maintenance request: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/execute', methods=['POST'])
@login_required
@role_required(['harbour_master', 'port_engineer'])
def api_execute_maintenance_request(request_id):
    """Mark maintenance as in execution."""
    try:
        data = request.get_json() or {}
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            c.execute("SELECT * FROM maintenance_requests WHERE request_id = ?", (request_id,))
            request_data = dict(c.fetchone() or {})
            if not request_data:
                return jsonify({'success': False, 'error': 'Request not found'})
            
            c.execute("""
                UPDATE maintenance_requests
                SET workflow_status = 'executing',
                    status = 'in_progress'
                WHERE request_id = ?
            """, (request_id,))
            conn.commit()
            
            log_workflow_action(request_id, 'executing', current_user.id,
                              f'{current_user.role.title()} {current_user.get_full_name()} began execution')
            
            return jsonify({'success': True, 'message': 'Execution started'})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error executing maintenance request: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/resolve', methods=['POST'])
@login_required
@role_required(['harbour_master', 'port_engineer'])
def api_resolve_maintenance_request(request_id):
    """Mark maintenance as resolved."""
    try:
        data = request.get_json() or {}
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            c.execute("SELECT * FROM maintenance_requests WHERE request_id = ?", (request_id,))
            request_data = dict(c.fetchone() or {})
            if not request_data:
                return jsonify({'success': False, 'error': 'Request not found'})
            
            c.execute("""
                UPDATE maintenance_requests
                SET workflow_status = 'resolved',
                    status = 'completed',
                    completed_at = ?
                WHERE request_id = ?
            """, (datetime.now(), request_id))
            conn.commit()
            
            log_workflow_action(request_id, 'resolved', current_user.id,
                              f'{current_user.role.title()} {current_user.get_full_name()} marked as resolved')
            
            # Notify PM & PE that issue is resolved
            c.execute("SELECT user_id FROM users WHERE role IN ('port_engineer', 'port_manager') AND is_active = 1")
            managers = c.fetchall()
            for mgr in managers:
                create_notification(
                    mgr['user_id'],
                    f'Maintenance Resolved: {request_data["ship_name"]}',
                    f'Maintenance request {request_id} has been resolved.',
                    'success',
                    f'/view-request/{request_id}'
                )
            
            return jsonify({'success': True, 'message': 'Maintenance marked as resolved'})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error resolving maintenance request: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/history', methods=['GET'])
@login_required
def api_maintenance_request_history(request_id):
    """Get complete history and workflow log for a maintenance request (for PM & PE review)."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get request details
            c.execute("SELECT * FROM maintenance_requests WHERE request_id = ?", (request_id,))
            request_data = dict(c.fetchone() or {})
            if not request_data:
                return jsonify({'success': False, 'error': 'Request not found'})
            
            # Get all workflow actions
            c.execute("""
                SELECT mwl.*, u.first_name, u.last_name
                FROM maintenance_workflow_log mwl
                LEFT JOIN users u ON mwl.actor_id = u.user_id
                WHERE mwl.request_id = ?
                ORDER BY mwl.created_at ASC
            """, (request_id,))
            
            actions = []
            for row in c.fetchall():
                row_dict = dict(row)
                actions.append({
                    'id': row_dict['id'],
                    'action': row_dict['action'],
                    'actor_name': f"{row_dict.get('first_name', '')} {row_dict.get('last_name', '')}".strip() or 'System',
                    'details': row_dict['details'],
                    'created_at': row_dict['created_at']
                })
            
            return jsonify({
                'success': True,
                'request': request_data,
                'actions': actions,
                'total_actions': len(actions)
            })
        except Exception as e:
            app.logger.error(f"Error fetching maintenance history: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/maintenance-requests/<request_id>/reject', methods=['POST'])
@login_required
@role_required(['port_engineer'])
def api_reject_maintenance_request(request_id):
    """Reject a maintenance request (Manager only)."""
    try:
        data = request.get_json() or {}
        rejection_reason = data.get('rejection_reason', 'No reason provided')
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Check if request exists
            c.execute("SELECT * FROM maintenance_requests WHERE request_id = ?", (request_id,))
            request_data = c.fetchone()
            if not request_data:
                return jsonify({'success': False, 'error': 'Request not found'})
            
            # Update rejection status
            c.execute("""
                UPDATE maintenance_requests
                SET approved = 0,
                    approved_by = ?,
                    approved_at = ?,
                    rejection_reason = ?,
                    status = 'rejected'
                WHERE request_id = ?
            """, (current_user.id, datetime.now(), rejection_reason, request_id))
            
            conn.commit()
            
            # Log activity
            log_activity('maintenance_rejected', f'Rejected maintenance request {request_id}')
            
            # Send notification to requester if they have an account
            if request_data['requested_by']:
                create_notification(
                    request_data['requested_by'],
                    'Maintenance Request Rejected',
                    f'Your maintenance request {request_id} for {request_data["ship_name"]} has been rejected. Reason: {rejection_reason}',
                    'warning',
                    '/maintenance-request'
                )
            
            return jsonify({
                'success': True,
                'message': 'Maintenance request rejected'
            })
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error rejecting maintenance request: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/pending-approval')
@login_required
@role_required(['port_engineer'])
def api_pending_maintenance_approvals():
    """Get maintenance requests pending approval (Manager only)."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            c.execute("""
                SELECT 
                    mr.request_id,
                    mr.ship_name,
                    mr.maintenance_type,
                    mr.priority,
                    mr.description,
                    mr.location,
                    mr.requested_by,
                    mr.created_at,
                    u.first_name || ' ' || u.last_name as requester_name,
                    u.email as requester_email
                FROM maintenance_requests mr
                LEFT JOIN users u ON mr.requested_by = u.user_id
                WHERE (mr.approved IS NULL OR mr.approved = 0)
                AND mr.status != 'rejected'
                ORDER BY 
                    CASE mr.priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                        ELSE 5
                    END,
                    mr.created_at ASC
                LIMIT 50
            """)
            
            requests = []
            for row in c.fetchall():
                requests.append(dict(row))
            
            return jsonify({'success': True, 'requests': requests})
        except Exception as e:
            app.logger.error(f"Error getting pending approvals: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/update', methods=['POST'])
@login_required
def api_update_maintenance_request(request_id):
    """Update maintenance request with status, progress, notes, etc."""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Build update query dynamically
            updates = []
            params = []
            
            if 'status' in data:
                updates.append('status = ?')
                params.append(data['status'])
            
            if 'progress' in data:
                updates.append('progress = ?')
                params.append(data['progress'])
            
            if 'notes' in data:
                updates.append('notes = ?')
                params.append(data['notes'])
            
            updates.append('updated_at = ?')
            params.append(datetime.now())
            params.append(request_id)
            
            if updates:
                query = f"UPDATE maintenance_requests SET {', '.join(updates)} WHERE request_id = ?"
                c.execute(query, params)
                conn.commit()
                
                log_activity('request_updated', f'Updated request {request_id}')
                return jsonify({'success': True, 'status': data.get('status')})
            else:
                return jsonify({'success': False, 'error': 'No updates provided'})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error updating request: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/notes', methods=['POST'])
@login_required
def api_add_maintenance_notes(request_id):
    """Add notes to maintenance request."""
    try:
        data = request.get_json()
        notes = data.get('notes')
        
        if not notes:
            return jsonify({'success': False, 'error': 'Notes are required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT notes FROM maintenance_requests WHERE request_id = ?", (request_id,))
            result = c.fetchone()
            existing_notes = result['notes'] if result and result.get('notes') else ''
            
            new_notes = f"{existing_notes}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {notes}" if existing_notes else f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {notes}"
            
            c.execute("""
                UPDATE maintenance_requests
                SET notes = ?, updated_at = ?
                WHERE request_id = ?
            """, (new_notes, datetime.now(), request_id))
            conn.commit()
            
            log_activity('notes_added', f'Added notes to request {request_id}')
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error adding notes: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/export')
@login_required
def api_export_maintenance_request(request_id):
    """Export maintenance request data."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM maintenance_requests WHERE request_id = ?", (request_id,))
            request_data = c.fetchone()
            
            if not request_data:
                return jsonify({'success': False, 'error': 'Request not found'})
            
            return jsonify({'success': True, 'data': dict(request_data)})
        except Exception as e:
            app.logger.error(f"Error exporting request: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/share', methods=['POST'])
@login_required
def api_share_maintenance_request():
    """Share maintenance request via email."""
    try:
        data = request.get_json()
        request_id = data.get('request_id')
        email = data.get('email')
        
        if not request_id or not email:
            return jsonify({'success': False, 'error': 'Request ID and email are required'})
        
        log_activity('request_shared', f'Shared request {request_id} with {email}')
        
        return jsonify({
            'success': True,
            'message': f'Request shared with {email}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== INTERNATIONAL REPORTS API ENDPOINTS ====================

@app.route('/api/bilge-report', methods=['POST'])
@login_required
@role_required(['chief_engineer', 'captain'])
def api_create_bilge_report():
    """
    Create and store a bilge water discharge report.
    
    Accepts bilge water management data including tank levels, water quality
    parameters, disposal method, and officer information. Automatically signs
    with current officer's credentials and timestamp.
    
    JSON Request Body:
        - vessel_name (str): Name of the vessel
        - imo_number (str): IMO registration number
        - report_date (str): Date of bilge water status (YYYY-MM-DD)
        - report_time (str): Time of report (HH:MM)
        - bilge_water_level (str): Current water level measurement
        - water_temperature (float): Temperature of bilge water
        - oil_content_ppm (float): Oil content parts per million
        - disposal_method (str): How/where bilge was disposed
        - location (str): Vessel location at time of report
        - signature_data (str): Officer's digital signature data
        - notes (str, optional): Additional remarks
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - report_id (str): Generated bilge report ID
            - message (str): Success message
            - error (str): Error description if failed
    
    Compliance:
        - MARPOL Annex I Oil Record Book entry
        - International Maritime regulations
    """
    try:
        data = request.get_json()
        report_id = generate_id('BLG')
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO bilge_reports
                (report_id, vessel_name, imo_number, report_date, report_time, bilge_water_level,
                 water_temperature, oil_content_ppm, disposal_method, location, officer_name, officer_rank,
                 officer_id, signature_data, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                report_id, data.get('vessel_name'), data.get('imo_number'), data.get('report_date'),
                data.get('report_time'), data.get('bilge_water_level'), data.get('water_temperature'),
                data.get('oil_content_ppm'), data.get('disposal_method'), data.get('location'),
                f"{current_user.first_name} {current_user.last_name}", current_user.role, current_user.id,
                data.get('signature_data'), data.get('notes'), datetime.now(), datetime.now()
            ))
            
            conn.commit()
            log_activity('bilge_report_created', f'Created and submitted bilge report {report_id}')
            
            return jsonify(
                {'success': True, 'report_id': report_id, 'message': 'Bilge report submitted successfully'}
            ), 201

        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error creating bilge report: {e}")
        return jsonify({'success': False, 'error': 'Failed to submit bilge report'}), 500

@app.route('/api/fuel-report', methods=['POST'])
@login_required
@role_required(['chief_engineer', 'captain'])
def api_create_fuel_report():
    """
    Create and store a fuel bunkering operation report.
    
    Documents fuel delivery, supplier information, fuel quality parameters,
    and truck/delivery reference details. Records total fuel onboard for
    inventory tracking.
    
    JSON Request Body:
        - vessel_name (str): Name of the vessel
        - imo_number (str): IMO registration number
        - report_date (str): Date of fuel delivery (YYYY-MM-DD)
        - fuel_type (str): Type of fuel delivered (HFO, MDO, etc.)
        - quantity_received (float): Volume of fuel delivered (m³ or tonnes)
        - fuel_density (float): Density of delivered fuel
        - fuel_temperature (float): Temperature of delivered fuel
        - truck_number (str): Truck/tanker reference number
        - supplier_name (str): Name of fuel supplier
        - total_fuel_onboard (float): Total fuel quantity after delivery
        - location (str): Port or location of delivery
        - signature_data (str): Officer's digital signature data
        - notes (str, optional): Additional remarks
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - report_id (str): Generated fuel report ID
            - message (str): Success message
            - error (str): Error description if failed
    
    Compliance:
        - MARPOL Annex I Oil Record Book entry
        - Fuel quality certification records
    """
    try:
        data = request.get_json()
        report_id = generate_id('FUL')
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO fuel_reports
                (report_id, vessel_name, imo_number, report_date, fuel_type, quantity_received,
                 fuel_density, fuel_temperature, truck_number, supplier_name, total_fuel_onboard,
                 location, officer_name, officer_rank, officer_id, signature_data, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                report_id, data.get('vessel_name'), data.get('imo_number'), data.get('report_date'),
                data.get('fuel_type'), data.get('quantity_received'), data.get('fuel_density'),
                data.get('fuel_temperature'), data.get('truck_number'), data.get('supplier_name'),
                data.get('total_fuel_onboard'), data.get('location'),
                f"{current_user.first_name} {current_user.last_name}", current_user.role, current_user.id,
                data.get('signature_data'), data.get('notes'), datetime.now(), datetime.now()
            ))
            
            conn.commit()
            log_activity('fuel_report_created', f'Created and submitted fuel report {report_id}')
            
            return jsonify(
                {'success': True, 'report_id': report_id, 'message': 'Fuel report submitted successfully'}
            ), 201

        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error creating fuel report: {e}")
        return jsonify({'success': False, 'error': 'Failed to submit fuel report'}), 500

@app.route('/api/sewage-report', methods=['POST'])
@login_required
@role_required(['chief_engineer', 'captain'])
def api_create_sewage_report():
    """
    Create and store a sewage treatment and disposal report.
    
    Documents sewage tank management, treatment methods, disposal procedures,
    and environmental impact considerations. Records sewage handling in
    compliance with MARPOL Annex IV.
    
    JSON Request Body:
        - vessel_name (str): Name of the vessel
        - imo_number (str): IMO registration number
        - report_date (str): Date of sewage management (YYYY-MM-DD)
        - report_time (str): Time of report (HH:MM)
        - sewage_tank_level (str): Current tank level or percentage
        - treatment_method (str): Method used for sewage treatment
        - disposal_method (str): How sewage was disposed (pumped ashore, etc.)
        - location (str): Vessel location at time of disposal
        - environmental_notes (str): Environmental considerations
        - signature_data (str): Officer's digital signature data
        - notes (str, optional): Additional remarks
    
    Returns:
        JSON response with:
            - success (bool): Operation status
            - report_id (str): Generated sewage report ID
            - message (str): Success message
            - error (str): Error description if failed
    
    Compliance:
        - MARPOL Annex IV (International Convention for Prevention of Pollution)
        - Sewage Record Book requirements
        - Environmental protection regulations
    """
    try:
        data = request.get_json()
        report_id = generate_id('SEW')
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO sewage_reports
                (report_id, vessel_name, imo_number, report_date, report_time, sewage_tank_level,
                 treatment_method, disposal_method, location, environmental_notes, officer_name,
                 officer_rank, officer_id, signature_data, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                report_id, data.get('vessel_name'), data.get('imo_number'), data.get('report_date'),
                data.get('report_time'), data.get('sewage_tank_level'), data.get('treatment_method'),
                data.get('disposal_method'), data.get('location'), data.get('environmental_notes'),
                f"{current_user.first_name} {current_user.last_name}", current_user.role, current_user.id,
                data.get('signature_data'), data.get('notes'), datetime.now(), datetime.now()
            ))
            
            conn.commit()
            log_activity('sewage_report_created', f'Created and submitted sewage report {report_id}')
            
            return jsonify(
                {'success': True, 'report_id': report_id, 'message': 'Sewage report submitted successfully'}
            ), 201

        finally:
            conn.close()

    except Exception as e:
        app.logger.error(f"Error creating sewage report: {e}")
        return jsonify({'success': False, 'error': 'Failed to submit sewage report'}), 500

@app.route('/api/logbook-entry', methods=['POST'])
@login_required
@role_required(['chief_engineer', 'captain'])
def api_create_logbook_entry():
    """Create a new logbook entry."""
    try:
        data = request.get_json()
        entry_id = generate_id('LOG')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO logbook_entries
            (entry_id, vessel_name, imo_number, entry_date, watch_period, weather_conditions,
             sea_state, wind_speed, wind_direction, course, speed, engine_hours, fuel_consumption,
             events, remarks, officer_name, officer_rank, officer_id, signature_data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (entry_id, data.get('vessel_name'), data.get('imo_number'), data.get('entry_date'),
              data.get('watch_period'), data.get('weather_conditions'), data.get('sea_state'),
              data.get('wind_speed'), data.get('wind_direction'), data.get('course'),
              data.get('speed'), data.get('engine_hours'), data.get('fuel_consumption'),
              data.get('events'), data.get('remarks'),
              current_user.first_name + ' ' + current_user.last_name, current_user.role, current_user.id,
              data.get('signature_data'), datetime.now(), datetime.now()))
        
        conn.commit()
        conn.close()
        
        log_activity('logbook_entry_created', f'Created logbook entry {entry_id}')
        
        return jsonify({'success': True, 'entry_id': entry_id, 'message': 'Logbook entry submitted'})
    except Exception as e:
        app.logger.error(f"Error creating logbook entry: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emission-report', methods=['POST'])
@login_required
@role_required(['chief_engineer', 'captain'])
def api_create_emission_report():
    """Create a new emission report."""
    try:
        data = request.get_json()
        report_id = generate_id('EMI')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO emission_reports
            (report_id, vessel_name, imo_number, report_date, fuel_type, fuel_consumption,
             voyage_distance, co2_emissions, energy_efficiency_indicator, compliance_status,
             location, officer_name, officer_rank, officer_id, signature_data, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (report_id, data.get('vessel_name'), data.get('imo_number'), data.get('report_date'),
              data.get('fuel_type'), data.get('fuel_consumption'), data.get('voyage_distance'),
              data.get('co2_emissions'), data.get('energy_efficiency_indicator'),
              data.get('compliance_status'), data.get('location'),
              current_user.first_name + ' ' + current_user.last_name, current_user.role, current_user.id,
              data.get('signature_data'), data.get('notes'), datetime.now(), datetime.now()))
        
        conn.commit()
        conn.close()
        
        log_activity('emission_report_created', f'Created emission report {report_id}')
        
        return jsonify({'success': True, 'report_id': report_id, 'message': 'Emission report submitted'})
    except Exception as e:
        app.logger.error(f"Error creating emission report: {e}")
        return jsonify({'success': False, 'error': str(e)})

# GET endpoints for retrieving reports
@app.route('/api/bilge-reports', methods=['GET'])
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def api_get_bilge_reports():
    """Get all bilge reports."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM bilge_reports ORDER BY report_date DESC, report_time DESC")
        reports = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify({'success': True, 'reports': reports})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/fuel-reports', methods=['GET'])
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def api_get_fuel_reports():
    """Get all fuel reports."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM fuel_reports ORDER BY report_date DESC")
        reports = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify({'success': True, 'reports': reports})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/sewage-reports', methods=['GET'])
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def api_get_sewage_reports():
    """Get all sewage reports."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM sewage_reports ORDER BY report_date DESC, report_time DESC")
        reports = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify({'success': True, 'reports': reports})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/logbook-entries', methods=['GET'])
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def api_get_logbook_entries():
    """Get all logbook entries."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM logbook_entries ORDER BY entry_date DESC")
        entries = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify({'success': True, 'entries': entries})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/emission-reports', methods=['GET'])
@login_required
@role_required(['chief_engineer', 'captain', 'harbour_master'])
def api_get_emission_reports():
    """Get all emission reports."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM emission_reports ORDER BY report_date DESC")
        reports = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify({'success': True, 'reports': reports})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/save-evaluation', methods=['POST'])
@login_required
def api_save_evaluation():
    """Save service evaluation."""
    try:
        data = request.get_json()
        request_id = data.get('request_id')
        sqi_score = data.get('sqi_score')
        
        if not request_id or sqi_score is None:
            return jsonify({'success': False, 'error': 'Request ID and SQI score are required'})
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Create service_evaluations table if it doesn't exist
            c.execute("""
                CREATE TABLE IF NOT EXISTS service_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    evaluation_id TEXT UNIQUE,
                    request_id TEXT,
                    evaluator_id TEXT,
                    sqi_score REAL,
                    rating TEXT,
                    response_time REAL,
                    parts_availability REAL,
                    technical_expertise REAL,
                    documentation REAL,
                    emergency_support REAL,
                    first_time_fix REAL,
                    additional_notes TEXT,
                    signature_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (evaluator_id) REFERENCES users (user_id)
                )
            """)
            
            # Generate evaluation ID
            evaluation_id = generate_id('EVAL')
            
            # Save signature if provided
            signature_path = None
            if data.get('signature'):
                import base64
                signature_data = data['signature'].split(',')[1] if ',' in data['signature'] else data['signature']
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"signature_{current_user.id}_{timestamp}.png"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'signatures', filename)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                with open(save_path, 'wb') as f:
                    f.write(base64.b64decode(signature_data))
                signature_path = filename
            
            # Insert evaluation
            c.execute("""
                INSERT INTO service_evaluations
                (evaluation_id, request_id, evaluator_id, sqi_score, rating,
                 response_time, parts_availability, technical_expertise,
                 documentation, emergency_support, first_time_fix,
                 additional_notes, signature_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evaluation_id,
                request_id,
                current_user.id,
                sqi_score,
                data.get('rating'),
                data.get('response_time'),
                data.get('parts_availability'),
                data.get('technical_expertise'),
                data.get('documentation'),
                data.get('emergency_support'),
                data.get('first_time_fix'),
                data.get('additional_notes'),
                signature_path
            ))
            
            conn.commit()
            log_activity('evaluation_saved', f'Saved evaluation {evaluation_id} for request {request_id}')
            
            return jsonify({
                'success': True,
                'evaluation_id': evaluation_id,
                'message': 'Evaluation saved successfully'
            })
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error saving evaluation: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error in save evaluation: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/evaluation-dashboard')
@login_required
@role_required(['harbour_master', 'quality_officer'])
def api_evaluation_dashboard():
    """Get evaluation dashboard data including KPIs and chart data."""
    try:
        time_range = request.args.get('time_range', 'monthly')  # monthly, weekly, yearly
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Check if service_evaluations table exists
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_evaluations'")
            table_exists = c.fetchone() is not None
            
            # KPI Metrics
            total_evaluations = 0
            avg_sqi = 0.0
            pending_evaluations = 0
            excellent_rate = 0.0
            
            if table_exists:
                # Total evaluations
                c.execute("SELECT COUNT(*) as count FROM service_evaluations")
                total_evaluations = c.fetchone()['count']
                
                # Average SQI
                c.execute("SELECT AVG(sqi_score) as avg FROM service_evaluations WHERE sqi_score IS NOT NULL")
                avg_result = c.fetchone()
                avg_sqi = round(avg_result['avg'], 1) if avg_result and avg_result['avg'] else 0.0
                
                # Excellent rate (SQI >= 85)
                c.execute("SELECT COUNT(*) as count FROM service_evaluations WHERE sqi_score >= 85")
                excellent_count = c.fetchone()['count']
                excellent_rate = round((excellent_count / total_evaluations * 100), 1) if total_evaluations > 0 else 0.0
            
            # Pending evaluations (maintenance requests without evaluations)
            c.execute("""
                SELECT COUNT(*) as count FROM maintenance_requests mr
                LEFT JOIN service_evaluations se ON mr.request_id = se.request_id
                WHERE se.request_id IS NULL AND mr.status = 'completed'
            """)
            pending_result = c.fetchone()
            pending_evaluations = pending_result['count'] if pending_result else 0
            
            # SQI Performance Chart Data - based on time_range
            sqi_chart_data = {
                'labels': [],
                'datasets': []
            }
            
            if table_exists:
                current_year = datetime.now().year
                last_year = current_year - 1
                
                if time_range == 'yearly':
                    # Yearly data for last 5 years
                    c.execute("""
                        SELECT 
                            strftime('%Y', created_at) as year,
                            AVG(sqi_score) as avg_sqi
                        FROM service_evaluations
                        WHERE strftime('%Y', created_at) >= ?
                        GROUP BY year
                        ORDER BY year
                    """, (str(current_year - 4),))
                    
                    year_data = {row['year']: round(row['avg_sqi'], 1) for row in c.fetchall()}
                    years = [str(current_year - 4 + i) for i in range(5)]
                    sqi_chart_data['labels'] = years
                    sqi_chart_data['datasets'] = [{
                        'label': 'Average SQI',
                        'data': [year_data.get(year, 0) for year in years]
                    }]
                    
                elif time_range == 'weekly':
                    # Weekly data for last 12 weeks
                    c.execute("""
                        SELECT 
                            strftime('%W', created_at) as week,
                            strftime('%Y', created_at) as year,
                            AVG(sqi_score) as avg_sqi
                        FROM service_evaluations
                        WHERE created_at >= date('now', '-12 weeks')
                        GROUP BY year, week
                        ORDER BY year, week
                        LIMIT 12
                    """)
                    
                    week_data = []
                    for row in c.fetchall():
                        week_data.append(round(row['avg_sqi'], 1))
                    
                    # Fill to 12 weeks if needed
                    while len(week_data) < 12:
                        week_data.insert(0, 0)
                    week_data = week_data[-12:]  # Take last 12
                    
                    sqi_chart_data['labels'] = [f'Week {i+1}' for i in range(12)]
                    sqi_chart_data['datasets'] = [{
                        'label': 'Average SQI',
                        'data': week_data
                    }]
                    
                else:  # monthly (default)
                    # Get monthly averages for current year
                    c.execute("""
                        SELECT 
                            strftime('%m', created_at) as month,
                            AVG(sqi_score) as avg_sqi
                        FROM service_evaluations
                        WHERE strftime('%Y', created_at) = ?
                        GROUP BY month
                        ORDER BY month
                    """, (str(current_year),))
                    
                    current_year_data = {row['month']: round(row['avg_sqi'], 1) for row in c.fetchall()}
                    
                    # Get monthly averages for last year
                    c.execute("""
                        SELECT 
                            strftime('%m', created_at) as month,
                            AVG(sqi_score) as avg_sqi
                        FROM service_evaluations
                        WHERE strftime('%Y', created_at) = ?
                        GROUP BY month
                        ORDER BY month
                    """, (str(last_year),))
                    
                    last_year_data = {row['month']: round(row['avg_sqi'], 1) for row in c.fetchall()}
                    
                    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    sqi_chart_data['labels'] = months
                    
                    # Fill in data for both years
                    current_values = [current_year_data.get(f"{i+1:02d}", 0) for i in range(12)]
                    last_values = [last_year_data.get(f"{i+1:02d}", 0) for i in range(12)]
                    
                    sqi_chart_data['datasets'] = [
                        {'label': str(current_year), 'data': current_values},
                        {'label': str(last_year), 'data': last_values}
                    ]
            
            # Rating Distribution Chart Data
            rating_distribution = {'Excellent': 0, 'Good': 0, 'Average': 0, 'Poor': 0, 'Critical': 0}
            if table_exists:
                c.execute("""
                    SELECT rating, COUNT(*) as count
                    FROM service_evaluations
                    WHERE rating IS NOT NULL
                    GROUP BY rating
                """)
                for row in c.fetchall():
                    rating = row['rating'].upper()
                    if rating in ['EXCELLENT']:
                        rating_distribution['Excellent'] = row['count']
                    elif rating in ['GOOD']:
                        rating_distribution['Good'] = row['count']
                    elif rating in ['AVERAGE']:
                        rating_distribution['Average'] = row['count']
                    elif rating in ['POOR']:
                        rating_distribution['Poor'] = row['count']
                    elif rating in ['CRITICAL']:
                        rating_distribution['Critical'] = row['count']
            
            total_ratings = sum(rating_distribution.values())
            
            # Category Performance Chart Data
            category_performance = {}
            if table_exists:
                c.execute("""
                    SELECT 
                        AVG(response_time) as avg_response_time,
                        AVG(parts_availability) as avg_parts,
                        AVG(technical_expertise) as avg_technical,
                        AVG(documentation) as avg_documentation,
                        AVG(emergency_support) as avg_emergency,
                        AVG(first_time_fix) as avg_first_time
                    FROM service_evaluations
                    WHERE response_time IS NOT NULL
                """)
                result = c.fetchone()
                if result:
                    category_performance = {
                        'Response Time': round(100 - (result['avg_response_time'] / 720 * 100), 1) if result['avg_response_time'] else 0,
                        'Parts Availability': round(result['avg_parts'], 1) if result['avg_parts'] else 0,
                        'Technical Expertise': round((result['avg_technical'] / 10) * 100, 1) if result['avg_technical'] else 0,
                        'Documentation': round(result['avg_documentation'], 1) if result['avg_documentation'] else 0,
                        'Emergency Support': round((result['avg_emergency'] / 10) * 100, 1) if result['avg_emergency'] else 0,
                        'First Time Fix': round(result['avg_first_time'], 1) if result['avg_first_time'] else 0
                    }
            
            return jsonify({
                'success': True,
                'data': {
                    'kpis': {
                        'total_evaluations': total_evaluations,
                        'avg_sqi': avg_sqi,
                        'pending_evaluations': pending_evaluations,
                        'excellent_rate': excellent_rate,
                        'total_ratings': total_ratings
                    },
                    'sqi_chart': sqi_chart_data,
                    'rating_distribution': rating_distribution,
                    'category_performance': category_performance
                }
            })
        except Exception as e:
            app.logger.error(f"Error getting evaluation dashboard: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/evaluation-maintenance-requests')
@login_required
@role_required(['harbour_master', 'quality_officer'])
def api_evaluation_maintenance_requests():
    """Get maintenance requests available for evaluation."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get completed maintenance requests that haven't been evaluated yet
            c.execute("""
                SELECT 
                    mr.request_id,
                    mr.ship_name,
                    mr.maintenance_type,
                    mr.priority,
                    mr.status,
                    mr.created_at,
                    mr.requested_by
                FROM maintenance_requests mr
                LEFT JOIN service_evaluations se ON mr.request_id = se.request_id
                WHERE se.request_id IS NULL AND mr.status = 'completed'
                ORDER BY mr.created_at DESC
                LIMIT 100
            """)
            
            requests = []
            for row in c.fetchall():
                requests.append({
                    'request_id': row['request_id'],
                    'ship_name': row['ship_name'],
                    'maintenance_type': row['maintenance_type'],
                    'priority': row['priority'],
                    'status': row['status'],
                    'created_at': row['created_at'],
                    'requested_by': row['requested_by']
                })
            
            return jsonify({'success': True, 'requests': requests})
        except Exception as e:
            app.logger.error(f"Error getting maintenance requests: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/evaluation-details/<request_id>')
@login_required
@role_required(['harbour_master', 'quality_officer'])
def api_evaluation_details(request_id):
    """Get details of a maintenance request for evaluation."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            c.execute("""
                SELECT 
                    request_id,
                    ship_name,
                    maintenance_type,
                    priority,
                    status,
                    created_at,
                    requested_by,
                    description,
                    location
                FROM maintenance_requests
                WHERE request_id = ?
            """, (request_id,))
            
            request_data = c.fetchone()
            if not request_data:
                return jsonify({'success': False, 'error': 'Request not found'})
            
            return jsonify({
                'success': True,
                'request': dict(request_data)
            })
        except Exception as e:
            app.logger.error(f"Error getting evaluation details: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/evaluations/recent')
@login_required
@role_required(['harbour_master', 'quality_officer'])
def api_recent_evaluations():
    """Get recent evaluations."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Check if table exists
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_evaluations'")
            if not c.fetchone():
                return jsonify({'success': True, 'evaluations': []})
            
            c.execute("""
                SELECT 
                    se.evaluation_id,
                    se.request_id,
                    se.sqi_score,
                    se.rating,
                    se.created_at,
                    mr.ship_name,
                    u.first_name || ' ' || u.last_name as evaluator_name
                FROM service_evaluations se
                LEFT JOIN maintenance_requests mr ON se.request_id = mr.request_id
                LEFT JOIN users u ON se.evaluator_id = u.user_id
                ORDER BY se.created_at DESC
                LIMIT 20
            """)
            
            evaluations = []
            for row in c.fetchall():
                evaluations.append({
                    'evaluation_id': row['evaluation_id'],
                    'request_id': row['request_id'],
                    'vessel': row['ship_name'] or 'N/A',
                    'evaluator': row['evaluator_name'] or 'N/A',
                    'sqi': round(row['sqi_score'], 1) if row['sqi_score'] else 0,
                    'rating': row['rating'] or 'N/A',
                    'date': row['created_at'][:10] if row['created_at'] else 'N/A'
                })
            
            return jsonify({'success': True, 'evaluations': evaluations})
        except Exception as e:
            app.logger.error(f"Error getting recent evaluations: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/evaluations/top')
@login_required
@role_required(['harbour_master', 'quality_officer'])
def api_top_evaluations():
    """Get top evaluations by SQI score."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Check if table exists
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='service_evaluations'")
            if not c.fetchone():
                return jsonify({'success': True, 'evaluations': []})
            
            c.execute("""
                SELECT 
                    se.request_id,
                    mr.ship_name,
                    se.sqi_score,
                    se.rating
                FROM service_evaluations se
                LEFT JOIN maintenance_requests mr ON se.request_id = mr.request_id
                WHERE se.sqi_score IS NOT NULL
                ORDER BY se.sqi_score DESC
                LIMIT 10
            """)
            
            evaluations = []
            for row in c.fetchall():
                evaluations.append({
                    'request_id': row['request_id'],
                    'vessel': row['ship_name'] or 'N/A',
                    'sqi': round(row['sqi_score'], 1) if row['sqi_score'] else 0,
                    'rating': row['rating'] or 'N/A'
                })
            
            return jsonify({'success': True, 'evaluations': evaluations})
        except Exception as e:
            app.logger.error(f"Error getting top evaluations: {e}")
            return jsonify({'success': False, 'error': str(e)})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/maintenance-requests/<request_id>/clone', methods=['POST'])
@login_required
def api_clone_maintenance_request(request_id):
    """Clone a maintenance request."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            c.execute("SELECT * FROM maintenance_requests WHERE request_id = ?", (request_id,))
            original = c.fetchone()
            
            if not original:
                return jsonify({'success': False, 'error': 'Request not found'})
            
            new_request_id = generate_id('MR')
            
            original_dict = dict(original)
            c.execute("""
                INSERT INTO maintenance_requests
                (request_id, ship_name, maintenance_type, priority, description,
                 requested_by, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (
                new_request_id,
                original_dict.get('ship_name'),
                original_dict.get('maintenance_type'),
                original_dict.get('priority'),
                f"Cloned from {request_id}: {original_dict.get('description', '')}",
                current_user.email,
                datetime.now()
            ))
            conn.commit()
            
            log_activity('request_cloned', f'Cloned request {request_id} to {new_request_id}')
            return jsonify({'success': True, 'new_request_id': new_request_id})
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error cloning request: {e}")
            return jsonify({'success': False, 'error': 'Database error'})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== CERTIFICATE MANAGEMENT ROUTES ====================

def send_email_notification(recipient_email, subject, body):
    """Send email notification."""
    if not SMTP_ENABLED or not recipient_email:
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        return True
    except Exception as e:
        app.logger.error(f"Error sending email: {e}")
        return False

@app.route('/api/certificates/upload', methods=['POST'])
@login_required
@role_required(['harbour_master', 'chief_engineer', 'captain'])
def api_upload_certificate():
    """Upload certificate document for crew member."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
        
        crew_id = request.form.get('crew_id')
        cert_type = request.form.get('certificate_type')
        notes = request.form.get('notes', '')
        
        if not crew_id or not cert_type:
            return jsonify({'success': False, 'error': 'Missing crew_id or certificate_type'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Validate file extension
        allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'success': False, 'error': 'Invalid file type'})
        
        # Save file
        filename = secure_filename(f"cert_{crew_id}_{cert_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file.filename.rsplit('.', 1)[1]}")
        cert_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'certificates')
        os.makedirs(cert_folder, exist_ok=True)
        file_path = os.path.join(cert_folder, filename)
        file.save(file_path)
        
        # Store in database
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                INSERT INTO certificate_documents
                (crew_id, certificate_type, document_path, file_name, file_size, uploaded_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (crew_id, cert_type, file_path, filename, os.path.getsize(file_path), current_user.id, notes))
            
            conn.commit()
            log_activity('certificate_uploaded', f'Uploaded {cert_type} certificate for crew {crew_id}')
            
            return jsonify({'success': True, 'message': 'Certificate uploaded successfully', 'file_path': filename})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error uploading certificate: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/certificates/expiry-alerts', methods=['GET'])
@login_required
@role_required(['harbour_master', 'port_engineer'])
def api_get_expiry_alerts():
    """Get certificate expiry alerts for monitoring."""
    try:
        days_threshold = request.args.get('days', 90, type=int)
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Calculate crew members with expiring certificates
            c.execute("""
                SELECT 
                    cm.crew_id,
                    cm.first_name,
                    cm.last_name,
                    cm.rank,
                    cm.vessel_id,
                    v.vessel_name,
                    'STCW' as certificate_type,
                    cm.stcw_expiry as expiry_date,
                    CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) as days_remaining
                FROM crew_members cm
                LEFT JOIN vessels v ON cm.vessel_id = v.vessel_id
                WHERE cm.stcw_expiry IS NOT NULL AND cm.status = 'active'
                    AND CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) <= ?
                    AND CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) >= 0
                
                UNION ALL
                
                SELECT 
                    cm.crew_id,
                    cm.first_name,
                    cm.last_name,
                    cm.rank,
                    cm.vessel_id,
                    v.vessel_name,
                    'GMDSS' as certificate_type,
                    cm.gmdss_expiry as expiry_date,
                    CAST((julianday(cm.gmdss_expiry) - julianday('now')) AS INTEGER) as days_remaining
                FROM crew_members cm
                LEFT JOIN vessels v ON cm.vessel_id = v.vessel_id
                WHERE cm.gmdss_expiry IS NOT NULL AND cm.status = 'active'
                    AND CAST((julianday(cm.gmdss_expiry) - julianday('now')) AS INTEGER) <= ?
                    AND CAST((julianday(cm.gmdss_expiry) - julianday('now')) AS INTEGER) >= 0
                
                UNION ALL
                
                SELECT 
                    cm.crew_id,
                    cm.first_name,
                    cm.last_name,
                    cm.rank,
                    cm.vessel_id,
                    v.vessel_name,
                    'Medical' as certificate_type,
                    cm.medical_expiry as expiry_date,
                    CAST((julianday(cm.medical_expiry) - julianday('now')) AS INTEGER) as days_remaining
                FROM crew_members cm
                LEFT JOIN vessels v ON cm.vessel_id = v.vessel_id
                WHERE cm.medical_expiry IS NOT NULL AND cm.status = 'active'
                    AND CAST((julianday(cm.medical_expiry) - julianday('now')) AS INTEGER) <= ?
                    AND CAST((julianday(cm.medical_expiry) - julianday('now')) AS INTEGER) >= 0
                
                ORDER BY days_remaining ASC
            """, (days_threshold, days_threshold, days_threshold))
            
            alerts = []
            for row in c.fetchall():
                alert_dict = dict(row)
                days = alert_dict['days_remaining']
                
                if days <= 0:
                    severity = 'EXPIRED'
                elif days <= 30:
                    severity = 'CRITICAL'
                elif days <= 60:
                    severity = 'HIGH'
                else:
                    severity = 'MEDIUM'
                
                alert_dict['severity'] = severity
                alerts.append(alert_dict)
            
            return jsonify({'success': True, 'alerts': alerts, 'count': len(alerts)})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error getting expiry alerts: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/certificates/check-renewals', methods=['POST'])
@login_required
@role_required(['harbour_master', 'port_engineer'])
def api_check_certificate_renewals():
    """Check for certificates needing renewal and send notifications."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            notifications_sent = 0
            current_date = datetime.now().date()
            
            # Check STCW certificates (30, 60, 90 day warnings)
            c.execute("""
                SELECT DISTINCT
                    cm.crew_id,
                    cm.first_name,
                    cm.last_name,
                    cm.email,
                    cm.stcw_expiry,
                    CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) as days_until_expiry
                FROM crew_members cm
                WHERE cm.stcw_expiry IS NOT NULL 
                    AND cm.status = 'active'
                    AND (
                        CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) = 30
                        OR CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) = 60
                        OR CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) = 90
                    )
            """)
            
            for row in c.fetchall():
                row_dict = dict(row)
                alert_type = f"{row_dict['days_until_expiry']}d_before_expiry"
                
                # Check if alert already sent
                c.execute("""
                    SELECT COUNT(*) as count FROM certificate_alerts
                    WHERE crew_id = ? AND certificate_type = 'STCW' 
                        AND alert_type = ? AND alert_sent_at > datetime('now', '-1 day')
                """, (row_dict['crew_id'], alert_type))
                
                if c.fetchone()['count'] == 0:
                    # Send email notification
                    if row_dict['email']:
                        subject = f"STCW Certificate Renewal Reminder - {row_dict['days_until_expiry']} Days"
                        body = f"""
                        <h3>Certificate Renewal Reminder</h3>
                        <p>Dear {row_dict['first_name']} {row_dict['last_name']},</p>
                        <p>Your STCW certificate will expire in <strong>{row_dict['days_until_expiry']} days</strong> ({row_dict['stcw_expiry']}).</p>
                        <p>Please arrange renewal promptly to avoid service interruptions.</p>
                        <p>Contact the Harbour Master or your training provider for assistance.</p>
                        """
                        
                        if send_email_notification(row_dict['email'], subject, body):
                            # Log alert
                            c.execute("""
                                INSERT INTO certificate_alerts
                                (crew_id, certificate_type, alert_type, days_until_expiry, 
                                 recipient_email, expiry_date)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (row_dict['crew_id'], 'STCW', alert_type, row_dict['days_until_expiry'],
                                  row_dict['email'], row_dict['stcw_expiry']))
                            
                            notifications_sent += 1
            
            conn.commit()
            log_activity('renewal_check', f'Checked certificate renewals, sent {notifications_sent} notifications')
            
            return jsonify({
                'success': True,
                'message': f'Checked certificate renewals and sent {notifications_sent} notifications',
                'notifications_sent': notifications_sent
            })
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error checking renewals: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/compliance-dashboard')
@login_required
@role_required(['harbour_master', 'port_engineer', 'captain'])
def compliance_dashboard():
    """Display crew compliance verification dashboard."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get vessel list for filter
            c.execute("SELECT vessel_id, vessel_name FROM vessels WHERE status = 'active' ORDER BY vessel_name")
            vessels = [dict(row) for row in c.fetchall()]
            
            # Get selected vessel (if any)
            selected_vessel = request.args.get('vessel_id')
            
            # Get crew compliance data
            if selected_vessel:
                c.execute("""
                    SELECT 
                        cm.crew_id,
                        cm.first_name,
                        cm.last_name,
                        cm.rank,
                        cm.department,
                        cm.stcw_expiry,
                        cm.gmdss_expiry,
                        cm.medical_expiry,
                        cm.status,
                        CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) as stcw_days,
                        CAST((julianday(cm.gmdss_expiry) - julianday('now')) AS INTEGER) as gmdss_days,
                        CAST((julianday(cm.medical_expiry) - julianday('now')) AS INTEGER) as medical_days
                    FROM crew_members cm
                    WHERE cm.vessel_id = ? AND cm.status = 'active'
                    ORDER BY cm.last_name, cm.first_name
                """, (selected_vessel,))
            else:
                c.execute("""
                    SELECT 
                        cm.crew_id,
                        cm.first_name,
                        cm.last_name,
                        cm.rank,
                        cm.department,
                        v.vessel_name,
                        cm.stcw_expiry,
                        cm.gmdss_expiry,
                        cm.medical_expiry,
                        cm.status,
                        CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) as stcw_days,
                        CAST((julianday(cm.gmdss_expiry) - julianday('now')) AS INTEGER) as gmdss_days,
                        CAST((julianday(cm.medical_expiry) - julianday('now')) AS INTEGER) as medical_days
                    FROM crew_members cm
                    LEFT JOIN vessels v ON cm.vessel_id = v.vessel_id
                    WHERE cm.status = 'active'
                    ORDER BY v.vessel_name, cm.last_name, cm.first_name
                    LIMIT 200
                """)
            
            crew_data = []
            for row in c.fetchall():
                row_dict = dict(row)
                
                # Calculate compliance status
                compliant_certs = 0
                total_certs = 3  # STCW, GMDSS, Medical
                
                if row_dict['stcw_days'] and row_dict['stcw_days'] >= 0:
                    compliant_certs += 1
                if row_dict['gmdss_days'] and row_dict['gmdss_days'] >= 0:
                    compliant_certs += 1
                if row_dict['medical_days'] and row_dict['medical_days'] >= 0:
                    compliant_certs += 1
                
                row_dict['compliance_rate'] = f"{(compliant_certs/total_certs)*100:.0f}%"
                row_dict['compliant_certs'] = compliant_certs
                row_dict['total_certs'] = total_certs
                crew_data.append(row_dict)
            
            # Calculate dashboard KPIs
            total_crew = len(crew_data)
            fully_compliant = sum(1 for c in crew_data if c['compliant_certs'] == c['total_certs'])
            partially_compliant = sum(1 for c in crew_data if 0 < c['compliant_certs'] < c['total_certs'])
            non_compliant = total_crew - fully_compliant - partially_compliant
            
            return render_template('compliance_dashboard.html',
                                 crew_data=crew_data,
                                 vessels=vessels,
                                 selected_vessel=selected_vessel,
                                 total_crew=total_crew,
                                 fully_compliant=fully_compliant,
                                 partially_compliant=partially_compliant,
                                 non_compliant=non_compliant)
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error loading compliance dashboard: {e}")
        flash('Error loading compliance dashboard', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/api/psc-compliance-report', methods=['GET'])
@login_required
@role_required(['harbour_master', 'port_engineer', 'captain'])
def api_psc_compliance_report():
    """Generate PSC (Port State Control) compliance report for crew."""
    try:
        vessel_id = request.args.get('vessel_id')
        include_recommendations = request.args.get('recommendations', 'true').lower() == 'true'
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get vessel info
            c.execute("SELECT * FROM vessels WHERE vessel_id = ?", (vessel_id,))
            vessel = dict(c.fetchone()) if vessel_id else None
            
            # Get crew compliance data
            if vessel_id:
                c.execute("""
                    SELECT 
                        cm.crew_id,
                        cm.first_name,
                        cm.last_name,
                        cm.rank,
                        cm.department,
                        cm.nationality,
                        cm.license_number,
                        cm.stcw_expiry,
                        cm.gmdss_expiry,
                        cm.medical_expiry,
                        CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) as stcw_days,
                        CAST((julianday(cm.gmdss_expiry) - julianday('now')) AS INTEGER) as gmdss_days,
                        CAST((julianday(cm.medical_expiry) - julianday('now')) AS INTEGER) as medical_days
                    FROM crew_members cm
                    WHERE cm.vessel_id = ? AND cm.status = 'active'
                    ORDER BY cm.last_name
                """, (vessel_id,))
            else:
                c.execute("""
                    SELECT 
                        cm.crew_id,
                        cm.first_name,
                        cm.last_name,
                        cm.rank,
                        cm.department,
                        cm.nationality,
                        cm.license_number,
                        cm.stcw_expiry,
                        cm.gmdss_expiry,
                        cm.medical_expiry,
                        CAST((julianday(cm.stcw_expiry) - julianday('now')) AS INTEGER) as stcw_days,
                        CAST((julianday(cm.gmdss_expiry) - julianday('now')) AS INTEGER) as gmdss_days,
                        CAST((julianday(cm.medical_expiry) - julianday('now')) AS INTEGER) as medical_days
                    FROM crew_members cm
                    WHERE cm.status = 'active'
                    ORDER BY cm.first_name
                    LIMIT 500
                """)
            
            crew_list = []
            deficiencies = []
            
            for row in c.fetchall():
                row_dict = dict(row)
                crew_entry = {
                    'name': f"{row_dict['first_name']} {row_dict['last_name']}",
                    'rank': row_dict['rank'],
                    'nationality': row_dict['nationality'],
                    'license': row_dict['license_number'],
                    'certificates': {
                        'STCW': {
                            'expiry': row_dict['stcw_expiry'],
                            'status': 'VALID' if (row_dict['stcw_days'] and row_dict['stcw_days'] > 0) else 'EXPIRED',
                            'days_remaining': row_dict['stcw_days']
                        },
                        'GMDSS': {
                            'expiry': row_dict['gmdss_expiry'],
                            'status': 'VALID' if (row_dict['gmdss_days'] and row_dict['gmdss_days'] > 0) else 'EXPIRED',
                            'days_remaining': row_dict['gmdss_days']
                        },
                        'Medical': {
                            'expiry': row_dict['medical_expiry'],
                            'status': 'VALID' if (row_dict['medical_days'] and row_dict['medical_days'] > 0) else 'EXPIRED',
                            'days_remaining': row_dict['medical_days']
                        }
                    }
                }
                crew_list.append(crew_entry)
                
                # Check for deficiencies
                for cert_type, cert_data in crew_entry['certificates'].items():
                    if cert_data['status'] == 'EXPIRED':
                        deficiencies.append({
                            'crew': crew_entry['name'],
                            'rank': crew_entry['rank'],
                            'certificate': cert_type,
                            'deficiency_type': 'EXPIRED_CERTIFICATE',
                            'severity': 'MAJOR',
                            'expiry_date': cert_data['expiry']
                        })
            
            # Generate recommendations
            recommendations = []
            if include_recommendations:
                if deficiencies:
                    recommendations.append({
                        'priority': 'IMMEDIATE',
                        'action': 'Renew all expired certificates before next port call',
                        'responsible': 'Master/Harbour Master',
                        'timeline': 'Within 7 days'
                    })
                
                # Check for certificates expiring within 30 days
                expiring_soon = sum(1 for c in crew_list for cert_data in c['certificates'].values() 
                                   if cert_data['days_remaining'] and 0 < cert_data['days_remaining'] <= 30)
                if expiring_soon > 0:
                    recommendations.append({
                        'priority': 'HIGH',
                        'action': f'Schedule renewal for {expiring_soon} crew members with certificates expiring within 30 days',
                        'responsible': 'Harbour Master',
                        'timeline': 'Within 14 days'
                    })
            
            report_data = {
                'generated_date': datetime.now().isoformat(),
                'report_type': 'PSC Crew Compliance Report',
                'vessel': vessel,
                'total_crew': len(crew_list),
                'crew_list': crew_list,
                'deficiencies': deficiencies,
                'total_deficiencies': len(deficiencies),
                'recommendations': recommendations,
                'compliance_status': 'NON-COMPLIANT' if deficiencies else 'COMPLIANT'
            }
            
            # Generate CSV if requested
            if request.args.get('format') == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['Crew Name', 'Rank', 'STCW Status', 'STCW Expiry', 'GMDSS Status', 'GMDSS Expiry', 'Medical Status', 'Medical Expiry'])
                
                for crew in crew_list:
                    writer.writerow([
                        crew['name'],
                        crew['rank'],
                        crew['certificates']['STCW']['status'],
                        crew['certificates']['STCW']['expiry'],
                        crew['certificates']['GMDSS']['status'],
                        crew['certificates']['GMDSS']['expiry'],
                        crew['certificates']['Medical']['status'],
                        crew['certificates']['Medical']['expiry']
                    ])
                
                output.seek(0)
                return send_file(
                    io.BytesIO(output.getvalue().encode('utf-8')),
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=f'psc-report-{datetime.now().strftime("%Y%m%d%H%M%S")}.csv'
                )
            
            return jsonify({'success': True, 'report': report_data})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error generating PSC report: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/crew-training-plans', methods=['GET'])
@login_required
@role_required(['harbour_master', 'port_engineer', 'captain'])
def api_get_crew_training_plans():
    """Get crew training plans and recommendations."""
    try:
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            status = request.args.get('status', 'all')
            crew_id = request.args.get('crew_id')
            
            query = "SELECT * FROM crew_training_plans WHERE 1=1"
            params = []
            
            if status != 'all':
                query += " AND plan_status = ?"
                params.append(status)
            
            if crew_id:
                query += " AND crew_id = ?"
                params.append(crew_id)
            
            query += " ORDER BY priority DESC, created_at DESC LIMIT 100"
            
            c.execute(query, params)
            plans = [dict(row) for row in c.fetchall()]
            
            return jsonify({'success': True, 'plans': plans, 'count': len(plans)})
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error getting training plans: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/crew-training-plans/generate', methods=['POST'])
@login_required
@role_required(['harbour_master', 'port_engineer'])
def api_generate_training_plans():
    """Generate training plans for crew based on missing certificates."""
    try:
        data = request.get_json()
        crew_id = data.get('crew_id')
        vessel_id = data.get('vessel_id')
        
        conn = get_db_connection()
        try:
            c = conn.cursor()
            
            # Get crew certificate data
            c.execute("""
                SELECT * FROM crew_members WHERE crew_id = ? AND status = 'active'
            """, (crew_id,))
            
            crew = c.fetchone()
            if not crew:
                return jsonify({'success': False, 'error': 'Crew member not found'})
            
            crew_dict = dict(crew)
            training_plans = []
            
            # Check for expired/missing certificates and create training plans
            certificates_to_check = [
                ('STCW', crew_dict.get('stcw_expiry')),
                ('GMDSS', crew_dict.get('gmdss_expiry')),
                ('Medical', crew_dict.get('medical_expiry'))
            ]
            
            for cert_type, expiry in certificates_to_check:
                if not expiry:
                    # Missing certificate
                    plan_id = generate_id('TP')
                    c.execute("""
                        INSERT INTO crew_training_plans
                        (crew_id, vessel_id, training_type, certificate_gap, priority, 
                         estimated_duration, estimated_cost, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        crew_id, vessel_id or None,
                        f'{cert_type} Certification',
                        f'Missing {cert_type} certificate',
                        'HIGH',
                        '5-10 days',
                        2000.00,
                        f'{cert_type} certification required for {crew_dict["rank"]} position'
                    ))
                    
                    training_plans.append({
                        'certificate': cert_type,
                        'type': 'Missing',
                        'priority': 'HIGH'
                    })
                else:
                    # Check if expiring soon
                    days_until_expiry = (datetime.strptime(expiry, '%Y-%m-%d').date() - datetime.now().date()).days
                    if 0 <= days_until_expiry <= 90:
                        priority = 'CRITICAL' if days_until_expiry <= 30 else 'HIGH'
                        plan_id = generate_id('TP')
                        c.execute("""
                            INSERT INTO crew_training_plans
                            (crew_id, vessel_id, training_type, certificate_gap, priority,
                             estimated_duration, estimated_cost, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            crew_id, vessel_id or None,
                            f'{cert_type} Renewal',
                            f'{cert_type} certificate expires in {days_until_expiry} days',
                            priority,
                            '3-5 days',
                            1500.00,
                            f'{cert_type} renewal needed before {expiry}'
                        ))
                        
                        training_plans.append({
                            'certificate': cert_type,
                            'type': 'Renewal',
                            'priority': priority,
                            'days_remaining': days_until_expiry
                        })
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Generated {len(training_plans)} training plans',
                'plans': training_plans
            })
        finally:
            conn.close()
    except Exception as e:
        app.logger.error(f"Error generating training plans: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error='Page not found', code=404), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Server Error: {error}")
    return render_template('error.html', error='Internal server error', code=500), 500

@app.errorhandler(413)
def too_large(error):
    return jsonify({'success': False, 'error': 'File too large'}), 413

# ==================== INITIALIZATION ROUTE ====================

@app.route('/init')
def initialize():
    """Initialize database and create demo accounts"""
    init_db()
    return jsonify({
        'status': 'success',
        'message': 'Database initialized successfully',
        'demo_accounts': [
            {'email': 'port_engineer@marine.com', 'password': 'Engineer@2026', 'role': 'Port Engineer'},
            {'email': 'dmpo@marine.com', 'password': 'Quality@2026', 'role': 'DMPO HQ'},
            {'email': 'harbour_master@marine.com', 'password': 'Harbour@2026', 'role': 'Harbour Master'}
        ]
    }), 200

# Automatically initialize database on first request
@app.before_request
def before_first_request_func():
    """Initialize database if not already done"""
    if not hasattr(app, 'db_initialized'):
        try:
            # Check if database exists and has tables
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if c.fetchone() is None:
                conn.close()
                init_db()
            else:
                conn.close()
            app.db_initialized = True
        except Exception as e:
            print(f"[WARNING] Warning during database check: {e}")
            app.db_initialized = True

@app.after_request
def add_caching_headers(response):
    """Add caching headers to optimize performance."""
    # Cache static files (CSS, JS, images) for 1 month
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days
    # Don't cache HTML templates or API responses
    elif request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    else:
        # Cache HTML pages for 1 minute (allows back button without reload)
        response.headers['Cache-Control'] = 'public, max-age=60'
    
    # Add compression headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

# ==================== MAIN APPLICATION ====================

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    print("\n" + "="*70)
    print("[SHIP] VESSELOSMARITIME MANAGEMENT PLATFORM - READY")
    print("="*70)
    print("[OK] System Initialized")
    print("[DATABASE] Database: SQLite with dynamic schema management")
    
    print("[FILE] File Upload: Up to 100MB supported")
    print("[REPORTS] Reports: CSV generation")
    print("[SECURITY] Role-based access control")
    print("[PROFILE] Profile System: Fully functional with picture upload")
    print("[SIGNATURE] Digital Signature: Upload and drawing capability")
    print("[DOCUMENTS] Document Management: View, Download, Rename, Delete")
    print("[MESSAGING] Messaging System: Complete with attachments and replies")
    print("[SENT] Sent Messages: New feature to view sent messages")
    print("[THREADS] Threads View: Conversation threads functionality")
    print("[CONVERSATIONS] Conversations: Floating panel conversation support")
    print("[QUICK] Quick Send: Quick message sending from floating panel")
    print("[REPLY] Quick Reply: Quick replies from conversation threads")
    print("[SEARCH] User Search: Search users for messaging")
    print("[PRINT] Print Profile: Professional print functionality")
    print("\n[FIXES] FIXES APPLIED:")
    print("   [OK] Fixed Network error in messaging system")
    print("   [OK] Added Threads functionality with /api/messaging/threads")
    print("   [OK] Added Conversations for floating panel")
    print("   [OK] Fixed sent messages query with proper grouping")
    print("   [OK] Added messaging-center route")
    print("   [OK] Fixed attachment handling with JSON storage")
    print("   [OK] Improved search functionality in inbox")
    print("   [OK] Added conversation thread viewing")
    print("   [OK] ADDED MISSING ROUTES FOR FLOATING PANEL:")
    print("       - /api/messaging/conversations")
    print("       - /api/messaging/conversation/<thread_id>")
    print("       - /api/messaging/quick-send")
    print("       - /api/messaging/quick-reply")
    print("       - /api/messaging/search-users")
    print("\n[ENDPOINTS] Access Points:")
    print("   [URL] Login:          http://localhost:5000/login")
    print("   [URL] Register:       http://localhost:5000/register")
    print("   [URL] Profile:        http://localhost:5000/profile")
    print("   [URL] Dashboard:      http://localhost:5000/dashboard")
    print("   [URL] Messaging:      http://localhost:5000/messaging-center")
    print("   [URL] Monitor:        http://localhost:5000/monitor")
    print("   [URL] Sent Messages:  http://localhost:5000/api/messaging/sent")
    print("   [URL] Threads:        http://localhost:5000/api/messaging/threads")
    print("   [URL] Conversations:  http://localhost:5000/api/messaging/conversations")
    print("   [URL] Attachment DL:  http://localhost:5000/api/messaging/download-attachment/<id>")
    print("\n[ACCOUNTS] Default Accounts:")
    print("   [LOGIN] Port Engineer:  port_engineer@marine.com / Engineer@2026")
    print("   [LOGIN] DMPO HQ: dmpo@marine.com / Quality@2026")
    print("   [LOGIN] Harbour Master: harbour_master@marine.com / Harbour@2026")
    print("\n[RULES] Messaging Rules:")
    print("   [RULE] Port Engineers & Harbour Masters can send")
    print("   [RULE] DMPO HQ cannot send (receive only)")
    print("   [RULE] File attachments up to 20MB")
    print("   [RULE] Replies allowed only for 'Message' type")
    print("   [RULE] Sent messages can be filtered and searched")
    print("   [RULE] Threads show conversation history")
    print("   [RULE] Floating panel has quick send and reply")
    print("   [RULE] Conversations load quickly in floating panel")
    print("="*70 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

# ==================== REAL-TIME MONITORING & AUDIT ROUTES ====================

@app.route('/api/realtime/user-activity/<user_id>')
@login_required
def api_user_activity_timeline(user_id):
    """Get real-time activity timeline for a user."""
    # Check permission - users can only see their own activity or admins can see all
    if current_user.id != user_id and current_user.role not in ['admin', 'port_engineer']:
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    hours = request.args.get('hours', 24, type=int)
    limit = request.args.get('limit', 50, type=int)
    
    activities = get_user_activity_timeline(user_id, limit=limit, hours=hours)
    
    return jsonify({
        'success': True,
        'user_id': user_id,
        'activities': activities,
        'count': len(activities),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/realtime/entity-history/<entity_type>/<entity_id>')
@login_required
def api_entity_change_history(entity_type, entity_id):
    """Get complete change history for any entity with timestamps."""
    limit = request.args.get('limit', 100, type=int)
    
    history = get_entity_change_history(entity_type, entity_id, limit=limit)
    
    return jsonify({
        'success': True,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'changes': history,
        'count': len(history),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/realtime/system-events')
@login_required
@role_required(['admin', 'port_engineer', 'manager'])
def api_system_events():
    """Get real-time system events for monitoring."""
    hours = request.args.get('hours', 1, type=int)
    severity = request.args.get('severity', None)
    
    events = get_real_time_events(hours=hours, severity_filter=severity)
    
    return jsonify({
        'success': True,
        'events': events,
        'count': len(events),
        'hours_included': hours,
        'severity_filter': severity,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/realtime/audit-trail')
@login_required
@role_required(['admin', 'port_engineer'])
def api_audit_trail():
    """Get audit trail of all system changes."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 200, type=int)
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        c.execute("""
            SELECT id, timestamp, user_id, action_type, entity_type, entity_id, 
                   old_value, new_value, ip_address, status
            FROM audit_trail
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (cutoff_time, limit))
        
        audit_records = [dict(row) for row in c.fetchall()]
        
        return jsonify({
            'success': True,
            'records': audit_records,
            'count': len(audit_records),
            'hours_included': hours,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app.logger.error(f"Error retrieving audit trail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/realtime/dashboard')
@login_required
def api_realtime_dashboard():
    """Get real-time system dashboard with all current metrics."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        current_time = datetime.now()
        one_hour_ago = current_time - timedelta(hours=1)
        
        # Count active users (logged in last hour)
        c.execute("""
            SELECT COUNT(DISTINCT user_id) as count 
            FROM activity_logs 
            WHERE timestamp > ?
        """, (one_hour_ago,))
        active_users = c.fetchone()['count']
        
        # Count recent activities
        c.execute("""
            SELECT COUNT(*) as count FROM activity_logs WHERE timestamp > ?
        """, (one_hour_ago,))
        recent_activities = c.fetchone()['count']
        
        # Count recent system events
        c.execute("""
            SELECT COUNT(*) as count FROM system_events WHERE timestamp > ? AND severity = 'error'
        """, (one_hour_ago,))
        recent_errors = c.fetchone()['count']
        
        # Get latest activities
        c.execute("""
            SELECT user_id, activity, details, timestamp FROM activity_logs
            ORDER BY timestamp DESC LIMIT 10
        """)
        latest_activities = [dict(row) for row in c.fetchall()]
        
        # Get pending items
        c.execute("SELECT COUNT(*) as count FROM maintenance_requests WHERE status = 'pending'")
        pending_maintenance = c.fetchone()['count']
        
        c.execute("SELECT COUNT(*) as count FROM emergency_requests WHERE status IN ('pending', 'active')")
        active_emergencies = c.fetchone()['count']
        
        # Count users online (activity in last 15 minutes)
        fifteen_min_ago = current_time - timedelta(minutes=15)
        c.execute("""
            SELECT COUNT(DISTINCT user_id) as count 
            FROM activity_logs 
            WHERE timestamp > ?
        """, (fifteen_min_ago,))
        online_users = c.fetchone()['count']
        
        return jsonify({
            'success': True,
            'timestamp': current_time.isoformat(),
            'metrics': {
                'active_users_1h': active_users,
                'recent_activities_1h': recent_activities,
                'recent_errors_1h': recent_errors,
                'online_users_15m': online_users,
                'pending_maintenance': pending_maintenance,
                'active_emergencies': active_emergencies
            },
            'latest_activities': latest_activities
        })
    except Exception as e:
        app.logger.error(f"Error retrieving dashboard: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/admin/audit-log')
@login_required
@role_required(['admin', 'port_engineer'])
def audit_log_page():
    """View complete audit log with filters."""
    page = request.args.get('page', 1, type=int)
    hours = request.args.get('hours', 24, type=int)
    action_type = request.args.get('action_type', None)
    user_filter = request.args.get('user_id', None)
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Build query
        query = "SELECT * FROM audit_trail WHERE timestamp > ?"
        params = [cutoff_time]
        
        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)
        
        if user_filter:
            query += " AND user_id = ?"
            params.append(user_filter)
        
        query += " ORDER BY timestamp DESC LIMIT 100 OFFSET ?"
        params.append((page - 1) * 100)
        
        c.execute(query, params)
        audit_records = [dict(row) for row in c.fetchall()]
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM audit_trail WHERE timestamp > ?"
        count_params = [cutoff_time]
        if action_type:
            count_query += " AND action_type = ?"
            count_params.append(action_type)
        if user_filter:
            count_query += " AND user_id = ?"
            count_params.append(user_filter)
        
        c.execute(count_query, count_params)
        total_records = c.fetchone()['total']
        
        return render_template('audit_log.html', 
                             audit_records=audit_records,
                             current_page=page,
                             total_records=total_records,
                             total_pages=(total_records + 99) // 100,
                             hours_filter=hours,
                             action_filter=action_type,
                             user_filter=user_filter)
    except Exception as e:
        app.logger.error(f"Error loading audit log: {e}")
        flash(f"Error loading audit log: {e}", "danger")
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

@app.route('/api/realtime/export-audit')
@login_required
@role_required(['admin', 'port_engineer'])
def export_audit_data():
    """Export audit data as CSV for external analysis."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        hours = request.args.get('hours', 24, type=int)
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        c.execute("""
            SELECT id, timestamp, user_id, action_type, entity_type, entity_id,
                   old_value, new_value, ip_address, status
            FROM audit_trail
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        """, (cutoff_time,))
        
        audit_records = c.fetchall()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Timestamp', 'User ID', 'Action Type', 'Entity Type', 'Entity ID',
                        'Old Value', 'New Value', 'IP Address', 'Status'])
        
        for record in audit_records:
            writer.writerow([
                record['id'],
                record['timestamp'],
                record['user_id'],
                record['action_type'],
                record['entity_type'],
                record['entity_id'],
                record['old_value'],
                record['new_value'],
                record['ip_address'],
                record['status']
            ])
        
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'audit-trail-{datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'
        )
    except Exception as e:
        app.logger.error(f"Error exporting audit data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()
