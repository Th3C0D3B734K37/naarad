"""
naarad - Database Module
Supports PostgreSQL (production) and SQLite (local development).
"""
import os
import logging
from urllib.parse import urlparse
from .config import Config

log = logging.getLogger(__name__)

# Detect database type at import time
USE_POSTGRES = bool(Config.DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2 import pool as pg_pool
else:
    import sqlite3

from flask import g


# ── Connection Pooling (PostgreSQL) ────────────────────────────────────────
_pg_pool = None

def _get_pg_pool():
    """Get or create PostgreSQL connection pool (M-02)."""
    global _pg_pool
    if _pg_pool is None and USE_POSTGRES:
        try:
            _pg_pool = pg_pool.ThreadedConnectionPool(
                minconn=1, maxconn=10, dsn=Config.DATABASE_URL,
                connect_timeout=5  # Avoid indefinite block if Postgres is down
            )
            log.info("[DB] PostgreSQL connection pool created (min=1, max=10)")
        except Exception as e:
            log.error("[DB] Failed to create connection pool: %s", e)
            _pg_pool = None
    return _pg_pool


def get_db():
    """Get database connection with dict-like row access."""
    if 'db' not in g:
        if USE_POSTGRES:
            pool = _get_pg_pool()
            if pool:
                g.db = pool.getconn()
            else:
                g.db = psycopg2.connect(Config.DATABASE_URL, connect_timeout=5)
        else:
            db_dir = os.path.dirname(Config.DB_FILE)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            g.db = sqlite3.connect(Config.DB_FILE)
            g.db.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent write performance
            g.db.execute('PRAGMA journal_mode=WAL')
            g.db.execute('PRAGMA foreign_keys=ON')
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
        if USE_POSTGRES and _pg_pool:
            _pg_pool.putconn(db)
        else:
            db.close()


# ─── Common column definitions ────────────────────────────────────────────────
# This list must include ALL columns that might need to be added to
# existing databases via migrate_db(). It should stay in sync with init_db().

_TRACKS_COLUMNS = [
    ('campaign_id',        'TEXT'),
    ('label',              'TEXT'),
    ('sender',             'TEXT'),
    ('recipient',          'TEXT'),
    ('subject',            'TEXT'),
    ('sent_at',            'TEXT'),
    ('ip_address',         'TEXT'),
    ('country',            'TEXT'),
    ('region',             'TEXT'),
    ('city',               'TEXT'),
    ('latitude',           'REAL'),
    ('longitude',          'REAL'),
    ('timezone',           'TEXT'),
    ('isp',                'TEXT'),
    ('org',                'TEXT'),
    ('asn',                'TEXT'),
    ('user_agent',         'TEXT'),
    ('browser',            'TEXT'),
    ('browser_version',    'TEXT'),
    ('os',                 'TEXT'),
    ('os_version',         'TEXT'),
    ('device_type',        'TEXT'),
    ('device_brand',       'TEXT'),
    ('is_mobile',          'INTEGER' if not USE_POSTGRES else 'BOOLEAN'),
    ('is_bot',             'INTEGER' if not USE_POSTGRES else 'BOOLEAN'),
    ('referer',            'TEXT'),
    ('accept_language',    'TEXT'),
    ('accept_encoding',    'TEXT'),
    ('accept_header',      'TEXT'),
    ('connection_type',    'TEXT'),
    ('do_not_track',       'TEXT'),
    ('cache_control',      'TEXT'),
    ('sec_ch_ua',          'TEXT'),
    ('sec_ch_ua_mobile',   'TEXT'),
    ('sec_ch_ua_platform', 'TEXT'),
    ('open_count',         'INTEGER DEFAULT 0'),
    ('click_count',        'INTEGER DEFAULT 0'),
    ('first_seen',         'TEXT'),
    ('last_seen',          'TEXT'),
]


def init_db():
    """
    Initialize database tables.
    Uses a direct connection (not flask.g) since this runs at startup.
    """
    if USE_POSTGRES:
        conn = psycopg2.connect(Config.DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracks (
                id               SERIAL PRIMARY KEY,
                timestamp        TEXT NOT NULL,
                track_id         TEXT NOT NULL,
                campaign_id      TEXT,
                label            TEXT,

                sender           TEXT,
                recipient        TEXT,
                subject          TEXT,
                sent_at          TEXT,

                ip_address       TEXT,
                country          TEXT,
                region           TEXT,
                city             TEXT,
                latitude         REAL,
                longitude        REAL,
                timezone         TEXT,
                isp              TEXT,
                org              TEXT,
                asn              TEXT,

                user_agent       TEXT,
                browser          TEXT,
                browser_version  TEXT,
                os               TEXT,
                os_version       TEXT,
                device_type      TEXT,
                device_brand     TEXT,
                is_mobile        BOOLEAN,
                is_bot           BOOLEAN,

                referer          TEXT,
                accept_language  TEXT,
                accept_encoding  TEXT,
                accept_header    TEXT,
                connection_type  TEXT,
                do_not_track     TEXT,
                cache_control    TEXT,

                sec_ch_ua          TEXT,
                sec_ch_ua_mobile   TEXT,
                sec_ch_ua_platform TEXT,

                open_count  INTEGER DEFAULT 0,
                click_count INTEGER DEFAULT 0,
                first_seen  TEXT,
                last_seen   TEXT,

                CONSTRAINT uq_track_id UNIQUE (track_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clicks (
                id          SERIAL PRIMARY KEY,
                timestamp   TEXT NOT NULL,
                track_id    TEXT NOT NULL,
                campaign_id TEXT,
                link_id     TEXT NOT NULL,
                target_url  TEXT NOT NULL,
                ip_address  TEXT,
                country     TEXT,
                city        TEXT,
                user_agent  TEXT,
                browser     TEXT,
                os          TEXT,
                device_type TEXT,
                referer     TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS geo_cache (
                ip_address TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                cached_at  TEXT NOT NULL
            )
        ''')

        # Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_track_id   ON tracks(track_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp  ON tracks(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_seen  ON tracks(last_seen)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_clicks_track ON clicks(track_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_country    ON tracks(country)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_device     ON tracks(device_type)')

        # Schema versioning to prevent redundant migrations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        ''')
        cursor.execute('INSERT INTO schema_version (version) VALUES (1) ON CONFLICT DO NOTHING')

        conn.commit()
        cursor.close()
        conn.close()
        log.info("[DB] PostgreSQL initialized")

    else:
        # SQLite
        db_dir = os.path.dirname(Config.DB_FILE)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(Config.DB_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS tracks (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp        TEXT NOT NULL,
                track_id         TEXT NOT NULL UNIQUE,
                campaign_id      TEXT,
                label            TEXT,

                sender           TEXT,
                recipient        TEXT,
                subject          TEXT,
                sent_at          TEXT,

                ip_address       TEXT,
                country          TEXT,
                region           TEXT,
                city             TEXT,
                latitude         REAL,
                longitude        REAL,
                timezone         TEXT,
                isp              TEXT,
                org              TEXT,
                asn              TEXT,

                user_agent       TEXT,
                browser          TEXT,
                browser_version  TEXT,
                os               TEXT,
                os_version       TEXT,
                device_type      TEXT,
                device_brand     TEXT,
                is_mobile        INTEGER,
                is_bot           INTEGER,

                referer          TEXT,
                accept_language  TEXT,
                accept_encoding  TEXT,
                accept_header    TEXT,
                connection_type  TEXT,
                do_not_track     TEXT,
                cache_control    TEXT,

                sec_ch_ua          TEXT,
                sec_ch_ua_mobile   TEXT,
                sec_ch_ua_platform TEXT,

                open_count  INTEGER DEFAULT 0,
                click_count INTEGER DEFAULT 0,
                first_seen  TEXT,
                last_seen   TEXT
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS clicks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                track_id    TEXT NOT NULL,
                campaign_id TEXT,
                link_id     TEXT NOT NULL,
                target_url  TEXT NOT NULL,
                ip_address  TEXT,
                country     TEXT,
                city        TEXT,
                user_agent  TEXT,
                browser     TEXT,
                os          TEXT,
                device_type TEXT,
                referer     TEXT
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS geo_cache (
                ip_address TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                cached_at  TEXT NOT NULL
            )
        ''')

        conn.execute('CREATE INDEX IF NOT EXISTS idx_track_id    ON tracks(track_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp   ON tracks(timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_last_seen   ON tracks(last_seen)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_clicks_track ON clicks(track_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_country     ON tracks(country)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_device      ON tracks(device_type)')

        # Schema versioning to prevent redundant migrations
        conn.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        ''')
        conn.execute('INSERT OR IGNORE INTO schema_version (version) VALUES (1)')

        conn.commit()
        conn.close()
        log.info("[DB] SQLite initialized")


def migrate_db():
    """Add new columns to existing database if they don't exist.
    
    _TRACKS_COLUMNS now lists ALL columns to ensure schema parity
    between fresh installs and migrated databases.
    """
    if USE_POSTGRES:
        conn = psycopg2.connect(Config.DATABASE_URL)
        cursor = conn.cursor()

        # Check schema version first
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cursor.fetchone()
        current_version = row[0] if row else 0

        target_version = 2 # Increment this when adding new columns in the future

        if current_version >= target_version:
            cursor.close()
            conn.close()
            return
            
        log.info("[DB] Migrating PostgreSQL database to version %d", target_version)

        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tracks'
        """)
        existing_cols = {row[0] for row in cursor.fetchall()}

        for col_name, col_type in _TRACKS_COLUMNS:
            # Strip DEFAULT clauses for ALTER TABLE — Postgres handles defaults differently
            base_type = col_type.split(' DEFAULT ')[0].strip()
            if col_name not in existing_cols:
                try:
                    cursor.execute(
                        f'ALTER TABLE tracks ADD COLUMN {col_name} {base_type}'
                    )
                    log.info("[DB] Added column: %s", col_name)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    log.error("[DB] Failed to add column %s: %s", col_name, e)

        # Update version
        if current_version < target_version:
            cursor.execute("INSERT INTO schema_version (version) VALUES (%s) ON CONFLICT DO NOTHING", (target_version,))
            conn.commit()

        cursor.close()
        conn.close()

    else:
        conn = sqlite3.connect(Config.DB_FILE)
        cursor = conn.cursor()

        # Check schema version first
        try:
            cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
            current_version = row[0] if row else 0
        except sqlite3.OperationalError:
            current_version = 0

        target_version = 2
        
        if current_version >= target_version:
            conn.close()
            return

        log.info("[DB] Migrating SQLite database to version %d", target_version)

        cursor.execute("PRAGMA table_info(tracks)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        for col_name, col_type in _TRACKS_COLUMNS:
            if col_name not in existing_cols:
                try:
                    conn.execute(
                        f'ALTER TABLE tracks ADD COLUMN {col_name} {col_type}'
                    )
                    log.info("[DB] Added column: %s", col_name)
                    conn.commit()
                except Exception as e:
                    log.error("[DB] Failed to add column %s: %s", col_name, e)

        # Update version
        if current_version < target_version:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
            conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (?)", (target_version,))
            conn.commit()

        conn.close()


def placeholder():
    """Return the correct SQL placeholder for the database type."""
    return '%s' if USE_POSTGRES else '?'
