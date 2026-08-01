import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Student, Attendance, ClassroomSession

client = TestClient(app)

def run_tests():
    print("=========================================")
    print("RUNNING SECURED ENDPOINT & VALIDATION TESTS")
    print("=========================================\n")
    
    # Define CR token and non-CR token
    valid_cr_email = "2500520200001@ietlucknow.ac.in"
    invalid_cr_email = "2500520200002@ietlucknow.ac.in"
    
    valid_cr_token = f"mock_token_{valid_cr_email}"
    invalid_cr_token = f"mock_token_{invalid_cr_email}"
    
    valid_headers = {"Authorization": f"Bearer {valid_cr_token}"}
    invalid_headers = {"Authorization": f"Bearer {invalid_cr_token}"}

    # Clear database tables to ensure test run isolation
    db = SessionLocal()
    try:
        db.query(Attendance).delete()
        db.query(ClassroomSession).delete()
        db.commit()
    finally:
        db.close()

    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Test Root Endpoint
    print("1. Testing Root GET /...")
    res = client.get("/")
    assert res.status_code == 200
    print("   [OK] Root endpoint returned 200.")

    # 2. Test Subjects List (Public)
    print("\n2. Testing GET /subjects...")
    res = client.get("/subjects")
    assert res.status_code == 200
    subjects_data = res.json()
    assert "subjects" in subjects_data
    target_subject = subjects_data["subjects"][0]
    print(f"   [OK] Subjects list fetched. Target: {target_subject}")

    # 3. Test Verify CR Endpoint
    print("\n3. Testing POST /verify-cr...")
    # Test valid CR
    res = client.post("/verify-cr", json={"google_token": valid_cr_token})
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    # Test invalid CR
    res = client.post("/verify-cr", json={"google_token": invalid_cr_token})
    assert res.status_code == 403
    print("   [OK] /verify-cr verified valid CR and blocked invalid student.")

    # 4. Test Start Session Security
    print("\n4. Testing POST /start-session (Security Checks)...")
    # No Auth Header
    res = client.post("/start-session", json={"subject": target_subject, "session_date": today_str})
    assert res.status_code == 401
    # Invalid CR Auth Header
    res = client.post("/start-session", json={"subject": target_subject, "session_date": today_str}, headers=invalid_headers)
    assert res.status_code == 403
    # Valid CR Auth Header
    res = client.post("/start-session", json={"subject": target_subject, "session_date": today_str}, headers=valid_headers)
    assert res.status_code == 200
    start_data = res.json()
    active_token = start_data["token"]
    print(f"   [OK] Start session blocked unauthorized users, and succeeded with valid CR. Token: {active_token}")

    # 5. Test Active Session Status (Public)
    print("\n5. Testing GET /active-session (Public access)...")
    res = client.get("/active-session")
    assert res.status_code == 200
    active_data = res.json()
    assert active_data["is_active"] is True
    assert active_data["subject"] == target_subject
    assert active_data["token"] == active_token
    print(f"   [OK] Active session returned correctly. Expires in: {active_data['remaining_seconds']}s")

    # 6. Test Student Marking Attendance (Public scanner endpoint)
    print("\n6. Testing POST /mark-attendance (Whitelisted email)...")
    student_email = "2500520200002@ietlucknow.ac.in" # student 02
    res = client.post("/mark-attendance", json={
        "token": active_token,
        "google_token": f"mock_token_{student_email}"
    })
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "success"
    assert res_data["roll_number"] == "2500520200002"
    print(f"   [OK] Attendance marked successfully for Roll No: {res_data['roll_number']}")

    # 7. Test Duplicate Attendance Prevention
    print("\n7. Testing POST /mark-attendance (Duplicate Prevention)...")
    res = client.post("/mark-attendance", json={
        "token": active_token,
        "google_token": f"mock_token_{student_email}"
    })
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "already_marked"
    print(f"   [OK] Duplicate attendance prevented correctly.")

    # 8. Test Attendance Report Security
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"\n8. Testing GET /attendance-report (Security Checks)...")
    # No Auth Header
    res = client.get(f"/attendance-report?date={today_str}&subject={target_subject}")
    assert res.status_code == 401
    # Invalid CR Auth Header
    res = client.get(f"/attendance-report?date={today_str}&subject={target_subject}", headers=invalid_headers)
    assert res.status_code == 403
    # Valid CR Auth Header
    res = client.get(f"/attendance-report?date={today_str}&subject={target_subject}", headers=valid_headers)
    assert res.status_code == 200
    report_data = res.json()
    assert len(report_data) > 0
    student_02 = next(s for s in report_data if s["roll_number"] == "2500520200002")
    assert student_02["status"] == "Present"
    print(f"   [OK] Report blocked unauthorized access. Verified student 02 is marked {student_02['status']}.")

    # 9. Test Download PDF Security
    print("\n9. Testing GET /download-pdf (Security Checks)...")
    # No Auth Header or Query Param
    res = client.get(f"/download-pdf?date={today_str}&subject={target_subject}&only_present=true")
    assert res.status_code == 401
    # Invalid CR Query Param
    res = client.get(f"/download-pdf?date={today_str}&subject={target_subject}&only_present=true&google_token={invalid_cr_token}")
    assert res.status_code == 403
    # Valid CR Query Param
    res = client.get(f"/download-pdf?date={today_str}&subject={target_subject}&only_present=true&google_token={valid_cr_token}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")
    print(f"   [OK] PDF download blocked unauthorized access, and succeeded with valid CR token parameter.")

    # 10. Test Stop Session Security
    print("\n10. Testing POST /stop-session (Security Checks)...")
    # No Auth Header
    res = client.post("/stop-session")
    assert res.status_code == 401
    # Invalid CR Auth
    res = client.post("/stop-session", headers=invalid_headers)
    assert res.status_code == 403
    # Valid CR Auth
    res = client.post("/stop-session", headers=valid_headers)
    assert res.status_code == 200
    # Verify active-session is now inactive
    res = client.get("/active-session")
    assert res.json()["is_active"] is False
    print("    [OK] Stop session blocked unauthorized access, and stopped session successfully.")

    # 11. Test Geofencing validation
    print("\n11. Testing Geofencing validations...")
    # Start a session WITH coordinates
    res = client.post("/start-session", json={
        "subject": target_subject,
        "session_date": today_str,
        "latitude": 26.8929,
        "longitude": 80.9840
    }, headers=valid_headers)
    assert res.status_code == 200
    geo_token = res.json()["token"]
    
    # Try to mark attendance WITHOUT coordinates -> Should fail (400)
    res = client.post("/mark-attendance", json={
        "token": geo_token,
        "google_token": f"mock_token_{valid_cr_email}"
    })
    assert res.status_code == 400
    assert "Location access is required" in res.json()["detail"]
    
    # Try to mark attendance WITH far coordinates (~6km) -> Should fail (400)
    res = client.post("/mark-attendance", json={
        "token": geo_token,
        "google_token": f"mock_token_{valid_cr_email}",
        "latitude": 26.9500,
        "longitude": 80.9900
    })
    assert res.status_code == 400
    assert "Location verification failed" in res.json()["detail"]
    
    # Try to mark attendance WITH close coordinates (~14m) -> Should succeed (200)
    res = client.post("/mark-attendance", json={
        "token": geo_token,
        "google_token": f"mock_token_{valid_cr_email}",
        "latitude": 26.8930,
        "longitude": 80.9841
    })
    assert res.status_code == 200
    # Clean stop
    client.post("/stop-session", headers=valid_headers)
    print("   [OK] Geofencing successfully blocked distant users and accepted close users.")

    print("\n=========================================")
    print("ALL SECURED TESTS PASSED SUCCESSFULLY!")
    print("=========================================")

if __name__ == "__main__":
    run_tests()
