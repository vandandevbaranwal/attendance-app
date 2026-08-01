import os
from google.oauth2 import id_token
from google.auth.transport import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

def verify_google_token(token: str) -> str:
    """
    Verifies a Google ID token and returns the user's email.
    """
    is_dev = os.getenv("ENV", "production").lower() == "development"
    if token.startswith("mock_token_"):
        if is_dev:
            parts = token.split("mock_token_")
            if len(parts) > 1 and parts[1]:
                return parts[1]
            return "2500520200001@ietlucknow.ac.in"
        else:
            raise ValueError("Mock authentication tokens are disabled in the production environment.")

    if not GOOGLE_CLIENT_ID or GOOGLE_CLIENT_ID == "your-google-client-id-here.apps.googleusercontent.com":
        raise ValueError("GOOGLE_CLIENT_ID is not configured in the .env file.")

    try:
        # Verify the ID token using google-auth library
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        
        # Check if email is verified
        if not idinfo.get("email_verified"):
            raise ValueError("Google account email is not verified.")
            
        email = idinfo.get("email")
        if not email:
            raise ValueError("Email not found in Google ID token.")
            
        return email
    except Exception as e:
        raise ValueError(f"Invalid Google ID token: {str(e)}")
