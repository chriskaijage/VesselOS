# Marine Service System - Firewall Configuration Guide

## Overview
This document provides comprehensive firewall setup instructions for the Marine Service System at both application and operating system levels.

## Application-Level Firewall Features

The system now includes built-in security features:

### 1. Input Validation
- **SQL Injection Detection**: Monitors for SQL keywords and syntax
- **XSS Prevention**: Detects script tags and javascript: handlers
- **String Sanitization**: Removes null bytes and limits string lengths
- **File Validation**: Checks extensions and prevents path traversal

### 2. Request Filtering
- IP-based whitelisting/blacklisting
- Content-Type validation
- Request size limits (16MB default)
- HTTP method validation
- Suspicious activity tracking

### 3. Security Headers
All responses include security headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy` for script/style management
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` restricting device access

### 4. Rate Limiting
- 5000 requests per day (default limit)
- 500 requests per hour per IP
- Customizable per route

---

## Windows Firewall Setup

### Enable Windows Defender Firewall

Open PowerShell as Administrator and run:

```powershell
# Enable firewall for all profiles
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True

# Set strict default policies
Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultInboundAction Block
Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultOutboundAction Allow
```

### Allow Application Ports

```powershell
# Allow Flask development server (port 5000)
New-NetFirewallRule -DisplayName "Marine Service - App" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5000

# Allow HTTP (port 80)
New-NetFirewallRule -DisplayName "Allow HTTP" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80

# Allow HTTPS (port 443)
New-NetFirewallRule -DisplayName "Allow HTTPS" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443

# Allow SSH for remote management (optional)
New-NetFirewallRule -DisplayName "Allow SSH" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22
```

### Block Specific IPs

```powershell
# Block malicious IP
New-NetFirewallRule -DisplayName "Block Malicious IP" `
    -Direction Inbound -Action Block `
    -RemoteAddress "192.168.1.100"

# Block entire subnet
New-NetFirewallRule -DisplayName "Block Subnet" `
    -Direction Inbound -Action Block `
    -RemoteAddress "192.168.1.0/24"
```

### Enable Firewall Logging

```powershell
# Configure logging for blocked connections
Set-NetFirewallProfile -Profile Domain,Public,Private `
    -LogFileName "C:\Windows\System32\LogFiles\Firewall\pfirewall.log"

Set-NetFirewallProfile -Profile Domain,Public,Private `
    -LogMaxSizeKilobytes 4096

Set-NetFirewallProfile -Profile Domain,Public,Private `
    -LogAllowed $true

Set-NetFirewallProfile -Profile Domain,Public,Private `
    -LogBlocked $true
```

### View Firewall Rules

```powershell
# List all enabled rules
Get-NetFirewallRule -Enabled True | Select-Object DisplayName, Direction, Action

# Show rule details with ports
Get-NetFirewallRule -Direction Inbound -Action Allow | 
    Get-NetFirewallPortFilter | Select-Object Protocol, LocalPort

# Export rules for backup
Export-NetFirewallPolicy -PolicyStore ActiveStore -FilePath "firewall_backup.wfw"
```

### Verify Configuration

```powershell
# Test connectivity
Test-NetConnection -ComputerName "localhost" -Port 5000 -InformationLevel Detailed

# Check if port is listening
Get-NetTCPConnection -LocalPort 5000

# Monitor firewall events
Get-EventLog -LogName Security | Where-Object {$_.EventID -eq 5152} | Select-Object TimeGenerated, Message
```

---

## Linux Firewall Setup (UFW)

### Install and Enable UFW

```bash
# Install UFW
sudo apt-get update
sudo apt-get install ufw -y

# Enable UFW
sudo ufw enable

# Verify status
sudo ufw status
```

### Configure Default Policies

```bash
# Set default policies (deny inbound, allow outbound)
sudo ufw default deny incoming
sudo ufw default allow outgoing
```

### Allow Necessary Ports

```bash
# Allow SSH first (to avoid lockout)
sudo ufw allow 22/tcp

# Allow HTTP
sudo ufw allow 80/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Allow application port
sudo ufw allow 5000/tcp

# Allow specific service by name
sudo ufw allow http
sudo ufw allow https
```

### Allow Specific IPs

```bash
# Allow specific IP
sudo ufw allow from 192.168.1.100

# Allow specific IP on specific port
sudo ufw allow from 192.168.1.100 to any port 5000

# Allow IP range
sudo ufw allow from 192.168.1.0/24
```

### Block IPs and Ports

```bash
# Block specific IP
sudo ufw deny from 192.168.1.100

# Block port globally
sudo ufw deny 3306  # Block MySQL port

# Block incoming on specific port
sudo ufw deny in 2222
```

### View and Manage Rules

```bash
# Show all rules
sudo ufw show raw

# Show numbered rules
sudo ufw status numbered

# Delete rule by number
sudo ufw delete 1

# Delete rule by name
sudo ufw delete allow http

# Reset all rules (use with caution!)
sudo ufw reset
```

### Enable Logging

```bash
# Enable low-level logging
sudo ufw logging on

# Set logging level
sudo ufw logging medium

# View logs
sudo tail -f /var/log/ufw.log

# Monitor in real-time
sudo journalctl -u ufw -f
```

---

## Network-Level Protection

### Use a Reverse Proxy

Configure Nginx as a reverse proxy with WAF capabilities:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=one:10m rate=10r/s;
    limit_req zone=one burst=20;

    # Proxy to Flask app
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### DDoS Protection

1. **Use CloudFlare or Akamai** for DDoS mitigation
2. **Rate Limiting** (already configured in app)
3. **Connection Limits** via firewall
4. **IP Reputation Checking**

### VPN/SSH Access

For remote access, use SSH tunneling:

```bash
# SSH tunnel to access internal port
ssh -L 5000:localhost:5000 user@your-server.com

# Then access locally at http://localhost:5000
```

---

## Monitoring and Logging

### Enable Application Logging

The firewall module logs to `firewall` logger. Configure in your app:

```python
import logging

# Configure firewall logging
fw_logger = logging.getLogger('firewall')
fw_logger.setLevel(logging.INFO)

handler = logging.FileHandler('logs/firewall.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
fw_logger.addHandler(handler)
```

### Monitor Suspicious Activity

Check for suspicious patterns:

```bash
# View blocked requests
grep "Blocked request\|SQL injection\|XSS attempt" logs/firewall.log

# Check failed login attempts
grep "invalid credentials\|login failed" logs/firewall.log

# Monitor access patterns
tail -f logs/firewall.log
```

---

## Best Practices

1. **Regular Updates**: Keep OS and firewall rules updated
2. **Least Privilege**: Only open necessary ports
3. **Monitor Logs**: Review firewall logs regularly
4. **Test Rules**: Verify rules work as intended
5. **Backup Configuration**: Export firewall rules periodically
6. **Use HTTPS**: Always use SSL/TLS in production
7. **Strong Passwords**: Require complex passwords
8. **2FA**: Enable two-factor authentication
9. **API Keys**: Rotate API keys regularly
10. **Database**: Keep database on internal network only

---

## Firewall Rule Templates

### Development Environment
- Allow all traffic from localhost
- Restrict external access
- Enable detailed logging

### Production Environment
- Whitelist only known IPs
- Strict rate limiting
- Enable all security features
- Monitor 24/7

### Staging Environment
- Intermediate restrictions
- Test all rules before production
- Monitor for issues

---

## Troubleshooting

### Can't Access Application
```bash
# Check if port is listening
netstat -tuln | grep 5000

# Check firewall rules
sudo ufw status verbose

# Temporarily disable firewall (for testing only)
sudo ufw disable
```

### High False Positives
- Adjust SQL injection patterns in `firewall.py`
- Increase rate limits if legitimate traffic is blocked
- Whitelist trusted IPs

### Performance Issues
- Check firewall logging overhead
- Reduce logging verbosity in production
- Use caching to reduce requests

---

## Additional Resources

- [Windows Firewall Documentation](https://docs.microsoft.com/en-us/windows/security/threat-protection/windows-firewall/)
- [UFW Documentation](https://help.ubuntu.com/community/UFW)
- [OWASP Security Best Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
- [Flask Security](https://flask.palletsprojects.com/en/2.0.x/security/)

