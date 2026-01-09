"""
Naarad - Database Module
Supports PostgreSQL (production) and SQLite (local development)
"""
import os
from urllib.parse import urlparse
from .config import Config

# Detect database type
USE_POSTGRES = bool(Config.DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
else:
    import sqlite3

from flask import g


def get_db():
    """Get database connection with dict-like row access."""
    if 'db' not in g:
        if USE_POSTGRES:
            g.db = psycopg2.connect(Config.DATABASE_URL)
        else:
            db_dir = os.path.dirname(Config.DB_FILE)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            g.db = sqlite3.connect(Config.DB_FILE)
            g.db.row_factory = sqlite3.Row
    return g.db


def get_cursor(conn):
    """Get a cursor with dict-like row access."""
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=RealDictCursor)
    else:
        return conn.cursor()


def close_db(e=None):
    """Close the database connection if it exists."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database tables.
    
    Uses a direct connection (not flask.g) since this runs at startup.
    """
    if USE_POSTGRES:
        conn = psycopg2.connect(Config.DATABASE_URL)
        cursor = conn.cursor()
        
        # PostgreSQL syntax
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracks (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                track_id TEXT NOT NULL,
                campaign_id TEXT,
                
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                sent_at TEXT,
                
                ip_address TEXT,
                country TEXT,
                region TEXT,
                city TEXT,
                latitude REAL,
                longitude REAL,
                timezone TEXT,
                isp TEXT,
                org TEXT,
                asn TEXT,
                
                user_agent TEXT,
                browser TEXT,
                browser_version TEXT,
                os TEXT,
                os_version TEXT,
                device_type TEXT,
                device_brand TEXT,
                is_mobile BOOLEAN,
                is_bot BOOLEAN,
                
                referer TEXT,
                accept_language TEXT,
                accept_encoding TEXT,
                accept_header TEXT,
                connection_type TEXT,
                do_not_track TEXT,
                cache_control TEXT,
                
                sec_ch_ua TEXT,
                sec_ch_ua_mobile TEXT,
                sec_ch_ua_platform TEXT,
                
                open_count INTEGER DEFAULT 1,
                click_count INTEGER DEFAULT 0,
                first_seen TEXT,
                last_seen TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clicks (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                track_id TEXT NOT NULL,
                campaign_id TEXT,
                link_id TEXT NOT NULL,
                target_url TEXT NOT NULL,
                ip_address TEXT,
                country TEXT,
                city TEXT,
                user_agent TEXT,
                browser TEXT,
                os TEXT,
                device_type TEXT,
                referer TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS geo_cache (
                ip_address TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                cached_at TEXT NOT NULL
            )
        ''')
        
        # PostgreSQL indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_track_id ON tracks(track_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON tracks(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clicks_track ON clicks(track_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_country ON tracks(country)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_device ON tracks(device_type)')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("[DB] PostgreSQL initialized")
    else:
        # SQLite syntax
        db_dir = os.path.dirname(Config.DB_FILE)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        conn = sqlite3.connect(Config.DB_FILE)
        conn.row_factory = sqlite3.Row
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                track_id TEXT NOT NULL,
                campaign_id TEXT,
                label TEXT,
                
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                sent_at TEXT,
                
                ip_address TEXT,
                country TEXT,
                region TEXT,
                city TEXT,
                latitude REAL,
                longitude REAL,
                timezone TEXT,
                isp TEXT,
                org TEXT,
                asn TEXT,
                
                user_agent TEXT,
                browser TEXT,
                browser_version TEXT,
                os TEXT,
                os_version TEXT,
                device_type TEXT,
                device_brand TEXT,
                is_mobile BOOLEAN,
                is_bot BOOLEAN,
                
                referer TEXT,
                accept_language TEXT,
                accept_encoding TEXT,
                accept_header TEXT,
                connection_type TEXT,
                do_not_track TEXT,
                cache_control TEXT,
                
                sec_ch_ua TEXT,
                sec_ch_ua_mobile TEXT,
                sec_ch_ua_platform TEXT,
                
                open_count INTEGER DEFAULT 1,
                click_count INTEGER DEFAULT 0,
                first_seen TEXT,
                last_seen TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                track_id TEXT NOT NULL,
                campaign_id TEXT,
                link_id TEXT NOT NULL,
                target_url TEXT NOT NULL,
                ip_address TEXT,
                country TEXT,
                city TEXT,
                user_agent TEXT,
                browser TEXT,
                os TEXT,
                device_type TEXT,
                referer TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS geo_cache (
                ip_address TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                cached_at TEXT NOT NULL
            )
        ''')
        
        conn.execute('CREATE INDEX IF NOT EXISTS idx_track_id ON tracks(track_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON tracks(timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_clicks_track ON clicks(track_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_country ON tracks(country)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_device ON tracks(device_type)')
        
        conn.commit()
        conn.close()
        print("[DB] SQLite initialized")


def migrate_db():
    """Add new columns to existing database if they don't exist."""
    if USE_POSTGRES:
        conn = psycopg2.connect(Config.DATABASE_URL)
        cursor = conn.cursor()
        
        # Get existing columns
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'tracks'
        """)
        existing_cols = {row[0] for row in cursor.fetchall()}
        
        new_columns = [
            ('org', 'TEXT'),
            ('asn', 'TEXT'),
            ('accept_encoding', 'TEXT'),
            ('accept_header', 'TEXT'),
            ('connection_type', 'TEXT'),
            ('do_not_track', 'TEXT'),
            ('cache_control', 'TEXT'),
            ('sec_ch_ua', 'TEXT'),
            ('sec_ch_ua_mobile', 'TEXT'),
            ('sec_ch_ua_platform', 'TEXT'),
            ('label', 'TEXT'),
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f'ALTER TABLE tracks ADD COLUMN {col_name} {col_type}')
                    print(f"[DB] Added column: {col_name}")
                except Exception:
                    pass
        
        conn.commit()
        cursor.close()
        conn.close()
    else:
        conn = sqlite3.connect(Config.DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(tracks)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        
        new_columns = [
            ('org', 'TEXT'),
            ('asn', 'TEXT'),
            ('accept_encoding', 'TEXT'),
            ('accept_header', 'TEXT'),
            ('connection_type', 'TEXT'),
            ('do_not_track', 'TEXT'),
            ('cache_control', 'TEXT'),
            ('sec_ch_ua', 'TEXT'),
            ('sec_ch_ua_mobile', 'TEXT'),
            ('sec_ch_ua_platform', 'TEXT'),
            ('label', 'TEXT'),
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in existing_cols:
                try:
                    conn.execute(f'ALTER TABLE tracks ADD COLUMN {col_name} {col_type}')
                    print(f"[DB] Added column: {col_name}")
                except Exception:
                    pass
        
        conn.commit()
        conn.close()


# Helper to get the right placeholder for queries
def placeholder():
    """Return the correct SQL placeholder for the database type."""
    return '%s' if USE_POSTGRES else '?'
