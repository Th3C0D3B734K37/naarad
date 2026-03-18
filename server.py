#!/usr/bin/env python3
"""
naarad Server
Simple, open-source email tracking for personal use.
"""
import sys, io
# Only wrap stdout if it's not already a TextIOWrapper with UTF-8
if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
elif hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from app import create_app
from app.config import Config
from app.database import init_db, migrate_db

# Create the Flask app. 
app = create_app()

# Run migrations unconditionally so it works on platforms like Render
# where the Procfile (manage.py init_all) might be ignored by default start commands.
init_db()
migrate_db()

def main():

    url = f"http://localhost:{Config.PORT}"
    print()
    print("=" * 56)
    print("  naarad (नारद) — Email Tracker")
    print("=" * 56)
    print(f"  Dashboard : {url}/dashboard")
    print()
    if not Config.IS_PRODUCTION:
        print(f"  API Key   : {Config.API_KEY}")
        print()
        print("  ┌─────────────────────────────────────────────────┐")
        print("  │  Open the dashboard above, click ⚙ Settings,   │")
        print("  │  and paste the API Key shown above.             │")
        print("  └─────────────────────────────────────────────────┘")
        print()
    print("  Endpoints:")
    print(f"    {url}/track?id=RECIPIENT    Open tracking pixel")
    print(f"    {url}/click/ID/URL          Link click tracking")
    print(f"    {url}/api/stats             Statistics API")
    print(f"    {url}/api/health            Health check")
    print("=" * 56)
    print()

    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

if __name__ == '__main__':
    main()
