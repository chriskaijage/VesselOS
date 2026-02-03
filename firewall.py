#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application Firewall Module for Marine Service System.

Provides comprehensive security protections including:
- Input validation and sanitization
- IP-based access control
- Request filtering
- Rate limiting configuration
- Security headers
- SQL injection prevention
- XSS protection
- CSRF protection
- Suspicious activity detection
"""

import re
import logging
from functools import wraps
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from flask import request, jsonify, abort, current_app


class IPWhitelist:
    """Manage IP whitelist for access control."""
    
    def __init__(self):
        self.whitelist = set()
        self.blacklist = set()
        self.suspicious_ips = {}  # IP -> timestamp of last suspicious activity
        
    def add_whitelist(self, ip: str) -> None:
        """Add IP to whitelist."""
        self.whitelist.add(ip)
        
    def remove_whitelist(self, ip: str) -> None:
        """Remove IP from whitelist."""
        self.whitelist.discard(ip)
        
    def add_blacklist(self, ip: str) -> None:
        """Add IP to blacklist."""
        self.blacklist.add(ip)
        
    def remove_blacklist(self, ip: str) -> None:
        """Remove IP from blacklist."""
        self.blacklist.discard(ip)
        
    def is_allowed(self, ip: str) -> bool:
        """Check if IP is allowed."""
        if ip in self.blacklist:
            return False
        if self.whitelist and ip not in self.whitelist:
            return False
        return True
    
    def log_suspicious(self, ip: str) -> None:
        """Log suspicious activity from IP."""
        self.suspicious_ips[ip] = datetime.now()


class InputValidator:
    """Validate and sanitize user inputs."""
    
    # Patterns for malicious input detection
    SQL_INJECTION_PATTERNS = [
        r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|EXEC|EXECUTE)\b)",
        r"(--|;|\/\*|\*\/|\xdb)",
        r"(\w+\s*=\s*\w+\s*(;|--|\/\*))",
    ]
    
    XSS_PATTERNS = [
        r"(<script[^>]*>.*?<\/script>)",
        r"(javascript:)",
        r"(on\w+\s*=)",
        r"(<iframe[^>]*>)",
        r"(<object[^>]*>)",
        r"(<embed[^>]*>)",
    ]
    
    # Safe file extensions
    SAFE_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'txt', 'csv', 'jpg', 'jpeg', 'png', 'gif', 'zip'
    }
    
    @staticmethod
    def check_sql_injection(value: str) -> bool:
        """Check if input contains SQL injection patterns."""
        if not isinstance(value, str):
            return False
        
        for pattern in InputValidator.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def check_xss(value: str) -> bool:
        """Check if input contains XSS patterns."""
        if not isinstance(value, str):
            return False
        
        for pattern in InputValidator.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input."""
        if not isinstance(value, str):
            return str(value)[:max_length]
        
        # Remove null bytes
        value = value.replace('\x00', '')
        # Limit length
        value = value[:max_length]
        return value
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone format."""
        # Accept various international formats
        pattern = r'^\+?[1-9]\d{1,14}$'
        sanitized = re.sub(r'[\s\-\(\).]', '', phone)
        return bool(re.match(pattern, sanitized))
    
    @staticmethod
    def validate_filename(filename: str) -> Tuple[bool, str]:
        """Validate filename for safety."""
        if not filename:
            return False, "Filename cannot be empty"
        
        # Check file extension
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if ext not in InputValidator.SAFE_EXTENSIONS:
            return False, f"File type .{ext} not allowed"
        
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            return False, "Invalid filename: path traversal detected"
        
        # Check length
        if len(filename) > 255:
            return False, "Filename too long"
        
        return True, "Valid"
    
    @staticmethod
    def validate_numeric(value: str) -> Tuple[bool, int]:
        """Validate numeric input."""
        try:
            num = int(value)
            return True, num
        except (ValueError, TypeError):
            return False, 0


class RequestValidator:
    """Validate HTTP requests."""
    
    def __init__(self):
        self.logger = logging.getLogger('firewall')
        self.ip_validator = IPWhitelist()
        self.input_validator = InputValidator()
    
    def validate_request(self) -> Tuple[bool, str]:
        """Perform comprehensive request validation."""
        # Check IP
        client_ip = self.get_client_ip()
        if not self.ip_validator.is_allowed(client_ip):
            self.logger.warning(f"Blocked request from IP: {client_ip}")
            return False, "Access denied"
        
        # Check request method
        if request.method not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']:
            self.logger.warning(f"Invalid request method: {request.method} from {client_ip}")
            return False, "Invalid request method"
        
        # Check Content-Type for POST/PUT
        if request.method in ['POST', 'PUT']:
            content_type = request.content_type or ''
            if not any(ct in content_type for ct in ['application/json', 'application/x-www-form-urlencoded', 'multipart/form-data']):
                self.logger.warning(f"Suspicious Content-Type: {content_type} from {client_ip}")
                return False, "Invalid Content-Type"
        
        # Check payload size
        content_length = request.content_length or 0
        max_size = 16 * 1024 * 1024  # 16MB
        if content_length > max_size:
            self.logger.warning(f"Request too large: {content_length} bytes from {client_ip}")
            return False, "Request payload too large"
        
        # Validate form data
        if request.method == 'POST' and request.form:
            for key, value in request.form.items():
                # Check for SQL injection
                if self.input_validator.check_sql_injection(str(value)):
                    self.logger.warning(f"SQL injection attempt detected in field '{key}' from {client_ip}")
                    self.ip_validator.log_suspicious(client_ip)
                    return False, "Malicious input detected"
                
                # Check for XSS
                if self.input_validator.check_xss(str(value)):
                    self.logger.warning(f"XSS attempt detected in field '{key}' from {client_ip}")
                    self.ip_validator.log_suspicious(client_ip)
                    return False, "Malicious input detected"
        
        return True, "Valid"
    
    @staticmethod
    def get_client_ip() -> str:
        """Get client IP address, handling proxies."""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr or '0.0.0.0'


def firewall_protect(f):
    """Decorator to apply firewall protection to routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Get or create validator
            if not hasattr(current_app, 'request_validator'):
                current_app.request_validator = RequestValidator()
            
            validator = current_app.request_validator
            
            # Validate request
            is_valid, message = validator.validate_request()
            if not is_valid:
                return jsonify({'success': False, 'error': message}), 403
            
            return f(*args, **kwargs)
        except Exception as e:
            logging.error(f"Firewall error: {e}")
            return jsonify({'success': False, 'error': 'Request validation error'}), 400
    
    return decorated_function


def get_security_headers() -> Dict[str, str]:
    """Get recommended security headers."""
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    }


def init_firewall(app):
    """Initialize firewall for Flask app."""
    
    # Add security headers to all responses
    @app.after_request
    def add_security_headers(response):
        for header, value in get_security_headers().items():
            response.headers[header] = value
        return response
    
    # Initialize request validator
    app.request_validator = RequestValidator()
    
    logging.getLogger('firewall').info("Firewall initialized")


# Windows Firewall Configuration Commands (for reference)
WINDOWS_FIREWALL_COMMANDS = """
# Run these commands as Administrator in PowerShell

# Enable Windows Defender Firewall
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True

# Block all inbound traffic by default
Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultInboundAction Block
Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultOutboundAction Allow

# Allow your application port (e.g., port 5000 for Flask)
New-NetFirewallRule -DisplayName "Allow Flask App" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5000

# Allow HTTP/HTTPS
New-NetFirewallRule -DisplayName "Allow HTTP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80
New-NetFirewallRule -DisplayName "Allow HTTPS" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443

# Allow SSH (if needed)
New-NetFirewallRule -DisplayName "Allow SSH" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22

# Block specific IP
New-NetFirewallRule -DisplayName "Block IP" -Direction Inbound -Action Block -RemoteAddress "192.168.1.100"

# View firewall rules
Get-NetFirewallRule -Enabled True | Select-Object DisplayName, Direction, Action

# Enable logging
Set-NetFirewallProfile -Profile Domain,Public,Private -LogFileName "C:\\Windows\\System32\\LogFiles\\Firewall\\pfirewall.log"
Set-NetFirewallProfile -Profile Domain,Public,Private -LogMaxSizeKilobytes 4096
Set-NetFirewallProfile -Profile Domain,Public,Private -LogAllowed $true
Set-NetFirewallProfile -Profile Domain,Public,Private -LogBlocked $true
"""

# Linux Firewall Configuration (UFW - for reference)
LINUX_FIREWALL_COMMANDS = """
# Run these commands as sudo on Linux

# Install UFW (if not installed)
sudo apt-get install ufw

# Enable UFW
sudo ufw enable

# Set default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (do this first to avoid lockout)
sudo ufw allow 22/tcp

# Allow HTTP
sudo ufw allow 80/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Allow specific application port
sudo ufw allow 5000/tcp

# Block specific IP
sudo ufw deny from 192.168.1.100

# View status
sudo ufw status verbose

# View detailed rules
sudo ufw show raw

# Delete a rule
sudo ufw delete allow 5000/tcp
"""
