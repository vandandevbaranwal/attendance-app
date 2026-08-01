# Anti-Proxy College Attendance System

A Python FastAPI application with an SQLite database and Google OAuth2 verification, designed for secure, anti-proxy college attendance tracking. 

## Features
1. **Dynamic QR Code Tracking**: Generates unique UUID session tokens that refresh every 10 seconds and expire after exactly 15 seconds.
2. **Google OAuth2 Integration**: Authenticates student identities directly using Google Accounts and extracts verified email addresses.
3. **Whitelist Validation**: Restricts marking attendance to whitelisted student accounts loaded into the SQLite database.
4. **Proxy Prevention**: Ensures attendance registration can only occur with active, unexpired tokens. Restricts students from duplicate markings during the same session.
5. **Modern, Responsive Frontend**: Features responsive, clean design interfaces for both the classroom display and student portal, with support for Dark/Light theme toggles.
6. **Local Test Mode**: Built-in developer mock tokens to test the full attendance flow without requiring valid Google API client configuration.

---

## Installation & Setup

### Prerequisites
- Python 3.8 or higher installed on your system.

### 1. Clone/Navigate to Project Folder
```bash
cd c:\Users\vanda\Desktop\attendance_app
```

### 2. Create and Activate Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Configuration

1. Locate the `.env` file in the project root.
2. Replace the placeholder Google Client ID with your credentials:
```env
GOOGLE_CLIENT_ID=your-actual-client-id.apps.googleusercontent.com
```

> [!NOTE]
> If you do not have a Google Client ID set up, you can still test the application locally using the **Local Developer Testing Panel** in the student interface (details below).

---

## Database Initialization & Whitelist Seeding

Before running the server, initialize the SQLite database tables and seed them with exactly 80 valid Electrical Engineering students (Roll numbers: `2500520200001` to `2500520200080` with email domain `@ietlucknow.ac.in`).

Run:
```bash
python seed.py
```

This generates the SQLite database file (`attendance.db`) containing the whitelisted student records.

---

## Running the Server

Start the FastAPI application on local port `8000`:
```bash
uvicorn main:app --reload
```

---

## Interface Walkthrough

### 1. Classroom Dashboard Screen
- Open your browser and navigate to: **`http://localhost:8000/static/dashboard.html`**
- This dashboard is displayed on the classroom screen.
- A new QR code is generated every 10 seconds, with an accompanying visual progress countdown bar.
- To switch themes, click the **Dark Mode / Light Mode** button in the upper-right corner.

### 2. Student Attendance Screen
- Scan the QR code from the dashboard or navigate directly to the URL encoded in it (e.g. `http://localhost:8000/mark-attendance?token=<ACTIVE-UUID>`).
- Sign in securely using the official **Sign in with Google** button.
- Once authenticated, the student's email is verified against the database whitelist. If the email matches and the token is valid, attendance is marked.

### 3. Local Developer Mock Testing
To test the attendance verification without configuring Google Credentials:
1. Scan the QR code or navigate to `http://localhost:8000/mark-attendance?token=<ACTIVE-UUID>`.
2. Expand the **Local developer testing options** link at the bottom of the student portal.
3. Input any whitelisted student email (e.g., `2500520200001@ietlucknow.ac.in`).
4. Click **Submit Mock Attendance**.
5. The application will simulate Google Identity authentication with a mock token suffix, marking attendance successfully.

---

## Verification & Testing Suite

We have created a comprehensive validation test suite (`scratch/test_endpoints.py`) using FastAPI's `TestClient` to verify all logical requirements (expiration, whitelist validation, duplicate marking prevention, etc.) without requiring uvicorn to run in the background.

Run the test suite:
```bash
python scratch/test_endpoints.py
```
