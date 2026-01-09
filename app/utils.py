
"""
Naarad - Utility Functions
"""
import re
import hashlib
import json
from datetime import datetime, timezone
from .config import Config

def now():
    """Get current UTC time."""
    return datetime.now(timezone.utc)

def now_iso():
    """Get current UTC time as ISO string."""
    return now().isoformat()

def sanitize_id(track_id):
    """
    Sanitize and validate track ID.
    Allows: alphanumeric, @, ., +, -, _
    """
    if not track_id:
        return 'unknown'
    # Remove dangerous characters, limit length
    cleaned = re.sub(r'[^\w\-@.+]', '', str(track_id))
    return cleaned[:100] if cleaned else 'unknown'

def validate_email(email):
    """Check if string looks like an email."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def hash_url(url):
    """Generate short hash of URL."""
    return hashlib.md5(url.encode()).hexdigest()[:8]

def send_webhook(event_type, data):
    """Send webhook notification."""
    if not Config.WEBHOOK_URL:
        return
    try:
        import urllib.request
        payload = json.dumps({'event': event_type, 'timestamp': now_iso(), 'data': data}).encode()
        req = urllib.request.Request(Config.WEBHOOK_URL, data=payload,
                                      headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[WEBHOOK] Failed: {e}")
