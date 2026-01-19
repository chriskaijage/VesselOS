# 🚢 Marine Service Center - Quick Start Card

## 🎯 IMMEDIATE ACTIONS (Do These Now)

### 1. REDEPLOY ON RENDER ⚡
```
Go to: render.com/dashboard
→ Click "marine-service-center" service
→ Click "Manual Deploy" 
→ Click "Deploy latest commit"
→ Wait 2-3 minutes
```

### 2. INITIALIZE DATABASE 🗄️
After deployment completes, visit:
```
https://your-render-app-url/init
```

You should see:
```json
{
  "status": "success",
  "message": "Database initialized successfully",
  "demo_accounts": [...]
}
```

### 3. LOGIN & TEST ✅
Visit your Render app URL and use any demo account:

```
🔐 PORT ENGINEER (Admin)
Email: port_engineer@marine.com
Pass: Admin@2025

👤 QUALITY OFFICER
Email: quality@marine.com
Pass: Quality@2025

👔 HARBOUR MASTER
Email: harbour_master@marine.com
Pass: Maintenance@2025
```

---

## 🆘 IF SOMETHING GOES WRONG

### Can't see login page?
→ Check if Render deployment finished (green checkmark)
→ Wait 30 seconds and refresh

### Login says "invalid credentials"?
→ Copy/paste credentials exactly (check caps lock)
→ Visit `/init` route first to initialize
→ Clear browser cache

### Getting database errors?
→ Visit `/init` route: `https://your-app-url/init`
→ Check Render logs for detailed error messages

---

## ✨ WHAT'S WORKING NOW

✅ Login with demo accounts  
✅ User registration (new users need approval)  
✅ Full dashboard access  
✅ Emergency request system  
✅ Maintenance requests  
✅ International maritime reports  
✅ Messaging between users  
✅ Digital signatures  
✅ File uploads  
✅ Role-based permissions  

---

## 🔗 USEFUL LINKS

- **Your App**: `https://marine-service-center-xxxxx.onrender.com`
- **Render Dashboard**: `https://render.com/dashboard`
- **GitHub Repo**: `https://github.com/chriskaijage/marine-service-center`
- **Full Guide**: Check `SYSTEM_READY.md` file in repo

---

## 💡 TIP: Test Each Account

**As Port Engineer:**
- View all users
- Approve new registrations
- Manage emergency requests
- Access full admin panel

**As Quality Officer:**
- Create reports (bilge, fuel, sewage)
- Submit service evaluations
- View your reports
- Receive messages

**As Harbour Master:**
- View maintenance requests
- Manage port operations
- Coordinate resources
- Send messages

---

**READY? Start with Step 1 above! 🚀**
