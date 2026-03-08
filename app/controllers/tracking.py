"""
Naarad - Tracking Controller
Handles pixel open tracking and link click tracking.
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from time import time

from flask import Blueprint, request, Response, redirect, jsonify
from ..database import get_db, get_cursor, placeholder
from ..services.geo import get_geo_info
from ..services.ua import parse_user_agent
from ..utils import sanitize_id, hash_url, send_webhook, validate_redirect_url, now_iso
from ..config import Config

log = logging.getLogger(__name__)

bp_track = Blueprint('track', __name__)

# Transparent 1x1 PNG (hardcoded bytes — no file I/O per request)
PIXEL = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

# ── In-memory rate limiter ──────────────────────────────────────────────────
# Tracks hit counts per IP within rolling 60-second windows.
# Includes periodic eviction to prevent unbounded memory growth.
_rate_buckets: dict = defaultdict(list)  # ip -> [timestamps]
_rate_last_evict: float = 0.0
_RATE_EVICT_INTERVAL = 300.0  # Evict stale IPs every 5 minutes
_RATE_MAX_IPS = 100000  # Hard cap on tracked IPs


def _is_rate_limited(ip: str) -> bool:
    """Return True if this IP has exceeded RATE_LIMIT_PER_MINUTE in the past 60s."""
    global _rate_last_evict
    limit = Config.RATE_LIMIT_PER_MINUTE
    if not limit:
        return False
    now_ts = time()
    window = 60.0
    hits = _rate_buckets[ip]
    # Prune old hits outside the window
    hits[:] = [t for t in hits if now_ts - t < window]
    if len(hits) >= limit:
        return True
    hits.append(now_ts)

    # Periodic eviction of stale IPs to prevent memory leak (C-07)
    if now_ts - _rate_last_evict > _RATE_EVICT_INTERVAL:
        _rate_last_evict = now_ts
        stale_ips = [k for k, v in _rate_buckets.items() if not v or (now_ts - v[-1]) > window]
        for k in stale_ips:
            del _rate_buckets[k]
        # Hard cap: if still too many IPs, clear the oldest half
        if len(_rate_buckets) > _RATE_MAX_IPS:
            _rate_buckets.clear()
            log.warning("[RATE] Cleared rate limiter — exceeded %d IP cap", _RATE_MAX_IPS)

    return False


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_client_ip() -> str:
    """Get real client IP (supports proxies and CDNs), first wins."""
    for header in ['CF-Connecting-IP', 'X-Real-IP', 'X-Forwarded-For']:
        ip = request.headers.get(header)
        if ip:
            return ip.split(',')[0].strip()
    return request.remote_addr or ''


def extract_headers() -> dict:
    """Extract tracking-relevant request headers."""
    return {
        'referer':          request.headers.get('Referer', 'Direct'),
        'accept_language':  request.headers.get('Accept-Language', ''),
        'accept_encoding':  request.headers.get('Accept-Encoding', ''),
        'accept_header':    request.headers.get('Accept', ''),
        'connection_type':  request.headers.get('Connection', ''),
        'do_not_track':     request.headers.get('DNT', ''),
        'cache_control':    request.headers.get('Cache-Control', ''),
        'sec_ch_ua':        request.headers.get('Sec-CH-UA', ''),
        'sec_ch_ua_mobile': request.headers.get('Sec-CH-UA-Mobile', ''),
        'sec_ch_ua_platform': request.headers.get('Sec-CH-UA-Platform', ''),
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@bp_track.route('/favicon.ico')
def favicon():
    return Response(status=204)


@bp_track.route('/track')
@bp_track.route('/pixel')
@bp_track.route('/t/<track_id>')
def track_open(track_id=None):
    """Track email open with maximum data capture.
    
    PII fields (sender, recipient, subject) are NOT accepted via query params
    to avoid leaking them in URLs/logs. Use POST /api/track to pre-register
    metadata before sending the email.
    """
    P = placeholder()
    ip = get_client_ip()

    # Rate-limit check — still return pixel so email client doesn't hang
    if _is_rate_limited(ip):
        log.warning("[TRACK] Rate limit hit for ip=%s", ip)
        return Response(PIXEL, mimetype='image/png', headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Expires': '0',
        })

    track_id  = sanitize_id(track_id or request.args.get('id', 'unknown'))
    campaign_id = request.args.get('c') or request.args.get('campaign')

    # PII is no longer accepted from query params (C-06).
    # Pre-register metadata via POST /api/track before sending the email.
    sender = recipient = subject = sent_at = None

    geo     = get_geo_info(ip)
    ua      = request.headers.get('User-Agent', '')
    ua_info = parse_user_agent(ua)
    headers = extract_headers()
    timestamp = now_iso()

    conn   = get_db()
    cursor = get_cursor(conn)

    try:
        cursor.execute(f'SELECT id FROM tracks WHERE track_id = {P}', (track_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                f'UPDATE tracks SET open_count = open_count + 1, last_seen = {P} WHERE track_id = {P}',
                (timestamp, track_id)
            )
        else:
            # Derive column list dynamically — never hardcode a count
            cols = [
                'timestamp', 'track_id', 'campaign_id', 'sender', 'recipient', 'subject', 'sent_at',
                'ip_address', 'country', 'region', 'city', 'latitude', 'longitude',
                'timezone', 'isp', 'org', 'asn',
                'user_agent', 'browser', 'browser_version', 'os', 'os_version',
                'device_type', 'device_brand', 'is_mobile', 'is_bot',
                'referer', 'accept_language', 'accept_encoding', 'accept_header',
                'connection_type', 'do_not_track', 'cache_control',
                'sec_ch_ua', 'sec_ch_ua_mobile', 'sec_ch_ua_platform',
                'open_count', 'first_seen', 'last_seen',
            ]
            values = (
                timestamp, track_id, campaign_id, sender, recipient, subject, sent_at,
                ip, geo['country'], geo['region'], geo['city'], geo['lat'], geo['lon'],
                geo['timezone'], geo['isp'], geo.get('org', ''), geo.get('asn', ''),
                ua, ua_info['browser'], ua_info['browser_version'],
                ua_info['os'], ua_info['os_version'], ua_info['device_type'],
                ua_info['device_brand'], ua_info['is_mobile'], ua_info['is_bot'],
                headers['referer'], headers['accept_language'], headers['accept_encoding'],
                headers['accept_header'], headers['connection_type'], headers['do_not_track'],
                headers['cache_control'], headers['sec_ch_ua'], headers['sec_ch_ua_mobile'],
                headers['sec_ch_ua_platform'],
                1, timestamp, timestamp,
            )
            placeholders = ', '.join([P] * len(cols))
            col_names = ', '.join(cols)
            cursor.execute(
                f'INSERT INTO tracks ({col_names}) VALUES ({placeholders})',
                values
            )

        conn.commit()
    except Exception as e:
        log.error("[TRACK] DB error recording open for track_id=%s: %s", track_id, e)
        try:
            conn.rollback()
        except Exception:
            pass

    send_webhook('open', {
        'track_id': track_id,
        'location': f"{geo['city']}, {geo['country']}",
    })

    return Response(PIXEL, mimetype='image/png', headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Expires':       '0',
        'Accept-CH':     'Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform',
    })


@bp_track.route('/click/<track_id>/<path:target_url>')
@bp_track.route('/c/<track_id>/<path:target_url>')
def track_click(track_id, target_url):
    """Track link click and redirect — validates the target URL to prevent open redirect abuse."""
    from urllib.parse import unquote
    P = placeholder()

    track_id   = sanitize_id(track_id)
    target_url = unquote(target_url)

    # ── Open Redirect Prevention ─────────────────────────────────────────
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    safe_url = validate_redirect_url(target_url)
    if not safe_url:
        log.warning("[CLICK] Blocked invalid redirect target: %s", target_url)
        return jsonify({'error': 'Invalid redirect target'}), 400

    campaign_id = request.args.get('c')
    link_id     = hash_url(safe_url)

    ip      = get_client_ip()
    ua      = request.headers.get('User-Agent', '')
    ua_info = parse_user_agent(ua)
    geo     = get_geo_info(ip)
    referer = request.headers.get('Referer', 'Direct')
    timestamp = now_iso()

    conn   = get_db()
    cursor = get_cursor(conn)

    try:
        # ── Atomic click + track upsert ───────────────────────────────────
        click_cols = [
            'timestamp', 'track_id', 'campaign_id', 'link_id', 'target_url',
            'ip_address', 'country', 'city', 'user_agent', 'browser',
            'os', 'device_type', 'referer',
        ]
        click_vals = (
            timestamp, track_id, campaign_id, link_id, safe_url,
            ip, geo['country'], geo['city'],
            ua, ua_info['browser'], ua_info['os'], ua_info['device_type'], referer,
        )
        placeholders = ', '.join([P] * len(click_cols))
        cursor.execute(
            f"INSERT INTO clicks ({', '.join(click_cols)}) VALUES ({placeholders})",
            click_vals
        )

        # Check whether a track record already exists
        cursor.execute(
            f'SELECT id FROM tracks WHERE track_id = {P}', (track_id,)
        )
        if not cursor.fetchone():
            # Create a minimal track row for click-only recipients (pixel was blocked)
            track_cols = [
                'timestamp', 'track_id', 'campaign_id',
                'ip_address', 'country', 'region', 'city', 'latitude', 'longitude',
                'user_agent', 'browser', 'os', 'device_type',
                'first_seen', 'last_seen',
                'click_count', 'open_count', 'referer',
            ]
            track_vals = (
                timestamp, track_id, campaign_id,
                ip, geo['country'], geo['region'], geo['city'], geo['lat'], geo['lon'],
                ua, ua_info['browser'], ua_info['os'], ua_info['device_type'],
                timestamp, timestamp,
                1, 0, referer,
            )
            placeholders = ', '.join([P] * len(track_cols))
            cursor.execute(
                f"INSERT INTO tracks ({', '.join(track_cols)}) VALUES ({placeholders})",
                track_vals
            )
        else:
            cursor.execute(
                f'UPDATE tracks SET click_count = click_count + 1, last_seen = {P} WHERE track_id = {P}',
                (timestamp, track_id)
            )

        conn.commit()
    except Exception as e:
        log.error("[CLICK] DB error for track_id=%s: %s", track_id, e)
        try:
            conn.rollback()
        except Exception:
            pass

    send_webhook('click', {'track_id': track_id, 'url': safe_url})

    return redirect(safe_url)
