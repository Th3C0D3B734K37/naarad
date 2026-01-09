#!/usr/bin/env python3
"""
Management script for Naarad.
Handles database initialization, migrations, and other admin tasks.
"""
import sys
import argparse
from app.config import Config
from app.database import init_db, migrate_db

def init():
    """Initialize the database."""
    print(f"[MANAGE] Initializing database (Postgres: {bool(Config.DATABASE_URL)})...")
    try:
        init_db()
        print("[MANAGE] Database initialized successfully.")
    except Exception as e:
        print(f"[MANAGE] Error initializing database: {e}")
        sys.exit(1)

def migrate():
    """Run database migrations."""
    print("[MANAGE] Running migrations...")
    try:
        migrate_db()
        print("[MANAGE] Migrations completed successfully.")
    except Exception as e:
        print(f"[MANAGE] Error running migrations: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Naarad Management Script')
    parser.add_argument('command', choices=['init', 'migrate', 'init_all'], 
                        help='Command to run (init_all runs init then migrate)')
    
    args = parser.parse_args()
    
    if args.command == 'init':
        init()
    elif args.command == 'migrate':
        migrate()
    elif args.command == 'init_all':
        init()
        migrate()

if __name__ == '__main__':
    main()
