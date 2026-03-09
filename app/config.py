"""
naarad - Configuration
"""
import os
import sys
import secrets
import logging

log = logging.getLogger(__name__)


def _is_production():
    """Detect production by presence of DATABASE_URL or explicit PRODUCTION=true.
    Local development (SQLite) should Just Work without any env vars."""
    if os.getenv('PRODUCTION', '').lower() == 'true':
        return True
    if os.getenv('DATABASE_URL'):
        return True
    return False


class Config:
    """Application configuration."""

    # Server
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 8080))
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

    # Are we in production? (auto-detected from DATABASE_URL or PRODUCTION=true)
    IS_PRODUCTION = _is_production()

    # Database - PostgreSQL in production (DATABASE_URL), SQLite locally
    DATABASE_URL = os.getenv('DATABASE_URL')  # Railway / Render inject this
    DB_FILE = os.getenv('DB_FILE', 'tracking.db')  # SQLite fallback

    # Security
    SECRET_KEY = os.getenv('SECRET_KEY')
    API_KEY = os.getenv('API_KEY')

    # In production, these MUST be explicitly set
    if IS_PRODUCTION:
        if not SECRET_KEY:
            log.critical("[CONFIG] SECRET_KEY is required in production. Set SECRET_KEY env var.")
            sys.exit(1)
        if not API_KEY:
            log.critical("[CONFIG] API_KEY is required in production. Set API_KEY env var.")
            sys.exit(1)
    else:
        # Local development: auto-generate keys so the app Just Works
        if not SECRET_KEY:
            SECRET_KEY = secrets.token_hex(32)
        if not API_KEY:
            API_KEY = secrets.token_urlsafe(24)
            # This will be printed by server.py's startup banner

    # Auth: when True, all /api/* endpoints require X-API-Key header
    REQUIRE_AUTH = os.getenv('REQUIRE_AUTH', 'true').lower() == 'true'

    # Allowed origins for CORS (comma-separated). Empty = same-origin only.
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '')

    # Number of trusted reverse proxies in front of the app.
    TRUSTED_PROXY_COUNT = int(os.getenv('TRUSTED_PROXY_COUNT', 1))

    # Max request body size (16 MB)
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # Webhooks
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', None)
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', None)

    # Geo API URL
    GEO_API_URL = os.getenv('GEO_API_URL', 'http://ip-api.com/json')
    GEO_CACHE_MINUTES = int(os.getenv('GEO_CACHE_MINUTES', 60))

    # Rate limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 30))
    API_RATE_LIMIT_PER_MINUTE = int(os.getenv('API_RATE_LIMIT_PER_MINUTE', 60))

    # ── Node Sync (Hybrid Architecture) ──────────────────────────────────
    SYNC_REMOTE_URL = os.getenv('SYNC_REMOTE_URL')
    SYNC_API_KEY = os.getenv('SYNC_API_KEY')
    SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', 60))
    SYNC_AUTO_WIPE = os.getenv('SYNC_AUTO_WIPE', 'true').lower() == 'true'
