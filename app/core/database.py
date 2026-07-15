import os
import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import settings

# Global Firestore client reference
db = None

def init_db_sync() -> None:
    global db
    if db is not None:
        return
        
    try:
        firebase_admin.get_app()
    except ValueError:
        bucket_name = settings.FIREBASE_STORAGE_BUCKET or os.environ.get("FIREBASE_STORAGE_BUCKET") or f"{settings.FIREBASE_PROJECT_ID}.appspot.com"
        options = {"storageBucket": bucket_name}
        
        # Check if credentials JSON is provided as environment variable
        import json
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            try:
                cred_info = json.loads(cred_json)
                cred = credentials.Certificate(cred_info)
                firebase_admin.initialize_app(cred, options)
            except Exception as e:
                print(f"ERROR: Failed to initialize Firebase using FIREBASE_CREDENTIALS_JSON: {e}")
                firebase_admin.initialize_app(options=options)
        else:
            # Fall back to credentials file path
            cred_path = settings.FIREBASE_CREDENTIALS_PATH
            if cred_path:
                # Resolve path relative to the backend root directory to be robust
                if not os.path.isabs(cred_path):
                    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    resolved_path = os.path.join(backend_root, cred_path)
                    if os.path.exists(resolved_path):
                        cred_path = resolved_path
                
                if os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred, options)
                else:
                    firebase_admin.initialize_app(options=options)
            else:
                firebase_admin.initialize_app(options=options)
            
    db = firestore.client()

    print("INFO:    Firebase Firestore client initialized successfully!")


async def init_db() -> None:
    init_db_sync()

def get_db():
    global db
    if db is None:
        init_db_sync()
    return db

