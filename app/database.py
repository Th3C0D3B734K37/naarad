"""
Naarad - Database Module
"""
import sqlite3
import os
from .config import Config

def get_db():
    """Get database connection with row factory."""
    os.makedirs(os.path.dirname(Config.DB_FILE), exist_ok=True)
    conn = sqlite3.connect(Config.DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables."""
    conn = get_db()
    
    # Main tracking table - captures maximum information
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            track_id TEXT NOT NULL,
            campaign_id TEXT,
            
            -- Email Context
            sender TEXT,
            recipient TEXT,
            subject TEXT,
            sent_at TEXT,
            
            -- Network Information
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
            
            -- User Agent & Device
            user_agent TEXT,
            browser TEXT,
            browser_version TEXT,
            os TEXT,
            os_version TEXT,
            device_type TEXT,
            device_brand TEXT,
            is_mobile BOOLEAN,
            is_bot BOOLEAN,
            
            -- Request Headers
            referer TEXT,
            accept_language TEXT,
            accept_encoding TEXT,
            accept_header TEXT,
            connection_type TEXT,
            do_not_track TEXT,
            cache_control TEXT,
            
            -- Client Hints (Modern browsers)
            sec_ch_ua TEXT,
            sec_ch_ua_mobile TEXT,
            sec_ch_ua_platform TEXT,
            
            -- Counters & Timestamps
            open_count INTEGER DEFAULT 1,
            click_count INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT
        )
    ''')
    
    # Click tracking table
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
    
    # Geo cache for IP lookups
    conn.execute('''
        CREATE TABLE IF NOT EXISTS geo_cache (
            ip_address TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            cached_at TEXT NOT NULL
        )
    ''')
    
    # Performance indexes
    conn.execute('CREATE INDEX IF NOT EXISTS idx_track_id ON tracks(track_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON tracks(timestamp)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_clicks_track ON clicks(track_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_country ON tracks(country)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_device ON tracks(device_type)')
    
    conn.commit()
    conn.close()
    print("[DB] Initialized")

def migrate_db():
    """Add new columns to existing database if they don't exist."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(tracks)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    
    # New columns to add
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
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            try:
                conn.execute(f'ALTER TABLE tracks ADD COLUMN {col_name} {col_type}')
                print(f"[DB] Added column: {col_name}")
            except sqlite3.OperationalError:
                pass  # Column already exists
    
    conn.commit()
    conn.close()
