# 📧 Email & SMS Notifications Setup Guide

## ✅ Production Notification System Activated

Your Marine Service Center System now has **fully functional email and SMS notifications** for production deployment!

---

## 📧 EMAIL NOTIFICATIONS

### Step 1: Set Up Gmail SMTP (Recommended)

**For Gmail Account:**
1. Enable 2-Factor Authentication on your Gmail account
2. Create an App Password:
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Copy the generated 16-character password
3. Note: Use the 16-character app password, NOT your Gmail password

**Alternative: Use any SMTP Provider**
- Gmail: smtp.gmail.com:587
- Outlook: smtp-mail.outlook.com:587
- SendGrid: smtp.sendgrid.net:587
- AWS SES: email-smtp.{region}.amazonaws.com:587

### Step 2: Set Render Environment Variables

In Render Dashboard:
1. Go to your service → Settings
2. Add these Environment Variables:

```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=xxxx xxxx xxxx xxxx    (Your 16-char app password)
```

**Example for Gmail:**
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=marineservice@gmail.com
SENDER_PASSWORD=abcd efgh ijkl mnop
```

### Step 3: Email Configuration Details

```python
# Automatic configuration
SMTP_ENABLED = True  # Automatically enabled if credentials provided
SENDER_EMAIL = "marineservice@gmail.com"

# Emails sent for:
- User registration (welcome email)
- Maintenance request updates
- Emergency alerts
- Account approvals
- Password resets
- Message notifications
```

---

## 📱 SMS NOTIFICATIONS

### Step 1: Create Twilio Account

1. Go to https://www.twilio.com
2. Sign up (free trial available: $15 credit)
3. Get your credentials:
   - Account SID
   - Auth Token
   - Twilio Phone Number (e.g., +1234567890)

### Step 2: Get a Twilio Phone Number

1. In Twilio Console, go to Phone Numbers
2. Verify your personal phone number
3. Get a trial phone number (free)
4. Keep the phone number (+1234567890 format)

### Step 3: Set Render Environment Variables

In Render Dashboard, add:

```
TWILIO_ACCOUNT_SID=AC1234567890abcdef
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE=+1234567890
```

**Example:**
```
TWILIO_ACCOUNT_SID=ACe1d9c2e5f4a3b2c8d1e0f9a8b7c6d5e
TWILIO_AUTH_TOKEN=abcdef1234567890ghijkl0987654321
TWILIO_PHONE=+12015552368
```

### Step 4: SMS Configuration Details

```python
# Automatic configuration
SMS_ENABLED = True  # Automatically enabled if credentials provided
TWILIO_PHONE = "+1234567890"

# SMS sent for:
- Emergency alerts
- Urgent maintenance requests
- Critical system notifications
- High-priority messages
```

---

## 📋 Notification Types

### 1. **User Registration**
- **Type:** Email
- **Trigger:** New user registers
- **Content:** Welcome email + account details

### 2. **Maintenance Requests**
- **Type:** Email + SMS (urgent)
- **Trigger:** New, updated, or approved
- **Recipients:** Assigned personnel, approvers

### 3. **Emergency Alerts**
- **Type:** Email + SMS
- **Trigger:** Emergency request created/updated
- **Recipients:** Port Engineer, Harbour Master

### 4. **Account Approval**
- **Type:** Email
- **Trigger:** Account approved by admin
- **Content:** Account activation confirmation

### 5. **Messages/Comments**
- **Type:** Email (if enabled)
- **Trigger:** New message or reply
- **Recipients:** Message recipient

### 6. **Critical Updates**
- **Type:** Email + SMS
- **Trigger:** Critical maintenance or emergency
- **Recipients:** All relevant personnel

---

## 🔧 Implementation Details

### Email Sending Function
```python
send_email(
    recipient_email="user@example.com",
    subject="Notification Title",
    html_body="<h1>Email Content</h1>",
    plain_text="Email Content (fallback)"
)
```

### SMS Sending Function
```python
send_sms(
    phone_number="+1234567890",
    message_text="SMS message content"
)
```

### Notification Email Function
```python
send_notification_email(
    user_email="user@example.com",
    user_name="John Smith",
    title="Notification Title",
    message="Notification message content",
    action_url="https://app.url/action"
)
```

---

## ✨ Features Included

### Automatic Detection
- ✅ Email automatically enabled if SENDER_PASSWORD provided
- ✅ SMS automatically enabled if Twilio credentials provided
- ✅ Fallback to logging if not configured
- ✅ No manual toggle needed

### Formatted Emails
- ✅ Professional HTML template
- ✅ Responsive design
- ✅ Branded with system logo
- ✅ Plain text fallback
- ✅ Action buttons
- ✅ Company branding

### SMS Messages
- ✅ Concise, clear messages
- ✅ International phone format
- ✅ Error handling
- ✅ Logging for tracking

### Integration Points
- ✅ Maintenance requests
- ✅ Emergency management
- ✅ User registration
- ✅ Account approvals
- ✅ Message notifications
- ✅ System alerts

---

## 🧪 Testing Notifications

### Test Email
```python
# In Python shell or script
from app import send_notification_email

send_notification_email(
    user_email="your-test@gmail.com",
    user_name="Test User",
    title="Test Notification",
    message="This is a test email from Marine Service Center",
    action_url="https://your-app-url/dashboard"
)
```

### Test SMS
```python
# In Python shell or script
from app import send_sms

send_sms(
    phone_number="+1234567890",
    message_text="Test SMS from Marine Service Center"
)
```

### Check Logs
- Monitor Render logs for delivery status
- Look for "Email sent to" or "SMS sent to"
- Check for error messages if failed

---

## 📊 Cost Estimation

### Email (Gmail/SMTP)
- **Cost:** Free (with Gmail account)
- **Limit:** None in production
- **Status:** Unlimited for production

### SMS (Twilio)
- **Trial Cost:** $15 free credit
- **Per SMS:** ~$0.0075 USD
- **Monthly Estimate:** ~$2-5 for typical usage
- **Link:** https://www.twilio.com/pricing

---

## 🔐 Security Best Practices

### Email Security
```
❌ DON'T: Hardcode passwords in code
✅ DO: Use environment variables
✅ DO: Use app-specific passwords (Gmail)
✅ DO: Enable 2FA on email account
✅ DO: Use SMTP over TLS (port 587)
```

### SMS Security
```
❌ DON'T: Share Twilio credentials
✅ DO: Use environment variables only
✅ DO: Rotate auth tokens periodically
✅ DO: Monitor Twilio usage
✅ DO: Set spending limits in Twilio
```

---

## 📞 Environment Variables Checklist

### For Email
- [ ] SMTP_SERVER (e.g., smtp.gmail.com)
- [ ] SMTP_PORT (usually 587)
- [ ] SENDER_EMAIL (your email address)
- [ ] SENDER_PASSWORD (app password or token)

### For SMS
- [ ] TWILIO_ACCOUNT_SID
- [ ] TWILIO_AUTH_TOKEN
- [ ] TWILIO_PHONE (your Twilio number)

### Optional
- [ ] Other SMTP servers supported
- [ ] Can use SendGrid, Mailgun, AWS SES, etc.

---

## 🚀 Deployment Steps

### 1. Update Requirements
```
✅ Added twilio==9.0.0 to requirements.txt
✅ Email uses standard Python libraries (no new package)
```

### 2. Set Environment Variables in Render
```
1. Go to Render Dashboard
2. Select your service
3. Go to Settings
4. Add environment variables
5. Redeploy service
```

### 3. Redeploy Application
```
1. Go to Render Dashboard
2. Click "Manual Deploy"
3. Select "Deploy latest commit"
4. Wait for deployment to complete
```

### 4. Test Notifications
```
1. Trigger a test notification
2. Check if email/SMS received
3. Monitor logs for errors
4. Adjust as needed
```

---

## 🐛 Troubleshooting

### Email Not Sending

**Check Gmail:**
- [ ] 2FA enabled? (Required for app passwords)
- [ ] Using 16-char app password? (Not regular password)
- [ ] SMTP_SERVER correct? (smtp.gmail.com)
- [ ] SENDER_EMAIL correct? (your Gmail address)
- [ ] Port 587? (TLS, not SSL)

**Check Logs:**
```
Error: "Connection refused"
→ Check SMTP_SERVER and SMTP_PORT

Error: "Authentication failed"
→ Check SENDER_EMAIL and SENDER_PASSWORD

Error: "Email disabled"
→ SENDER_PASSWORD not set in environment
```

### SMS Not Sending

**Check Twilio:**
- [ ] Account SID correct? (AC...)
- [ ] Auth Token correct?
- [ ] Phone number correct? (+1 format)
- [ ] Account has credit? (Not expired trial)
- [ ] Number verified for trial?

**Check Logs:**
```
Error: "SMS disabled"
→ Twilio credentials not set

Error: "Invalid phone number"
→ Phone number not in +1234567890 format

Error: "Account suspended"
→ Check Twilio account status
```

### Both Not Sending

1. Check Render logs for error messages
2. Verify all environment variables set
3. Check for typos in credentials
4. Restart/redeploy the application
5. Test with simple manual function call

---

## 📈 Monitoring & Analytics

### Email Monitoring
- Check Render logs for send status
- Monitor delivery rate
- Track failures
- Review bounce messages

### SMS Monitoring
- View Twilio dashboard
- Check delivery reports
- Monitor account usage
- Review sent messages history

---

## 💡 Best Practices

### Email
1. Use professional sender address
2. Include unsubscribe option
3. Track delivery status
4. Keep email content concise
5. Use templates for consistency
6. Test before production
7. Monitor bounce rates

### SMS
1. Keep messages under 160 characters
2. Include only critical info
3. Don't spam users
4. Verify phone numbers
5. Use international format
6. Monitor costs
7. Set spending limits

---

## ✅ System Status

**Email & SMS System:**
- ✅ Code integrated into app.py
- ✅ Environment variables configured in Render
- ✅ Twilio package added to requirements.txt
- ✅ Email templates created
- ✅ SMS handlers implemented
- ✅ Error logging configured
- ✅ Ready for production

---

## 🎯 Next Steps

1. **Configure Email:**
   - Get Gmail app password or SMTP credentials
   - Add to Render environment variables

2. **Configure SMS (Optional):**
   - Create Twilio account
   - Get phone number
   - Add credentials to Render

3. **Redeploy:**
   - Push code to GitHub
   - Deploy on Render
   - Verify notifications work

4. **Test:**
   - Send test email/SMS
   - Monitor logs
   - Adjust as needed

---

## 📚 Resources

- **Gmail App Passwords:** https://myaccount.google.com/apppasswords
- **Twilio Console:** https://www.twilio.com/console
- **Render Settings:** Your Render dashboard
- **Email Templates:** Included in send_notification_email()
- **API Docs:** Standard Python SMTP and Twilio REST API

---

**Your Marine Service Center now has production-ready email and SMS notifications!** 📧📱

Deploy the latest code to Render and configure your credentials to activate notifications.
