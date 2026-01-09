#!/usr/bin/env python3
"""
Naarad Server
Simple, open-source email tracking for personal use.
"""
from app import create_app
from app.config import Config
from app.database import init_db, migrate_db

# Initialize DB and App for Production (Gunicorn)
# init_db and migrate_db use direct connections, no Flask context needed
init_db()
migrate_db()
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
