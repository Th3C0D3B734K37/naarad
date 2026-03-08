"""
Naarad - Configuration
"""
import os
import logging

log = logging.getLogger(__name__)

class Config:
    """Application configuration."""

    # Server
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 8080))
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

    # Database - PostgreSQL in production (DATABASE_URL), SQLite locally
    DATABASE_URL = os.getenv('DATABASE_URL')  # Railway injects this
    DB_FILE = os.getenv('DB_FILE', 'tracking.db')  # SQLite fallback

    # Security
    # IMPORTANT: Set SECRET_KEY and API_KEY as environment variables in production.
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        import secrets
        SECRET_KEY = secrets.token_hex(32)
        log.warning("[CONFIG] SECRET_KEY not set – generated ephemeral key. Set SECRET_KEY env var for production.")

    API_KEY = os.getenv('API_KEY')
    if not API_KEY:
        import secrets as _s
        API_KEY = _s.token_urlsafe(32)
        log.warning("[CONFIG] API_KEY not set – generated ephemeral key. Set API_KEY env var for production.")

    # Auth: when True, all /api/* endpoints require X-API-Key header
    REQUIRE_AUTH = os.getenv('REQUIRE_AUTH', 'true').lower() == 'true'

    # Allowed origins for CORS (comma-separated). Empty = same-origin only.
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '')

    # Webhooks
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', None)
    # Shared secret appended as X-Webhook-Secret header
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', None)

    # Geo API URL (H-07: configurable — ip-api.com free tier is HTTP-only,
    # set this to an HTTPS endpoint in production, e.g. 'https://pro.ip-api.com/json')
    GEO_API_URL = os.getenv('GEO_API_URL', 'http://ip-api.com/json')

    # Geo cache duration in minutes
    GEO_CACHE_MINUTES = int(os.getenv('GEO_CACHE_MINUTES', 60))

    # Rate limiting: max pixel hits per IP per minute (0 = disabled)
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 30))

    # Rate limiting: max API calls per IP per minute (0 = disabled)
    API_RATE_LIMIT_PER_MINUTE = int(os.getenv('API_RATE_LIMIT_PER_MINUTE', 60))

    # ── Node Sync (Hybrid Architecture) ─────────────────────────────────────
    # URL of the remote cloud node to pull tracks from (e.g. 'https://my-cloud-tracker.com')
    SYNC_REMOTE_URL = os.getenv('SYNC_REMOTE_URL')
    
    # API key for the remote cloud node
    SYNC_API_KEY = os.getenv('SYNC_API_KEY')
    
    # How often to pull data from the remote node, in seconds
    SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', 60))
    
    # If true, successfully pulled data will be explicitly deleted from the remote node
    SYNC_AUTO_WIPE = os.getenv('SYNC_AUTO_WIPE', 'true').lower() == 'true'
