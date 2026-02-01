# Emergency Drill Report System - Complete Documentation

## Overview

A comprehensive emergency drill reporting system integrated into the International Reports section. Supports all SOLAS, MARPOL, and ISPS Code required drills with flexible templates for different emergency scenarios.

**Commit:** `ea1d5dd` - Feature: Add comprehensive emergency drill report system

---

## Features

### 1. **Supported Drill Types**

#### General Drill (Base Template)
- Vessel identification
- Drill date, time, location
- Personnel participation tracking
- Weather conditions
- Drill scenario description
- Equipment used checklist
- Performance evaluation
- Deficiency identification
- Corrective action planning

#### Fire Drill (SOLAS II-2)
- Fire location selection (Engine Room, Galley, Accommodation, Cargo Hold, Other)
- Alarm activation tracking
- Response time measurement
- Team performance metrics:
  - Muster correctness
  - Fire pump operation
  - Breathing apparatus usage
  - Boundary cooling procedures

#### Abandon Ship Drill (SOLAS III)
- Lifeboat/Liferaft selection (Port, Starboard, Free-Fall, Inflatable)
- Muster time tracking
- Boat lowering verification
- Crew preparedness assessment:
  - Life jacket compliance
  - Roll call completion
  - Emergency rations check

#### Man Overboard (MOB) Drill
- Side of incident (Port/Starboard)
- MOB equipment tracking
- Recovery method selection (Rescue Boat, Ladder, Crane, Maneuver Only)
- Navigation procedures:
  - Williamson Turn
  - Anderson Turn
  - GPS Mark recording

#### Oil Spill / Pollution Drill (MARPOL)
- Spill type (Fuel Oil, Lube Oil, Sewage, Chemical)
- Location tracking (Engine Room, Deck, Bunker Station)
- Response actions:
  - Spill containment
  - SOPEP procedure compliance
  - Scupper plugging

#### Emergency Steering Drill (SOLAS V)
- Main steering failure simulation
- Bridge-to-steering flat communication testing
- Response time measurement
- Result assessment (Satisfactory/Unsatisfactory)

#### Security Drill (ISPS Code)
- Security level (1, 2, or 3)
- Threat scenario (Unauthorized Access, Bomb Threat, Piracy, Stowaway)
- Response actions:
  - Access point securing
  - SSP procedure compliance
  - Communication logging
- SSO remarks

#### Engine Room & Other Drills
- Customizable "Other" drill type
- Flexible scenario description

---

## Database Schema

### Table: `drill_reports`

```sql
CREATE TABLE IF NOT EXISTS drill_reports (
    -- Primary Keys & Identifiers
    report_id TEXT PRIMARY KEY,
    officer_id TEXT,
    
    -- Vessel Information
    vessel_name TEXT NOT NULL,
    imo_number TEXT,
    flag_state TEXT,
    port_position TEXT,
    
    -- Drill Scheduling
    report_date DATE NOT NULL,
    time_start TIME,
    time_end TIME,
    
    -- Drill Type & Scenario
    drill_type TEXT NOT NULL,
    other_drill_type TEXT,
    drill_scenario TEXT,
    
    -- Weather Conditions
    weather_wind TEXT,
    weather_sea_state TEXT,
    weather_visibility TEXT,
    
    -- Personnel Data
    total_crew_onboard INTEGER,
    crew_participated INTEGER,
    officer_name TEXT NOT NULL,
    officer_rank TEXT,
    
    -- General Drill Information
    actions_taken TEXT,
    equipment_used TEXT,
    performance_rating TEXT,
    deficiencies_observed TEXT,
    corrective_actions TEXT,
    target_completion_date DATE,
    master_remarks TEXT,
    
    -- Fire Drill Specific
    fire_location TEXT,
    alarm_activated TEXT,
    response_time_minutes INTEGER,
    muster_correct TEXT,
    fire_pump_started TEXT,
    ba_correctly_used TEXT,
    boundary_cooling TEXT,
    
    -- Abandon Ship Specific
    lifeboat_type TEXT,
    muster_time_minutes INTEGER,
    boat_lowered TEXT,
    life_jackets_worn TEXT,
    roll_call_completed TEXT,
    emergency_rations_checked TEXT,
    
    -- MOB Specific
    mob_side TEXT,
    mob_equipment_used TEXT,
    recovery_method TEXT,
    williamson_turn TEXT,
    anderson_turn TEXT,
    gps_mark_activated TEXT,
    
    -- Oil Spill Specific
    spill_type TEXT,
    spill_location TEXT,
    spill_contained TEXT,
    sopep_followed TEXT,
    scuppers_plugged TEXT,
    
    -- Emergency Steering Specific
    main_steering_failure_simulated TEXT,
    bridge_steering_communication TEXT,
    steering_response_time_seconds INTEGER,
    emergency_steering_result TEXT,
    
    -- Security Drill Specific
    security_level TEXT,
    security_scenario TEXT,
    access_points_secured TEXT,
    ssp_followed TEXT,
    communication_logged TEXT,
    sso_remarks TEXT,
    
    -- Audit & Signatures
    signature_data TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (officer_id) REFERENCES users (user_id)
)
```

---

## User Interface

### 1. Drill Report Form (`/drill-report`)

**Features:**
- Progressive form with collapsible sections
- Dynamic drill type selection with multi-select checkboxes
- Context-sensitive sections that appear based on selected drill type
- Digital signature pad (canvas-based using Signature Pad library)
- Equipment and action checklists
- Real-time field validation
- Responsive mobile-friendly design

**Main Sections:**
1. Vessel Information
2. Drill Details
3. Weather Conditions
4. Personnel Involved
5. Drill Scenario & Actions
6. Performance Evaluation
7. Drill-Type Specific Sections (Fire, Abandon Ship, MOB, Oil Spill, Steering, Security)
8. Master Remarks & Signatures

### 2. Drill Reports Archive (`/drill-reports`)

**Features:**
- Dashboard with 3-card statistics:
  - Total drills conducted
  - Drills this month
  - Reports with identified deficiencies
- Advanced filtering system:
  - Filter by drill type
  - Filter by performance rating
  - Date range filtering
- Responsive data table with:
  - Report date
  - Drill type badge
  - Vessel name
  - Performance rating (color-coded)
  - Crew participation ratio
  - Action buttons
- Detail viewer modal
- PDF/text export functionality
- Quick view of key information

**Performance Rating Colors:**
- Excellent → Green (success)
- Satisfactory → Blue (info)
- Needs Improvement → Orange (warning)
- N/A → Gray (secondary)

---

## API Endpoints

### Create Drill Report
**POST** `/api/drill-report`

**Authentication:** Required (Login)  
**Authorization:** chief_engineer, captain

**Request Body:**
```json
{
    "vessel_name": "MSC Gulsun",
    "imo_number": "IMO1234567",
    "flag_state": "Panama",
    "port_position": "Port of Singapore",
    "report_date": "2026-02-01",
    "time_start": "10:00",
    "time_end": "11:30",
    "drill_type": "Fire",
    "weather_wind": "15 knots NW",
    "weather_sea_state": "Moderate (2-3m)",
    "weather_visibility": "5 NM",
    "total_crew_onboard": 25,
    "crew_participated": 24,
    "officer_name": "Captain John Smith",
    "officer_rank": "Captain",
    "drill_scenario": "Simulated fire in engine room",
    "actions_taken": "Activated alarm, assembled crew, deployed fire team...",
    "equipment_used": "Fire Pumps, Breathing Apparatus, Fire Hoses",
    "performance_rating": "Excellent",
    "deficiencies_observed": "None",
    "corrective_actions": "None required",
    "target_completion_date": null,
    "master_remarks": "Well-executed drill.",
    "fire_location": "Engine Room",
    "alarm_activated": "Yes",
    "response_time_minutes": 5,
    "muster_correct": "Yes",
    "fire_pump_started": "Yes",
    "ba_correctly_used": "Yes",
    "boundary_cooling": "Yes",
    "signature_data": "data:image/png;base64,...",
    "notes": "No issues noted."
}
```

**Response:**
```json
{
    "success": true,
    "report_id": "DRL00001",
    "message": "Drill report submitted"
}
```

---

### Get All Drill Reports
**GET** `/api/drill-reports`

**Authentication:** Required (Login)  
**Authorization:** chief_engineer, captain, harbour_master

**Response:**
```json
{
    "success": true,
    "reports": [
        {
            "report_id": "DRL00001",
            "vessel_name": "MSC Gulsun",
            "imo_number": "IMO1234567",
            "report_date": "2026-02-01",
            "drill_type": "Fire",
            "performance_rating": "Excellent",
            "total_crew_onboard": 25,
            "crew_participated": 24,
            "officer_name": "Captain John Smith",
            "created_at": "2026-02-01T10:30:00",
            "..."
        }
    ]
}
```

---

## Navigation Integration

### Menu Structure

**International Reports** (Expanded Menu)
- Bilge Report / View Logs
- Fuel Report / View Fuel
- Sewage Report / View Sewage
- Logbook / View Logbook
- Emission Report / View Emissions
- **→ Drill Report** *(New)*
- **→ View Drills** *(New)*

**Access Requirements:**
- Drill Report form: chief_engineer, captain
- Drill Reports archive: chief_engineer, captain, harbour_master
- Menu visibility: All roles with international reports access

---

## Compliance & Standards

### SOLAS (Safety of Life at Sea) Compliance
- **SOLAS II-2:** Fire Drill Report (fire detection, suppression, team procedures)
- **SOLAS III:** Abandon Ship Drill (muster procedures, lifeboat operations)
- **SOLAS V:** Emergency Steering Drill (steering communication, response time)

### MARPOL (Marine Pollution) Compliance
- **Oil Spill Drill:** Pollution response procedures (SOPEP, containment, scupper management)

### ISPS Code (Maritime Security)
- **Security Drill:** Threat response procedures (access control, SSP compliance, communication)

### IMO Requirements
- Monthly minimum drill frequency tracking
- Digital signature authority
- Master attestation capability
- Deficiency and corrective action documentation
- Performance rating and audit trail

---

## Features in Detail

### 1. Digital Signature Pad
- Canvas-based signature capture using Signature Pad library
- Supports drawing and clearing signatures
- Saved as PNG data URI in database
- Clear button for signature correction

### 2. Dynamic Form Sections
- Fire Drill section appears when "Fire" is selected
- Abandon Ship section appears when "Abandon Ship" is selected
- MOB section appears when "Man Overboard" is selected
- And so on for all drill types
- Sections collapse/hide when drill type is deselected

### 3. Equipment Tracking
- Checkbox list for equipment used:
  - Fire Pumps
  - Breathing Apparatus
  - Lifeboats / Liferafts
  - Emergency Generator
  - Emergency Steering System
  - Spill Response Equipment

### 4. Performance Metrics
- Overall Performance Rating (3-level scale)
- Crew participation percentage
- Response time measurements (where applicable)
- Specific performance items (muster, BA usage, etc.)

### 5. Audit Trail
- Created timestamp
- Updated timestamp
- Officer identification
- Master remarks
- Signature data
- Corrective action tracking

### 6. Reporting & Export
- View drill reports by date range
- Filter by drill type
- Filter by performance rating
- PDF export of reports
- Text export capability
- Modal detail viewer

---

## User Workflow

### Creating a Drill Report

1. Navigate to **Int'l Reports** → **Drill Report**
2. Enter vessel information
3. Select drill type(s) and date/time
4. Fill weather conditions
5. Enter personnel information
6. Describe drill scenario
7. Record actions taken
8. Select equipment used
9. Evaluate performance
10. Complete drill-type specific sections
11. Enter master remarks
12. Sign on signature pad
13. Submit report
14. System generates unique report ID (DRL00001, etc.)

### Viewing & Managing Drills

1. Navigate to **Int'l Reports** → **View Drills**
2. Browse all drill reports with statistics
3. Filter by:
   - Drill type
   - Performance rating
   - Date range
4. Click **View** for detail modal
5. Click **PDF** for export
6. Track deficiencies and corrective actions

---

## Technical Implementation

### Frontend Technologies
- HTML5 Canvas for signature pad
- Bootstrap 5 for responsive design
- JavaScript for form validation and API calls
- Signature Pad library (v4.1.7)

### Backend Technologies
- Flask routing and middleware
- SQLite database persistence
- JSON API responses
- Role-based access control (RBAC)

### Data Validation
- Required field validation (HTML5 + JS)
- Date range validation
- Crew number validation (participated ≤ onboard)
- Signature requirement on submission
- Drill type selection requirement

---

## Customization & Future Enhancements

### Potential Additions
1. **Drill Template Library** - Pre-filled scenarios for common drills
2. **Crew Assignment** - Link crew members to specific drill roles
3. **Performance Trends** - Analytics dashboard showing drill improvements over time
4. **Automated Reporting** - Monthly/annual audit reports
5. **Integrated Deficiency Tracker** - Link drills to maintenance requests
6. **Photo Attachments** - Add images of equipment used, team setup
7. **Video Evidence** - Attach drill video recordings
8. **Real-Time Notifications** - Alert crew of scheduled drills
9. **Multi-Language Support** - Localize for different crew nationalities
10. **Integration with SMS/Email** - Send drill schedules and reminders

---

## Troubleshooting

### Drill Report Not Submitting
- Check that all required fields are filled
- Ensure signature is drawn on the signature pad
- Verify drill type is selected
- Check browser console for JavaScript errors

### Filter Results Empty
- Adjust date range filter
- Clear all filters to see all records
- Ensure drill reports exist in database

### API Errors
- Verify user has proper role authorization
- Check database connection
- Review server logs for detailed error messages

---

## Summary

The Emergency Drill Report System provides a complete SOLAS, MARPOL, and ISPS Code-compliant solution for documenting maritime emergency drills. With support for 8 different drill types, dynamic form sections, digital signatures, and comprehensive reporting capabilities, it ensures regulatory compliance and operational readiness tracking across all emergency scenarios.

**Key Components:**
- ✅ Database table with 65+ fields for comprehensive drill data
- ✅ Dynamic form with 8 drill-type specific sections
- ✅ Digital signature pad for officer attestation
- ✅ Advanced filtering and reporting dashboard
- ✅ Full audit trail and compliance documentation
- ✅ Mobile-responsive design
- ✅ RESTful API endpoints
- ✅ Navigation menu integration

**Git Commit:** `ea1d5dd`
