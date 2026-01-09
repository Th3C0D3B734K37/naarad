#!/usr/bin/env python3
"""
Naarad Server
Simple, open-source email tracking for personal use.
"""
import sys
from app import create_app
from app.config import Config
from app.database import init_db, migrate_db

# Initialize DB and App for Production (Gunicorn)
print(f"[SERVER] Starting... DATABASE_URL set: {bool(Config.DATABASE_URL)}", flush=True)
try:
    init_db()
    migrate_db()
    print("[SERVER] Database ready", flush=True)
except Exception as e:
    print(f"[SERVER] Database init error: {e}", flush=True)
    sys.exit(1)

app = create_app()

def main():
    print()
    print("=" * 50)
    print("  NAARAD (नारद) - Email Tracker")
    print("=" * 50)
    print(f"  Server:    http://localhost:{Config.PORT}")
    print(f"  Dashboard: http://localhost:{Config.PORT}/dashboard")
    print()
    print("  Endpoints:")
    print("    /track?id=...     Tracking pixel")
    print("    /click/ID/URL     Link tracking")
    print("    /api/stats        Statistics")
    print("    /api/export       Export data")
    print("=" * 50)
    print()
    
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

if __name__ == '__main__':
    main()
