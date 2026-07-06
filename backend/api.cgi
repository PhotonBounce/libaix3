#!/home/photonb/public_html/opsbrief-api/venv/bin/python3
import sys
import os

# Add app directory to path
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

# Set required env vars
os.environ.setdefault('JWT_SECRET_KEY', 'opsbrief-local-dev-secret-key-32chars-min')
os.environ.setdefault('FREE_MODE', 'true')
os.environ.setdefault('ANTHROPIC_API_KEY', '')

from opsbrief.main import app as fastapi_app
from a2wsgi import ASGIMiddleware

application = ASGIMiddleware(fastapi_app)

# CGI entry point
def main():
    from wsgiref.handlers import CGIHandler
    CGIHandler().run(application)

if __name__ == '__main__':
    main()
