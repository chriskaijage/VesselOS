# Button Functions Audit - All onclick Handlers

## Buttons Found and Their Functions

### Reports Page
- `exportAllReports()` - Export all reports
- `loadReports()` - Load reports list
- `clearAllReports()` - Clear all reports

### Report Pages (bilge_report, fuel_report, emission_report, sewage_report, logbook)
- `clearSignature()` - Clear signature (used in multiple pages)

### Waste Transfer Note
- `clearPrfSignature()` - Clear PRF signature
- `clearShipSignature()` - Clear ship signature

### View Request Page
- `assignToMe()` - Assign request to current user
- `updateStatus()` - Update request status
- `addNotes()` - Add notes to request
- `startService()` - Start service on request
- `declareEmergency()` - Declare emergency
- `loadWorkflowHistory()` - Load workflow history
- `updateRequestStatus()` - Update request status (variant)
- `evaluateService()` - Evaluate service
- `printRequest()` - Print request
- `exportRequest()` - Export request
- `shareRequest()` - Share request
- `cloneRequest()` - Clone request
- `saveStatusUpdate()` - Save status update
- `viewFullEvaluation()` - View full evaluation

### Quality Officer Page
- `showAccessRequestModal()` - Show access request modal
- `loadMyEvaluations()` - Load my evaluations
- `submitAccessRequest()` - Submit access request

### Port Engineer Dashboard
- `openComposeTab()` - Open compose message tab (messaging - ALREADY FIXED)
- `sendBulkNotifications()` - Send bulk notifications
- `generateSystemReport()` - Generate system report
- `toggleMessagingPanel()` - Toggle messaging panel (ALREADY FIXED)
- `generateOneTimePassword()` - Generate OTP
- `updateQualityOfficerAccess()` - Update quality officer access
- `createQualityOfficer()` - Create quality officer
- `sendNotification()` - Send notification

### Monitor Page
- `loadLiveUpdates()` - Load live updates

### Maintenance Request Page
- `printRequest()` - Print request
- `newRequest()` - Create new request
- `callEmergency()` - Call emergency

### Profile Page
- `printProfile()` - Print profile
- `removeProfilePic()` - Remove profile picture
- `showSignatureModal()` - Show signature modal
- `resetFormChanges()` - Reset form changes
- `showSendMessageModal()` - Show send message modal
- `showInbox()` - Show inbox
- `showSentMessagesModal()` - Show sent messages modal

## Functions Already Fixed
- ✅ `toggleMessagingPanel()` - Already in global scope
- ✅ `openComposeTab()` - Already in global scope (via port_engineer_dashboard)
- ✅ `toggleSidebar()` - Already added to global scope
- ✅ `setTheme()` - Already added to global scope

## Functions Needing Global Scope Fix
Total: 38+ unique functions need to be:
1. Added as global stubs at script start
2. Exposed to window object on DOMContentLoaded
3. Updated onclick handlers to use `window.functionName()` pattern

## Status
- Reports: Need fixes
- Report Pages: Need fixes
- View Request: Need fixes (major - 14+ buttons)
- Quality Officer: Need fixes
- Port Engineer Dashboard: Partial fix (openComposeTab, toggleMessagingPanel already fixed)
- Monitor: Need fixes
- Maintenance Request: Need fixes
- Profile: Need fixes
