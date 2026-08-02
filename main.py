import os
import uuid
import io
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import math

from database import get_db, Student, Attendance, ClassroomSession
from auth import verify_google_token

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = FastAPI(title="Anti-Proxy Attendance System")

# Configure CORS middleware
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure the static directory exists
os.makedirs("static", exist_ok=True)

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Whitelisted Class Representative (CR) Google accounts
CR_EMAILS = [e.strip() for e in os.getenv("CR_EMAILS", "").split(",") if e.strip()]

# Maximum allowed distance (radius in meters) for classroom geofencing verification
GEOFENCE_RADIUS_METERS = 100.0

# Subject list defined by the user
SUBJECTS = [
    "IEE301 Electromagnetic Field Theory",
    "IEE302 Electrical Measurements & Instrumentation",
    "IEE303 Basic Signals & Systems",
    "INC305 Research Methodology",
    "IEE354 Mini Project-I or Internship Assessment"
]

class AttendanceRequest(BaseModel):
    token: str
    google_token: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class StartSessionRequest(BaseModel):
    subject: str
    session_date: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class VerifyCrRequest(BaseModel):
    google_token: str

def get_local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not need to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Haversine formula to compute distance in meters between coordinates
    R = 6371000.0  # Earth's radius in meters
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

try:
    IST_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    IST_TZ = timezone(timedelta(hours=5, minutes=30))

def to_local_time(utc_dt: datetime) -> datetime:
    # Convert UTC datetime to IST (Asia/Kolkata) local timezone
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(IST_TZ).replace(tzinfo=None)

def verify_cr_token(authorization: str = Header(None)) -> str:
    google_token = None
    if authorization:
        token_type, _, val = authorization.partition(" ")
        if token_type.lower() == "bearer" and val:
            google_token = val
        
    if not google_token:
        raise HTTPException(status_code=401, detail="Authentication token required")
        
    try:
        email = verify_google_token(google_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google Token: {str(e)}")
        
    if email not in CR_EMAILS:
        raise HTTPException(status_code=403, detail="Unauthorized: You are not whitelisted as a Class Representative.")
    return email

def generate_pdf_report(date_str: str, subject_str: str, students_list: list, only_present: bool):
    buffer = io.BytesIO()
    
    # Page setup
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    primary_color = colors.HexColor("#2563eb") # Sleek modern blue
    text_color = colors.HexColor("#0f172a") # Slate 900
    border_color = colors.HexColor("#cbd5e1") # Slate 300
    
    # Custom Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=primary_color,
        alignment=1, # Center
        spaceAfter=12
    )
    
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        alignment=1, # Center
        spaceAfter=15
    )
    
    col_header_style = ParagraphStyle(
        'ColHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.whitesmoke
    )
    
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=text_color
    )
    
    cell_bold_style = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=text_color
    )
    
    # Title & Metadata
    story.append(Paragraph("ATTENDANCE REPORT", title_style))
    
    total_students = len(students_list)
    present_students = sum(1 for s in students_list if s["status"] == "Present")
    absent_students = total_students - present_students
    attendance_pct = (present_students / total_students * 100) if total_students > 0 else 0
    
    meta_text = (
        f"<b>Subject:</b> {subject_str}<br/>"
        f"<b>Date:</b> {date_str} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Total Present:</b> {present_students}/{total_students} ({attendance_pct:.1f}%)"
    )
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 10))
    
    # Filter list based on only_present flag
    if only_present:
        display_list = [s for s in students_list if s["status"] == "Present"]
    else:
        display_list = students_list
        
    # Table data construction
    if only_present:
        table_data = [[
            Paragraph("S.No.", col_header_style), 
            Paragraph("Roll No.", col_header_style), 
            Paragraph("Student Name", col_header_style)
        ]]
        
        for idx, student in enumerate(display_list, start=1):
            table_data.append([
                Paragraph(str(idx), cell_style),
                Paragraph(student["roll_number_last2"], cell_bold_style),
                Paragraph(student["name"], cell_style)
            ])
            
        t = Table(table_data, colWidths=[60, 100, 380])
    else:
        table_data = [[
            Paragraph("S.No.", col_header_style), 
            Paragraph("Roll No.", col_header_style), 
            Paragraph("Student Name", col_header_style),
            Paragraph("Status", col_header_style)
        ]]
        
        for idx, student in enumerate(display_list, start=1):
            status_color = "#10b981" if student["status"] == "Present" else "#ef4444"
            status_html = f"<font color='{status_color}'><b>{student['status']}</b></font>"
            table_data.append([
                Paragraph(str(idx), cell_style),
                Paragraph(student["roll_number_last2"], cell_bold_style),
                Paragraph(student["name"], cell_style),
                Paragraph(status_html, cell_bold_style)
            ])
            
        t = Table(table_data, colWidths=[50, 80, 310, 100])
        
    # Styles for table
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
        ('TOPPADDING', (0,1), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
    ])
    t.setStyle(t_style)
    story.append(t)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_student_receipt_pdf(receipt_data: dict):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()
    
    primary_color = colors.HexColor("#4f46e5")
    accent_green = colors.HexColor("#059669")
    text_color = colors.HexColor("#0f172a")
    sub_color = colors.HexColor("#64748b")
    bg_light = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#cbd5e1")
    
    header_style = ParagraphStyle(
        'InstHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=primary_color,
        alignment=1,
        spaceAfter=2
    )
    
    sub_header_style = ParagraphStyle(
        'InstSubHeader',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=sub_color,
        alignment=1,
        spaceAfter=15
    )
    
    title_style = ParagraphStyle(
        'ReceiptTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=text_color,
        alignment=1,
        spaceAfter=8
    )
    
    ref_style = ParagraphStyle(
        'ReceiptRef',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=sub_color,
        alignment=1,
        spaceAfter=15
    )

    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    
    val_style = ParagraphStyle(
        'ValStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=text_color
    )

    roll2_style = ParagraphStyle(
        'Roll2Style',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        textColor=primary_color
    )
    
    status_style = ParagraphStyle(
        'StatusStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=accent_green
    )

    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=sub_color,
        alignment=1,
        spaceBefore=20
    )

    story.append(Paragraph("INSTITUTE OF ENGINEERING & TECHNOLOGY, LUCKNOW", header_style))
    story.append(Paragraph("Department of Electrical Engineering &bull; Class of 2029", sub_header_style))
    story.append(Paragraph("DIGITAL ATTENDANCE RECEIPT", title_style))
    story.append(Paragraph(f"Receipt Ref: {receipt_data.get('receipt_id', 'N/A')}", ref_style))
    story.append(Spacer(1, 10))

    table_data = [
        [Paragraph("Student Name", label_style), Paragraph(receipt_data.get("name", "N/A"), val_style)],
        [Paragraph("Full Roll Number", label_style), Paragraph(receipt_data.get("roll_number", "N/A"), val_style)],
        [Paragraph("Roll Number (2 Digits)", label_style), Paragraph(receipt_data.get("roll_number_last2", "N/A"), roll2_style)],
        [Paragraph("Email Address", label_style), Paragraph(receipt_data.get("email", "N/A"), val_style)],
        [Paragraph("Subject", label_style), Paragraph(receipt_data.get("subject", "N/A"), val_style)],
        [Paragraph("Date", label_style), Paragraph(receipt_data.get("session_date", receipt_data.get("date", "N/A")), val_style)],
        [Paragraph("Verification Status", label_style), Paragraph("&check; PRESENT & VERIFIED", status_style)]
    ]

    t = Table(table_data, colWidths=[160, 360])
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (0,-1), bg_light),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
    ])
    t.setStyle(t_style)
    story.append(t)
    story.append(Spacer(1, 20))
    story.append(Paragraph("This attendance record was authenticated via College Google Account Verification.", footer_style))
    story.append(Paragraph("System Generated Document &bull; No physical signature required.", footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


@app.on_event("startup")
def startup_event():
    from database import Base, engine
    Base.metadata.create_all(bind=engine)
    
    local_ip = get_local_ip()
    print("\n" + "="*70)
    print("  ANTI-PROXY ATTENDANCE SYSTEM STARTED")
    print("="*70)
    print(f"  Local Host URL:  http://localhost:8000/static/dashboard.html")
    print(f"  CR Portal URL:   http://localhost:8000/cr-portal")
    print(f"  Mobile Phone URL: http://{local_ip}:8000/static/dashboard.html")
    print("="*70)
    print("  IMPORTANT: Ensure your mobile phone is connected to the SAME Wi-Fi")
    print("  network, and run Uvicorn with: --host 0.0.0.0")
    print("="*70 + "\n")

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/dashboard.html")

@app.get("/subjects")
def get_subjects():
    return {"subjects": SUBJECTS}

@app.post("/verify-cr")
def verify_cr_endpoint(payload: VerifyCrRequest):
    try:
        email = verify_google_token(payload.google_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
        
    if email not in CR_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You are not registered as a Class Representative."
        )
    return {"status": "success", "email": email}

@app.post("/start-session")
def start_session(payload: StartSessionRequest, authorization: str = Header(None), db: Session = Depends(get_db)):
    verify_cr_token(authorization)
    
    if payload.subject not in SUBJECTS:
        raise HTTPException(status_code=400, detail="Invalid subject name.")
        
    # Deactivate all existing active sessions
    db.query(ClassroomSession).filter(ClassroomSession.is_active == 1).update({"is_active": 0})
    
    # Start the new session
    now = datetime.utcnow()
    new_session = ClassroomSession(
        subject=payload.subject,
        session_date=payload.session_date,
        is_active=1,
        started_at=now,
        current_token=str(uuid.uuid4()),
        token_expiry=now + timedelta(seconds=15),
        latitude=payload.latitude,
        longitude=payload.longitude
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return {
        "status": "success",
        "message": f"Attendance session started for {payload.subject}",
        "subject": new_session.subject,
        "token": new_session.current_token
    }

@app.post("/stop-session")
def stop_session(authorization: str = Header(None), db: Session = Depends(get_db)):
    verify_cr_token(authorization)
    
    db.query(ClassroomSession).filter(ClassroomSession.is_active == 1).update({"is_active": 0})
    db.commit()
    return {"status": "success", "message": "Attendance session stopped successfully"}

def rotate_session_token(session: ClassroomSession, db: Session):
    now = datetime.utcnow()
    if now >= session.token_expiry:
        old_token = session.current_token
        prev_list = []
        if session.previous_tokens:
            prev_list = session.previous_tokens.split(",")
        prev_list.insert(0, old_token)
        # Keep up to 3 older tokens (valid for 60 seconds total: 15s display + 45s buffer)
        session.previous_tokens = ",".join(prev_list[:3])
        
        session.current_token = str(uuid.uuid4())
        session.token_expiry = now + timedelta(seconds=15)
        db.commit()
        db.refresh(session)

@app.get("/active-session")
def get_active_session(db: Session = Depends(get_db)):
    session = db.query(ClassroomSession).filter(ClassroomSession.is_active == 1).first()
    if not session:
        return {"is_active": False}
        
    rotate_session_token(session, db)
    
    now = datetime.utcnow()
    remaining = int((session.token_expiry - now).total_seconds())
    return {
        "is_active": True,
        "subject": session.subject,
        "token": session.current_token,
        "remaining_seconds": max(0, remaining),
        "server_ip": get_local_ip()
    }

@app.get("/generate-qr-token")
def generate_qr_token(request: Request, authorization: str = Header(None), db: Session = Depends(get_db)):
    verify_cr_token(authorization)
    # Legacy wrapper for backward compatibility with automated tests
    session = db.query(ClassroomSession).filter(ClassroomSession.is_active == 1).first()
    now = datetime.utcnow()
    if not session:
        # Create a default active session for testing
        today_local_str = to_local_time(now).strftime("%Y-%m-%d")
        session = ClassroomSession(
            subject="IEE301 Electromagnetic Field Theory",
            session_date=today_local_str,
            is_active=1,
            started_at=now,
            current_token=str(uuid.uuid4()),
            token_expiry=now + timedelta(seconds=15)
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        rotate_session_token(session, db)
            
    base_url = str(request.base_url).rstrip("/")
    mark_url = f"{base_url}/mark-attendance?token={session.current_token}"
    return {
        "token": session.current_token,
        "expiry_time": session.token_expiry.isoformat() + "Z",
        "url": mark_url,
        "server_ip": get_local_ip()
    }

@app.get("/mark-attendance")
def serve_student_page(token: str = None):
    if not token:
        raise HTTPException(status_code=400, detail="Token parameter is required")
        
    student_html_path = os.path.join("static", "student.html")
    if not os.path.exists(student_html_path):
        raise HTTPException(status_code=500, detail="Student interface page not found on server")
        
    with open(student_html_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    content = content.replace("{{GOOGLE_CLIENT_ID}}", google_client_id)
    return HTMLResponse(content)

@app.get("/cr-portal")
def serve_cr_page(request: Request):
    cr_html_path = os.path.join("static", "cr.html")
    if not os.path.exists(cr_html_path):
        raise HTTPException(status_code=400, detail="CR Portal page not found on server (make sure static/cr.html exists)")
        
    with open(cr_html_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    content = content.replace("{{GOOGLE_CLIENT_ID}}", google_client_id)
    return HTMLResponse(content)

@app.post("/mark-attendance")
def mark_attendance(payload: AttendanceRequest, db: Session = Depends(get_db)):
    if not payload.google_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google Authentication token is required"
        )
        
    try:
        email = verify_google_token(payload.google_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
        
    student = db.query(Student).filter(Student.email == email).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{email}' is not in the student whitelist."
        )
        
    session = db.query(ClassroomSession).filter(ClassroomSession.is_active == 1).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active attendance session found."
        )
        
    # Build a list of valid tokens: current_token + older tokens in sliding window
    valid_tokens = [session.current_token]
    if session.previous_tokens:
        valid_tokens.extend(session.previous_tokens.split(","))
        
    if payload.token not in valid_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR token. The QR code has updated. Please scan the latest code."
        )
        
    # Geofencing Validation: verify distance between student and CR if session has location coordinates
    if session.latitude is not None and session.longitude is not None:
        if payload.latitude is None or payload.longitude is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Location access is required to verify physical presence in the classroom."
            )
        distance = calculate_distance(
            session.latitude, session.longitude,
            payload.latitude, payload.longitude
        )
        # Enforce 100 meters threshold
        if distance > GEOFENCE_RADIUS_METERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Attendance rejected: Location verification failed. You must be physically present in the classroom (within {int(GEOFENCE_RADIUS_METERS)}m)."
            )
        
    now = datetime.utcnow()
        
    # Construct timestamp from session_date and current local time, then convert back to UTC
    try:
        session_date_obj = datetime.strptime(session.session_date, "%Y-%m-%d").date()
    except ValueError:
        session_date_obj = to_local_time(now).date()
        
    local_now = to_local_time(now)
    local_attendance_dt = datetime.combine(session_date_obj, local_now.time())
    
    # Convert local back to UTC
    attendance_timestamp = local_attendance_dt.replace(tzinfo=IST_TZ).astimezone(timezone.utc).replace(tzinfo=None)
    
    # Check if attendance already marked for this subject on this session_date
    student_attendances = db.query(Attendance).filter(
        Attendance.student_id == student.id,
        Attendance.subject == session.subject
    ).all()
    
    already_marked = False
    for att in student_attendances:
        if to_local_time(att.timestamp).date() == session_date_obj:
            already_marked = True
            break
            
    roll_last2 = student.roll_number[-2:] if len(student.roll_number) >= 2 else student.roll_number
    date_clean = session.session_date.replace("-", "")
    receipt_id = f"REC-{date_clean}-{roll_last2}-{student.id:03d}"
    formatted_ts = local_attendance_dt.strftime("%Y-%m-%d %I:%M %p")

    if already_marked:
        return {
            "status": "already_marked",
            "message": f"Attendance already marked for student {student.name} (Roll No: {student.roll_number}).",
            "name": student.name,
            "roll_number": student.roll_number,
            "roll_number_last2": roll_last2,
            "email": student.email,
            "subject": session.subject,
            "session_date": session.session_date,
            "timestamp": formatted_ts,
            "receipt_id": receipt_id
        }
        
    new_attendance = Attendance(
        student_id=student.id,
        timestamp=attendance_timestamp,
        subject=session.subject
    )
    db.add(new_attendance)
    db.commit()
    
    return {
        "status": "success",
        "message": "Attendance successfully recorded!",
        "name": student.name,
        "roll_number": student.roll_number,
        "roll_number_last2": roll_last2,
        "email": student.email,
        "subject": session.subject,
        "session_date": session.session_date,
        "timestamp": formatted_ts,
        "receipt_id": receipt_id
    }

@app.get("/attendance-report")
def get_attendance_report(date: str, subject: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    verify_cr_token(authorization)
    
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
    students = db.query(Student).order_by(Student.roll_number).all()
    attendances = db.query(Attendance).filter(Attendance.subject == subject).all()
    
    present_student_ids = set()
    for att in attendances:
        local_dt = to_local_time(att.timestamp)
        if local_dt.date() == target_date:
            present_student_ids.add(att.student_id)
            
    report = []
    for idx, s in enumerate(students, start=1):
        status_str = "Present" if s.id in present_student_ids else "Absent"
        report.append({
            "s_no": idx,
            "roll_number": s.roll_number,
            "roll_number_last2": s.roll_number[-2:],
            "name": s.name,
            "email": s.email,
            "status": status_str
        })
    return report

@app.get("/download-pdf")
def download_pdf(date: str, subject: str, only_present: bool = True, authorization: str = Header(None), db: Session = Depends(get_db)):
    verify_cr_token(authorization)
    
    report = get_attendance_report(date, subject, authorization, db)
    pdf_buffer = generate_pdf_report(date, subject, report, only_present)
    
    safe_subject = "".join([c if c.isalnum() else "_" for c in subject])
    filename = f"attendance_{safe_subject}_{date}.pdf"
    
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)

@app.get("/download-student-receipt-pdf")
def download_student_receipt_pdf(authorization: str = Header(None), db: Session = Depends(get_db)):
    google_token = None
    if authorization:
        token_type, _, val = authorization.partition(" ")
        if token_type.lower() == "bearer" and val:
            google_token = val

    if not google_token:
        raise HTTPException(status_code=401, detail="Google Authentication token is required")
        
    try:
        email = verify_google_token(google_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
        
    student = db.query(Student).filter(Student.email == email).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in registry.")
        
    latest_att = db.query(Attendance).filter(Attendance.student_id == student.id).order_by(Attendance.timestamp.desc()).first()
    if not latest_att:
        raise HTTPException(status_code=404, detail="No attendance records found for student.")
        
    session = db.query(ClassroomSession).filter(ClassroomSession.subject == latest_att.subject).order_by(ClassroomSession.id.desc()).first()
    session_date = session.session_date if session else to_local_time(latest_att.timestamp).strftime("%Y-%m-%d")
    
    local_dt = to_local_time(latest_att.timestamp)
    roll_last2 = student.roll_number[-2:] if len(student.roll_number) >= 2 else student.roll_number
    date_clean = session_date.replace("-", "")
    receipt_id = f"REC-{date_clean}-{roll_last2}-{student.id:03d}"
    
    receipt_data = {
        "name": student.name,
        "roll_number": student.roll_number,
        "roll_number_last2": roll_last2,
        "email": student.email,
        "subject": latest_att.subject,
        "session_date": session_date,
        "timestamp": local_dt.strftime("%Y-%m-%d %I:%M %p"),
        "receipt_id": receipt_id
    }
    
    pdf_buffer = generate_student_receipt_pdf(receipt_data)
    filename = f"attendance_receipt_{roll_last2}_{date_clean}.pdf"
    
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)

