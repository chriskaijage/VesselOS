# Certificate Management System Documentation

## Overview

The Marine Service Center now includes a comprehensive certificate management system designed to ensure crew compliance with international maritime regulations (STCW, GMDSS, Medical). This system provides automated expiry alerts, compliance dashboards, PSC reporting, and training plan generation.

## Features Implemented

### 1. **Certificate Expiry Alerts & Email Notifications**
- **Automatic notifications** 30, 60, and 90 days before certificate expiry
- **Email delivery** using SMTP (configured via environment variables)
- **Alert tracking** in database to prevent duplicate notifications
- **Multiple certificate types**: STCW, GMDSS, Medical, MLV

**Configuration:**
```python
SMTP_SERVER = 'smtp.gmail.com'  # Gmail or your SMTP provider
SMTP_PORT = 587
SENDER_EMAIL = 'marineservice@gmail.com'
SENDER_PASSWORD = 'your_app_password'
```

**Endpoint:** `/api/certificates/check-renewals` (POST)

### 2. **Compliance Verification Dashboards**
Real-time monitoring of crew certificate compliance status.

**Features:**
- View all crew members and their certificate status at a glance
- Filter by vessel, department, or compliance status
- Visual indicators for valid, expiring, and expired certificates
- Compliance percentage calculation per crew member
- KPI cards showing fully compliant, partially compliant, and non-compliant crew

**Route:** `/compliance-dashboard`

**Dashboard Metrics:**
- Total crew members
- Fully compliant crew (all certificates valid)
- Partially compliant crew (some certificates valid)
- Non-compliant crew (expired/missing certificates)

### 3. **Certificate Upload & Storage**
Secure document management for crew certificates.

**Features:**
- Upload PDF, images, and document files
- Automatic file naming and organization
- Link documents to crew members and certificate types
- File size tracking
- Storage in `uploads/certificates/` directory

**Endpoint:** `/api/certificates/upload` (POST)

**Supported file types:** PDF, JPG, JPEG, PNG, DOC, DOCX

### 4. **Renewal Reminders (30/60/90 Days)**
Automated system to track and notify about upcoming certificate expirations.

**Functionality:**
- Automatically checks for certificates expiring in 30, 60, or 90 days
- Sends email notifications to crew members
- Logs alert history in database
- Prevents duplicate notifications within 24 hours

**Endpoint:** `/api/certificates/check-renewals` (POST)

**Alert Types:**
- 90 days before expiry: "MEDIUM" priority reminder
- 60 days before expiry: "HIGH" priority reminder  
- 30 days before expiry: "CRITICAL" priority reminder
- Expired: "BLOCKED" status (crew cannot work)

### 5. **Port State Control (PSC) Compliance Reports**
Generate official compliance reports for port state control inspections.

**Endpoint:** `/api/psc-compliance-report` (GET)

**Report Includes:**
- Complete crew list with ranks and certifications
- Certificate validity status for each crew member
- STCW, GMDSS, Medical certificate details
- Identified deficiencies and non-compliances
- Recommendations for remediation
- Compliance status: COMPLIANT or NON-COMPLIANT

**Query Parameters:**
- `vessel_id` - Filter by specific vessel
- `recommendations=true/false` - Include recommendations
- `format=csv` - Export as CSV file

**Example:**
```bash
GET /api/psc-compliance-report?vessel_id=1&format=csv
```

### 6. **Crew Training Plan Generation**
Automatic generation of training recommendations based on missing/expiring certificates.

**Endpoint:** `/api/crew-training-plans/generate` (POST)

**Features:**
- Identifies missing certificates
- Identifies certificates expiring within 90 days
- Sets priority levels (CRITICAL, HIGH, MEDIUM)
- Provides estimated training duration
- Estimates training costs
- Generates training provider recommendations

**Request Body:**
```json
{
  "crew_id": 1,
  "vessel_id": 2
}
```

**Response Example:**
```json
{
  "success": true,
  "message": "Generated 3 training plans",
  "plans": [
    {
      "certificate": "STCW",
      "type": "Missing",
      "priority": "HIGH"
    },
    {
      "certificate": "GMDSS",
      "type": "Renewal",
      "priority": "CRITICAL",
      "days_remaining": 15
    }
  ]
}
```

## Database Schema

### certificate_documents
Stores uploaded certificate files and metadata.

```sql
CREATE TABLE certificate_documents (
  doc_id INTEGER PRIMARY KEY,
  crew_id INTEGER,
  certificate_type TEXT,
  document_path TEXT,
  file_name TEXT,
  file_size INTEGER,
  uploaded_by TEXT,
  uploaded_at TIMESTAMP,
  notes TEXT,
  FOREIGN KEY (crew_id) REFERENCES crew_members (crew_id)
)
```

### certificate_alerts
Tracks expiry alerts sent and their delivery status.

```sql
CREATE TABLE certificate_alerts (
  alert_id INTEGER PRIMARY KEY,
  crew_id INTEGER,
  certificate_type TEXT,
  alert_type TEXT,
  days_until_expiry INTEGER,
  alert_sent_at TIMESTAMP,
  recipient_email TEXT,
  notification_status TEXT DEFAULT 'sent',
  expiry_date DATE,
  FOREIGN KEY (crew_id) REFERENCES crew_members (crew_id)
)
```

### crew_training_plans
Stores generated training plans and recommendations.

```sql
CREATE TABLE crew_training_plans (
  plan_id INTEGER PRIMARY KEY,
  crew_id INTEGER,
  vessel_id INTEGER,
  training_type TEXT,
  certificate_gap TEXT,
  priority TEXT,
  recommended_provider TEXT,
  estimated_duration TEXT,
  estimated_cost REAL,
  plan_status TEXT,
  created_at TIMESTAMP,
  approved_at TIMESTAMP,
  completed_at TIMESTAMP,
  notes TEXT,
  FOREIGN KEY (crew_id) REFERENCES crew_members (crew_id),
  FOREIGN KEY (vessel_id) REFERENCES vessels (vessel_id)
)
```

## API Endpoints Reference

### Certificate Management

#### Upload Certificate Document
```
POST /api/certificates/upload
Content-Type: multipart/form-data

Parameters:
- file: Certificate document file
- crew_id: ID of crew member
- certificate_type: Type of certificate (STCW, GMDSS, Medical, etc.)
- notes: Optional notes
```

#### Get Expiry Alerts
```
GET /api/certificates/expiry-alerts?days=90
```

Response:
```json
{
  "success": true,
  "alerts": [
    {
      "crew_id": 1,
      "first_name": "John",
      "last_name": "Doe",
      "certificate_type": "STCW",
      "days_remaining": 45,
      "severity": "MEDIUM",
      "expiry_date": "2026-04-15"
    }
  ]
}
```

#### Check Certificate Renewals
```
POST /api/certificates/check-renewals

Checks for certificates expiring in 30/60/90 days and sends notifications.
```

### Compliance & Reporting

#### Get Compliance Dashboard
```
GET /compliance-dashboard?vessel_id=1
```

#### Generate PSC Compliance Report
```
GET /api/psc-compliance-report?vessel_id=1&recommendations=true&format=json
```

### Training Plans

#### Get Training Plans
```
GET /api/crew-training-plans?status=pending&crew_id=1
```

#### Generate Training Plans
```
POST /api/crew-training-plans/generate

Request Body:
{
  "crew_id": 1,
  "vessel_id": 2
}
```

## Integration with Existing System

### Crew Management
The certificate system integrates seamlessly with crew member management:
- Certificate data stored in `crew_members` table
- Certificate documents linked via `crew_id`
- Training plans associated with crew and vessel

### Role-Based Access
Access controlled through role restrictions:
- `harbour_master` - Full access to compliance features
- `port_engineer` - Full access to compliance features
- `chief_engineer` - View-only access to crew compliance
- `captain` - View-only access to crew compliance

## Usage Examples

### Check for Expiring Certificates
```python
# Check every day for certificates expiring in 30/60/90 days
POST /api/certificates/check-renewals

# Returns:
{
  "success": true,
  "message": "Checked certificate renewals and sent 5 notifications",
  "notifications_sent": 5
}
```

### Generate PSC Report
```bash
# Get JSON report
curl https://app.com/api/psc-compliance-report?vessel_id=1

# Export as CSV
curl https://app.com/api/psc-compliance-report?vessel_id=1&format=csv \
  > psc_report.csv
```

### Monitor Compliance Dashboard
```
Navigate to: /compliance-dashboard
- View all crew members
- Filter by vessel
- Check individual compliance status
- Click "Training" to generate training plans
- Click "PSC Report" to download compliance report
```

## Email Configuration

### Gmail Setup
1. Enable 2-Factor Authentication
2. Generate App Password at https://myaccount.google.com/apppasswords
3. Set environment variables:
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SENDER_EMAIL=your_email@gmail.com
   SENDER_PASSWORD=your_app_password
   ```

### Other SMTP Providers
Configure for your SMTP server:
```
SMTP_SERVER=smtp.office365.com (Office 365)
SMTP_SERVER=smtp.sendgrid.net (SendGrid)
SMTP_SERVER=smtp.mailgun.org (Mailgun)
```

## Scheduling Automatic Checks

### Using APScheduler (Recommended)
```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def check_renewals():
    # Call renewal check endpoint
    requests.post('http://localhost:5000/api/certificates/check-renewals')

# Run daily at 8 AM
scheduler.add_job(check_renewals, 'cron', hour=8)
scheduler.start()
```

### Using Cron Job
```bash
# Check renewals daily at 8 AM
0 8 * * * curl -X POST http://app.com/api/certificates/check-renewals
```

## Performance Considerations

- Certificate expiry checks use indexed queries on `expiry_date` fields
- Alert tracking prevents duplicate emails
- Reports are generated on-demand (no pre-computation)
- Database queries optimized with proper INDEXES on:
  - `certificate_alerts.crew_id`
  - `certificate_alerts.alert_type`
  - `crew_members.vessel_id`

## Future Enhancements

1. **SMS Notifications** - Send SMS reminders in addition to email
2. **Training Tracking** - Track completion of generated training plans
3. **Flag State Requirements** - Customize requirements by flag state
4. **Certificate History** - Maintain historical record of all certificates
5. **Automated Scheduling** - Background job to auto-check renewals
6. **Integration with Training Providers** - Direct enrollment in training courses
7. **Mobile App Notifications** - Push notifications for crew members
8. **Custom Alert Thresholds** - Configure alert days per certificate type

## Troubleshooting

### Emails Not Sending
1. Check SMTP configuration in environment variables
2. Verify email provider allows SMTP authentication
3. Check email logs in system (if available)
4. Test with simpler email provider (Gmail with app password)

### Missing Certificates Not Showing
1. Ensure `crew_members` table has NULL values for missing certs (not empty strings)
2. Check database synchronization
3. Verify crew member status is "active"

### PSC Report Shows Unexpected Data
1. Verify crew member vessel assignment
2. Check certificate date formats (YYYY-MM-DD)
3. Review crew status field (active/inactive)

## Support & Issues

For questions or issues, please contact the development team or check the project documentation at:
- GitHub: https://github.com/chriskaijage/marine-service-center
- Issue Tracker: [GitHub Issues]

---

**Last Updated:** February 3, 2026
**Version:** 1.0
**Status:** Production Ready
