"""
Naarad - Configuration
"""
import os
import secrets

class Config:
    """Application configuration."""
    
    # Server
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 8080))
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    
    # Database
    DB_FILE = os.getenv('DB_FILE', 'data/tracking.db')
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
    API_KEY = os.getenv('API_KEY', secrets.token_urlsafe(32))
    REQUIRE_AUTH = os.getenv('REQUIRE_AUTH', 'false').lower() == 'true'
    
    # Webhooks
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', None)
    
    # Geo cache duration in minutes
    GEO_CACHE_MINUTES = 60
