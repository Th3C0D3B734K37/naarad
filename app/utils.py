"""
naarad - Utility Functions
"""
import re
import hmac
import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse
from .config import Config

log = logging.getLogger(__name__)


def now():
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def now_iso():
    """Get current UTC time as ISO string."""
    return now().isoformat()


def sanitize_id(track_id):
    """
    Sanitize and validate track ID.
    Allows only: alphanumeric, hyphen, underscore.
    """
    if not track_id:
        return 'unknown'
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '', str(track_id))
    return cleaned[:100] if cleaned else 'unknown'


def validate_email(email):
    """Check if string looks like an email."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_redirect_url(url):
    """
    Validate that a redirect URL is a safe absolute HTTP/HTTPS URL.
    Rejects URLs with embedded credentials (@), protocol-relative tricks,
    and non-standard schemes. Returns the sanitised URL or None if invalid.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return None
        if not parsed.netloc:
            return None
        # Block embedded credentials (user:pass@host) — phishing vector
        if '@' in parsed.netloc:
            return None
        # Block protocol-relative or empty-host tricks
        if parsed.netloc.startswith('/') or parsed.netloc.startswith('\\'):
            return None
        # Ensure the host contains at least one dot (or is localhost)
        host = parsed.hostname
        if not host:
            return None
        if '.' not in host and host not in ('localhost',):
            return None
        return url
    except Exception:
        return None


def hash_url(url):
    """Generate short hash of URL using SHA-256 (16-char hex = 64-bit)."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def safe_str_compare(a, b):
    """Timing-safe string comparison to prevent side-channel attacks."""
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def send_webhook(event_type, data):
    """Send webhook notification asynchronously so it never blocks the request."""
    if not Config.WEBHOOK_URL:
        return

    def _send():
        try:
            import urllib.request
            payload = json.dumps({
                'event': event_type,
                'timestamp': now_iso(),
                'data': data
            }).encode()
            headers = {'Content-Type': 'application/json'}
            if Config.WEBHOOK_SECRET:
                # S-06: Send HMAC signature, not the raw secret
                signature = hmac.new(
                    Config.WEBHOOK_SECRET.encode('utf-8'),
                    payload,
                    hashlib.sha256
                ).hexdigest()
                headers['X-Webhook-Signature'] = f'sha256={signature}'
            req = urllib.request.Request(
                Config.WEBHOOK_URL, data=payload, headers=headers
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            log.warning("[WEBHOOK] Failed to deliver %s event: %s", event_type, e)

    # Fire-and-forget in a daemon thread — does not block the HTTP response
    t = threading.Thread(target=_send, daemon=True)
    t.start()
