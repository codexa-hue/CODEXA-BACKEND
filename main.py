import sys
import os

# Add the current directory to sys.path so that 'app' can be imported correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from firebase_functions import https_fn
import firebase_admin
from app.main import app as fastapi_app

# Initialize Firebase Admin SDK if not already done
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

# Expose the FastAPI app under the function name 'api'
api = https_fn.on_request(
    app=fastapi_app,
    min_instances=0
)
