"""Passenger WSGI entry point for cPanel deployment."""
import sys
import os

# Add the app directory to Python path
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

# Import the FastAPI app and wrap as WSGI
from opsbrief.main import app as fastapi_app
from a2wsgi import ASGIMiddleware

# Passenger expects a WSGI callable named 'application'
application = ASGIMiddleware(fastapi_app)
