import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import generate_student_receipt_pdf

def generate_scratchpad_receipts():
    print("Generating sample receipts in scratchpad directory...")
    
    sample_data = {
        "name": "VANDAN DEV BARANWAL",
        "roll_number": "2500520200001",
        "roll_number_last2": "01",
        "email": "2500520200001@ietlucknow.ac.in",
        "subject": "IEE301 Electromagnetic Field Theory",
        "session_date": "2026-08-02",
        "timestamp": "2026-08-02 11:45 AM",
        "receipt_id": "REC-20260802-01-001"
    }

    # 1. Save PDF receipt to scratch/
    pdf_buffer = generate_student_receipt_pdf(sample_data)
    pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_attendance_receipt_01.pdf")
    with open(pdf_path, "wb") as f:
        f.write(pdf_buffer.getvalue())
    print(f"   [PDF Generated] Saved to: {pdf_path} ({len(pdf_buffer.getvalue())} bytes)")

    # 2. Save JPG receipt to scratch/ (using PIL / Pillow)
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (800, 1000), color='#ffffff')
        draw = ImageDraw.Draw(img)
        
        # Header bar
        draw.rectangle([0, 0, 800, 16], fill='#6366f1')
        
        # Header text
        draw.text((400, 60), "INSTITUTE OF ENGINEERING & TECHNOLOGY", fill='#4f46e5', anchor='ms', font_size=24)
        draw.text((400, 95), "Department of Electrical Engineering | Batch 2029", fill='#64748b', anchor='ms', font_size=15)
        
        # Line
        draw.line([60, 125, 740, 125], fill='#cbd5e1', width=2)
        
        # Receipt Title
        draw.text((400, 175), "OFFICIAL ATTENDANCE RECEIPT", fill='#0f172a', anchor='ms', font_size=26)
        draw.text((400, 210), f"REF: {sample_data['receipt_id']}", fill='#6366f1', anchor='ms', font_size=16)
        
        # Box background
        draw.rectangle([60, 240, 740, 760], fill='#ffffff', outline='#cbd5e1', width=1)
        
        # Rows
        rows = [
            ("Student Name:", sample_data['name'], '#0f172a'),
            ("Full Roll Number:", sample_data['roll_number'], '#334155'),
            ("Roll Number (2 Digits):", f"Roll #{sample_data['roll_number_last2']}", '#6366f1'),
            ("Email Address:", sample_data['email'], '#334155'),
            ("Subject:", sample_data['subject'], '#0f172a'),
            ("Date & Time:", sample_data['timestamp'], '#334155'),
            ("Verification Status:", "✓ PRESENT & VERIFIED", '#059669')
        ]
        
        y = 300
        for label, val, color in rows:
            draw.text((100, y), label, fill='#64748b', font_size=18)
            draw.text((700, y), val, fill=color, anchor='ra', font_size=18)
            draw.line([100, y + 35, 700, y + 35], fill='#f1f5f9', width=1)
            y += 65

        # Footer
        draw.text((400, 830), "Verified via Anti-Proxy Classroom Geofence & Google Authentication", fill='#94a3b8', anchor='ms', font_size=14)
        draw.text((400, 860), "This is an official system generated attendance receipt.", fill='#94a3b8', anchor='ms', font_size=14)

        jpg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_attendance_receipt_01.jpg")
        img.save(jpg_path, "JPEG", quality=95)
        print(f"   [JPG Generated] Saved to: {jpg_path} ({os.path.getsize(jpg_path)} bytes)")
    except Exception as e:
        print(f"   [JPG Note] Pillow generation notice: {e}")

if __name__ == "__main__":
    generate_scratchpad_receipts()
