"""
naarad - Tracking Controller
Handles pixel open tracking and link click tracking.

Enhanced with full analytics:
  - Date / time / day-of-week
  - IP address + ISP / ASN / org
  - Geo: country, region, city, lat/lon, timezone
  - Device: type, brand, OS, browser / email-client, version
  - Email metadata: sender, recipient, subject, campaign_id, sent_at
  - Open counts: total, unique, repeated
  - Click counts: total, unique
  - Forward detection: opens from new IP / device / location vs first-seen
  - Full header capture: language, encoding, DNT, cache-control, Sec-CH-UA*
"""
import hashlib
import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone
from time import time

from flask import Blueprint, request, Response, redirect, jsonify, current_app
from ..database import get_db, get_cursor, placeholder
from ..services.geo import get_geo_info, enrich_track_async
from ..services.ua import parse_user_agent
from ..utils import sanitize_id, hash_url, send_webhook, validate_redirect_url, now_iso
from ..config import Config

log = logging.getLogger(__name__)

bp_track = Blueprint('track', __name__)

# Transparent 1×1 PNG — no file I/O per request
PIXEL = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

# ── In-memory rate limiter (thread-safe) ─────────────────────────────
_rate_lock = threading.Lock()
_rate_buckets: dict = defaultdict(list)   # ip -> [timestamps]
_rate_last_evict: float = 0.0
_RATE_EVICT_INTERVAL = 300.0              # evict stale IPs every 5 min
_RATE_MAX_IPS        = 100_000            # hard cap on tracked IPs


def _is_rate_limited(ip: str) -> bool:
    """Return True if this IP has exceeded RATE_LIMIT_PER_MINUTE in the past 60 s."""
    global _rate_last_evict
    limit = Config.RATE_LIMIT_PER_MINUTE
    if not limit:
        return False
    now_ts = time()
    window = 60.0

    with _rate_lock:
        hits = _rate_buckets[ip]
        hits[:] = [t for t in hits if now_ts - t < window]
        if len(hits) >= limit:
            return True
        hits.append(now_ts)

        if now_ts - _rate_last_evict > _RATE_EVICT_INTERVAL:
            _rate_last_evict = now_ts
            stale = [k for k, v in _rate_buckets.items()
                     if not v or (now_ts - v[-1]) > window]
            for k in stale:
                del _rate_buckets[k]
            if len(_rate_buckets) > _RATE_MAX_IPS:
                _rate_buckets.clear()
                log.warning("[RATE] Cleared rate limiter — exceeded %d IP cap", _RATE_MAX_IPS)

    return False


# ── Helpers ──────────────────────────────────────────────────────────

def get_client_ip() -> str:
    """Return real client IP, honouring ProxyFix when configured."""
    if Config.TRUSTED_PROXY_COUNT > 0:
        return request.remote_addr or ''
    for header in ('CF-Connecting-IP', 'X-Real-IP', 'X-Forwarded-For'):
        ip = request.headers.get(header)
        if ip:
            return ip.split(',')[0].strip()
    return request.remote_addr or ''


def extract_headers() -> dict:
    """Capture all tracking-relevant request headers."""
    return {
        'referer':              request.headers.get('Referer', 'Direct'),
        'accept_language':      request.headers.get('Accept-Language', ''),
        'accept_encoding':      request.headers.get('Accept-Encoding', ''),
        'accept_header':        request.headers.get('Accept', ''),
        'connection_type':      request.headers.get('Connection', ''),
        'do_not_track':         request.headers.get('DNT', ''),
        'cache_control':        request.headers.get('Cache-Control', ''),
        'sec_ch_ua':            request.headers.get('Sec-CH-UA', ''),
        'sec_ch_ua_mobile':     request.headers.get('Sec-CH-UA-Mobile', ''),
        'sec_ch_ua_platform':   request.headers.get('Sec-CH-UA-Platform', ''),
    }


def _now_full() -> dict:
    """
    Return a rich timestamp bundle for a single moment in time.

    Keys
    ----
    iso          : ISO-8601 UTC string  (stored in DB as `timestamp`)
    date         : YYYY-MM-DD
    time         : HH:MM:SS UTC
    day_of_week  : Monday … Sunday
    unix_ms      : integer epoch milliseconds (sortable, timezone-free)
    """
    now = datetime.now(tz=timezone.utc)
    return {
        'iso':         now.isoformat(timespec='seconds'),
        'date':        now.strftime('%Y-%m-%d'),
        'time':        now.strftime('%H:%M:%S'),
        'day_of_week': now.strftime('%A'),
        'unix_ms':     int(now.timestamp() * 1000),
    }


def _fingerprint(ip: str, ua: str, device_type: str, browser: str) -> str:
    """
    Lightweight fingerprint used for forward-detection.
    Hashed so raw values are never stored twice.
    """
    raw = f"{ip}|{ua}|{device_type}|{browser}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _detect_forward(cursor, P: str, track_id: str,
                    ip: str, geo: dict, ua_info: dict) -> bool:
    """
    Heuristic: if we already have a track record for this track_id
    AND the current IP / country / device_type doesn't match the first-seen
    record, flag this open as a probable forward.
    """
    cursor.execute(
        f'SELECT ip_address, country, device_type FROM tracks WHERE track_id = {P}',
        (track_id,)
    )
    row = cursor.fetchone()
    if not row:
        return False
    orig_ip, orig_country, orig_device = (
        (row['ip_address'], row['country'], row['device_type'])
        if hasattr(row, 'keys')
        else row
    )
    # Different IP AND (different country OR different device class) → likely forwarded
    if ip != orig_ip and (
        geo.get('country') != orig_country or
        ua_info.get('device_type') != orig_device
    ):
        return True
    return False


# ── Routes ────────────────────────────────────────────────────────────

@bp_track.route('/favicon.ico')
def favicon():
    return Response(status=204)


@bp_track.route('/track')
@bp_track.route('/pixel')
@bp_track.route('/t/<track_id>')
def track_open(track_id=None):
    """
    Track email open — returns a 1×1 tracking pixel immediately.

    Analytics captured per open
    ────────────────────────────
    Timestamp   : ISO date-time (UTC), date, time, day-of-week, unix_ms
    Location    : country, region, city, lat, lon, timezone
    Network     : IP address, ISP, org, ASN
    Device      : UA string, browser, browser_version, OS, OS_version,
                  device_type, device_brand, is_mobile, is_bot
    Email meta  : sender, recipient, subject, campaign_id, sent_at
    Headers     : referer, accept_language, accept_encoding, accept_header,
                  connection_type, do_not_track, cache_control, Sec-CH-UA*
    Counters    : open_count (total per track_id), is_repeat, is_forward
    """
    P  = placeholder()
    ip = get_client_ip()

    # Rate-limit — still return pixel so email clients don't hang
    if _is_rate_limited(ip):
        log.warning("[TRACK] Rate limit hit for ip=%s", ip)
        return Response(PIXEL, mimetype='image/png', headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Expires': '0',
        })

    # ── Collect all data ─────────────────────────────────────────
    ts        = _now_full()
    track_id  = sanitize_id(track_id or request.args.get('id', 'unknown'))
    campaign_id = request.args.get('c') or request.args.get('campaign')

    # Email metadata — accepted via query params (embed in pixel URL at send time)
    sender    = request.args.get('sender')
    recipient = request.args.get('recipient')
    subject   = request.args.get('subject')
    sent_at   = request.args.get('sent_at')

    geo     = get_geo_info(ip)          # fast cache path; async enrichment below
    ua      = request.headers.get('User-Agent', '')
    ua_info = parse_user_agent(ua)
    headers = extract_headers()

    # Enrich geo asynchronously for cache misses — pixel is returned before this completes
    enrich_track_async(current_app._get_current_object(), track_id, ip)

    conn   = get_db()
    cursor = get_cursor(conn)

    try:
        cursor.execute(f'SELECT id, open_count FROM tracks WHERE track_id = {P}', (track_id,))
        existing = cursor.fetchone()

        if existing:
            # ── Repeat open (or first real open on a pre-registered track) ──
            existing_id    = existing[0] if isinstance(existing, (list, tuple)) else existing['id']
            existing_count = existing[1] if isinstance(existing, (list, tuple)) else existing['open_count']

            is_forward = _detect_forward(cursor, P, track_id, ip, geo, ua_info)

            # Use COALESCE so pre-registered tracks get their NULL fields
            # filled on the first real pixel open, without overwriting
            # data that already exists from a previous real open.
            cursor.execute(
                f'''UPDATE tracks
                    SET open_count    = open_count + 1,
                        last_seen     = {P},
                        is_repeat     = CASE WHEN open_count > 0 THEN 1 ELSE 0 END,
                        forward_count = COALESCE(forward_count, 0) + {1 if is_forward else 0},
                        -- Timestamp detail (fill if first real open)
                        open_date     = COALESCE(open_date, {P}),
                        open_time     = COALESCE(open_time, {P}),
                        day_of_week   = COALESCE(day_of_week, {P}),
                        unix_ms       = COALESCE(unix_ms, {P}),
                        -- Network / geo
                        ip_address    = COALESCE(ip_address, {P}),
                        country       = COALESCE(NULLIF(country, 'Local'), NULLIF(country, 'Unknown'), {P}),
                        region        = COALESCE(NULLIF(region,  'Local'), NULLIF(region,  'Unknown'), {P}),
                        city          = COALESCE(NULLIF(city,    'Local'), NULLIF(city,    'Unknown'), {P}),
                        latitude      = CASE WHEN latitude IS NULL OR latitude = 0 THEN {P} ELSE latitude END,
                        longitude     = CASE WHEN longitude IS NULL OR longitude = 0 THEN {P} ELSE longitude END,
                        timezone      = COALESCE(NULLIF(timezone, 'Local'), NULLIF(timezone, 'Unknown'), {P}),
                        isp           = COALESCE(NULLIF(isp,      'Local'), NULLIF(isp,      'Unknown'), {P}),
                        org           = COALESCE(NULLIF(org, ''), {P}),
                        asn           = COALESCE(NULLIF(asn, ''), {P}),
                        -- Device / UA
                        user_agent    = COALESCE(user_agent, {P}),
                        browser       = COALESCE(NULLIF(browser, 'Unknown'), {P}),
                        browser_version = COALESCE(browser_version, {P}),
                        os            = COALESCE(NULLIF(os, 'Unknown'), {P}),
                        os_version    = COALESCE(os_version, {P}),
                        device_type   = COALESCE(NULLIF(device_type, 'Unknown'), {P}),
                        device_brand  = COALESCE(NULLIF(device_brand, 'Unknown'), {P}),
                        is_mobile     = COALESCE(is_mobile, {P}),
                        is_bot        = COALESCE(is_bot, {P}),
                        -- Headers
                        referer       = COALESCE(NULLIF(referer, 'Direct'), {P}),
                        accept_language = COALESCE(NULLIF(accept_language, ''), {P}),
                        accept_encoding = COALESCE(NULLIF(accept_encoding, ''), {P}),
                        accept_header   = COALESCE(NULLIF(accept_header, ''), {P}),
                        connection_type = COALESCE(NULLIF(connection_type, ''), {P}),
                        do_not_track    = COALESCE(NULLIF(do_not_track, ''), {P}),
                        cache_control   = COALESCE(NULLIF(cache_control, ''), {P}),
                        sec_ch_ua           = COALESCE(NULLIF(sec_ch_ua, ''), {P}),
                        sec_ch_ua_mobile    = COALESCE(NULLIF(sec_ch_ua_mobile, ''), {P}),
                        sec_ch_ua_platform  = COALESCE(NULLIF(sec_ch_ua_platform, ''), {P}),
                        -- Email metadata (fill if not pre-registered)
                        sender        = COALESCE(NULLIF(sender, ''), {P}),
                        recipient     = COALESCE(NULLIF(recipient, ''), {P}),
                        subject       = COALESCE(NULLIF(subject, ''), {P}),
                        sent_at       = COALESCE(NULLIF(sent_at, ''), {P}),
                        campaign_id   = COALESCE(campaign_id, {P})
                    WHERE track_id = {P}''',
                (
                    ts['iso'],
                    # Timestamp detail
                    ts['date'], ts['time'], ts['day_of_week'], ts['unix_ms'],
                    # Network / geo
                    ip,
                    geo['country'], geo['region'], geo['city'],
                    geo['lat'], geo['lon'],
                    geo['timezone'], geo['isp'],
                    geo.get('org', ''), geo.get('asn', ''),
                    # Device / UA
                    ua,
                    ua_info['browser'], ua_info['browser_version'],
                    ua_info['os'], ua_info['os_version'],
                    ua_info['device_type'], ua_info['device_brand'],
                    ua_info['is_mobile'], ua_info['is_bot'],
                    # Headers
                    headers['referer'], headers['accept_language'],
                    headers['accept_encoding'], headers['accept_header'],
                    headers['connection_type'], headers['do_not_track'],
                    headers['cache_control'], headers['sec_ch_ua'],
                    headers['sec_ch_ua_mobile'], headers['sec_ch_ua_platform'],
                    # Email metadata
                    sender, recipient, subject, sent_at,
                    campaign_id,
                    # WHERE
                    track_id,
                )
            )

            # Record individual open event in open_events table
            _insert_open_event(cursor, P, {
                'track_id': track_id, 'campaign_id': campaign_id,
                'ts': ts, 'ip': ip, 'geo': geo, 'ua': ua,
                'ua_info': ua_info, 'headers': headers,
                'sender': sender, 'recipient': recipient,
                'subject': subject, 'sent_at': sent_at,
                'is_repeat': 1, 'is_forward': int(is_forward),
            })

        else:
            # ── First open ───────────────────────────────────────
            cols = [
                # Timestamp fields
                'timestamp', 'open_date', 'open_time', 'day_of_week', 'unix_ms',
                # Identity
                'track_id', 'campaign_id',
                # Email metadata
                'sender', 'recipient', 'subject', 'sent_at',
                # Network / geo
                'ip_address',
                'country', 'region', 'city', 'latitude', 'longitude',
                'timezone', 'isp', 'org', 'asn',
                # Device / UA
                'user_agent', 'browser', 'browser_version',
                'os', 'os_version', 'device_type', 'device_brand',
                'is_mobile', 'is_bot',
                # Request headers
                'referer', 'accept_language', 'accept_encoding', 'accept_header',
                'connection_type', 'do_not_track', 'cache_control',
                'sec_ch_ua', 'sec_ch_ua_mobile', 'sec_ch_ua_platform',
                # Counters / flags
                'open_count', 'click_count', 'forward_count',
                'is_repeat', 'is_forward',
                'first_seen', 'last_seen',
            ]
            values = (
                ts['iso'], ts['date'], ts['time'], ts['day_of_week'], ts['unix_ms'],
                track_id, campaign_id,
                sender, recipient, subject, sent_at,
                ip,
                geo['country'], geo['region'], geo['city'],
                geo['lat'], geo['lon'],
                geo['timezone'], geo['isp'],
                geo.get('org', ''), geo.get('asn', ''),
                ua,
                ua_info['browser'], ua_info['browser_version'],
                ua_info['os'], ua_info['os_version'],
                ua_info['device_type'], ua_info['device_brand'],
                ua_info['is_mobile'], ua_info['is_bot'],
                headers['referer'], headers['accept_language'],
                headers['accept_encoding'], headers['accept_header'],
                headers['connection_type'], headers['do_not_track'],
                headers['cache_control'], headers['sec_ch_ua'],
                headers['sec_ch_ua_mobile'], headers['sec_ch_ua_platform'],
                1, 0, 0,    # open_count, click_count, forward_count
                0, 0,       # is_repeat, is_forward
                ts['iso'], ts['iso'],
            )
            placeholders = ', '.join([P] * len(cols))
            cursor.execute(
                f"INSERT INTO tracks ({', '.join(cols)}) VALUES ({placeholders})",
                values
            )

            # Record first open event
            _insert_open_event(cursor, P, {
                'track_id': track_id, 'campaign_id': campaign_id,
                'ts': ts, 'ip': ip, 'geo': geo, 'ua': ua,
                'ua_info': ua_info, 'headers': headers,
                'sender': sender, 'recipient': recipient,
                'subject': subject, 'sent_at': sent_at,
                'is_repeat': 0, 'is_forward': 0,
            })

        conn.commit()
        log.info(
            "[TRACK] Open recorded: track_id=%s ip=%s country=%s device=%s browser=%s",
            track_id, ip[:10] + '***', geo.get('country', '?'),
            ua_info.get('device_type', '?'), ua_info.get('browser', '?'),
        )

    except Exception as e:
        log.error("[TRACK] DB error for track_id=%s: %s", track_id, e)
        try:
            conn.rollback()
        except Exception:
            pass

    send_webhook('open', {
        'track_id':   track_id,
        'sender':     sender,
        'recipient':  recipient,
        'subject':    subject,
        'date':       ts['date'],
        'time':       ts['time'],
        'day':        ts['day_of_week'],
        'ip':         ip,
        'isp':        geo.get('isp', ''),
        'location':   f"{geo['city']}, {geo['region']}, {geo['country']}",
        'lat':        geo.get('lat'),
        'lon':        geo.get('lon'),
        'device':     ua_info.get('device_type', ''),
        'browser':    ua_info.get('browser', ''),
        'os':         ua_info.get('os', ''),
    })

    return Response(PIXEL, mimetype='image/png', headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Expires':       '0',
        'Accept-CH':     'Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform',
    })


def _insert_open_event(cursor, P: str, ctx: dict) -> None:
    """
    Insert one row into ``open_events`` — a per-open log that keeps every
    individual open (even repeats and forwards) so dashboards can render
    timeline charts and unique-vs-repeat breakdowns.
    """
    ts      = ctx['ts']
    geo     = ctx['geo']
    ua_info = ctx['ua_info']
    headers = ctx['headers']

    cols = [
        'timestamp', 'open_date', 'open_time', 'day_of_week', 'unix_ms',
        'track_id', 'campaign_id',
        'sender', 'recipient', 'subject', 'sent_at',
        'ip_address', 'country', 'region', 'city', 'latitude', 'longitude',
        'timezone', 'isp', 'org', 'asn',
        'user_agent', 'browser', 'browser_version',
        'os', 'os_version', 'device_type', 'device_brand',
        'is_mobile', 'is_bot',
        'referer', 'accept_language',
        'is_repeat', 'is_forward',
        'fingerprint',
    ]
    fp = _fingerprint(ctx['ip'], ctx['ua'], ua_info['device_type'], ua_info['browser'])
    values = (
        ts['iso'], ts['date'], ts['time'], ts['day_of_week'], ts['unix_ms'],
        ctx['track_id'], ctx['campaign_id'],
        ctx['sender'], ctx['recipient'], ctx['subject'], ctx['sent_at'],
        ctx['ip'],
        geo['country'], geo['region'], geo['city'],
        geo['lat'], geo['lon'],
        geo['timezone'], geo['isp'],
        geo.get('org', ''), geo.get('asn', ''),
        ctx['ua'],
        ua_info['browser'], ua_info['browser_version'],
        ua_info['os'], ua_info['os_version'],
        ua_info['device_type'], ua_info['device_brand'],
        ua_info['is_mobile'], ua_info['is_bot'],
        headers['referer'], headers['accept_language'],
        ctx['is_repeat'], ctx['is_forward'],
        fp,
    )
    placeholders = ', '.join([P] * len(cols))
    cursor.execute(
        f"INSERT INTO open_events ({', '.join(cols)}) VALUES ({placeholders})",
        values
    )


@bp_track.route('/click/<track_id>/<path:target_url>')
@bp_track.route('/c/<track_id>/<path:target_url>')
def track_click(track_id, target_url):
    """
    Track link click and redirect.

    Analytics captured per click
    ─────────────────────────────
    Timestamp   : ISO date-time (UTC), date, time, day-of-week, unix_ms
    Location    : country, region, city, lat, lon
    Network     : IP address, ISP, org, ASN
    Device      : UA, browser, OS, device_type
    Email meta  : sender, recipient, subject, campaign_id, link_id, target_url
    Counters    : click_count incremented on parent tracks row;
                  unique clicks tracked via fingerprint
    """
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

    ts          = _now_full()
    campaign_id = request.args.get('c')
    link_id     = hash_url(safe_url)

    sender    = request.args.get('sender')
    recipient = request.args.get('recipient')
    subject   = request.args.get('subject')
    sent_at   = request.args.get('sent_at')

    ip      = get_client_ip()
    ua      = request.headers.get('User-Agent', '')
    ua_info = parse_user_agent(ua)
    geo     = get_geo_info(ip)
    referer = request.headers.get('Referer', 'Direct')
    fp      = _fingerprint(ip, ua, ua_info['device_type'], ua_info['browser'])

    conn   = get_db()
    cursor = get_cursor(conn)

    try:
        # ── clicks table ─────────────────────────────────────────────────
        click_cols = [
            'timestamp', 'click_date', 'click_time', 'day_of_week', 'unix_ms',
            'track_id', 'campaign_id', 'link_id', 'target_url',
            'ip_address', 'country', 'region', 'city', 'latitude', 'longitude',
            'isp', 'org', 'asn',
            'user_agent', 'browser', 'browser_version',
            'os', 'os_version', 'device_type', 'device_brand',
            'is_mobile', 'is_bot',
            'referer',
            'sender', 'recipient', 'subject', 'sent_at',
            'fingerprint',
        ]
        click_vals = (
            ts['iso'], ts['date'], ts['time'], ts['day_of_week'], ts['unix_ms'],
            track_id, campaign_id, link_id, safe_url,
            ip, geo['country'], geo['region'], geo['city'],
            geo['lat'], geo['lon'],
            geo['isp'], geo.get('org', ''), geo.get('asn', ''),
            ua,
            ua_info['browser'], ua_info['browser_version'],
            ua_info['os'], ua_info['os_version'],
            ua_info['device_type'], ua_info['device_brand'],
            ua_info['is_mobile'], ua_info['is_bot'],
            referer,
            sender, recipient, subject, sent_at,
            fp,
        )
        placeholders = ', '.join([P] * len(click_cols))
        cursor.execute(
            f"INSERT INTO clicks ({', '.join(click_cols)}) VALUES ({placeholders})",
            click_vals
        )

        # ── tracks table upsert ──────────────────────────────────────────
        cursor.execute(f'SELECT id FROM tracks WHERE track_id = {P}', (track_id,))
        if not cursor.fetchone():
            # Pixel was blocked — create minimal track row from click data
            track_cols = [
                'timestamp', 'open_date', 'open_time', 'day_of_week', 'unix_ms',
                'track_id', 'campaign_id',
                'sender', 'recipient', 'subject', 'sent_at',
                'ip_address', 'country', 'region', 'city', 'latitude', 'longitude',
                'isp', 'org', 'asn',
                'user_agent', 'browser', 'browser_version',
                'os', 'os_version', 'device_type', 'device_brand',
                'is_mobile', 'is_bot',
                'referer',
                'open_count', 'click_count', 'forward_count',
                'is_repeat', 'is_forward',
                'first_seen', 'last_seen',
            ]
            track_vals = (
                ts['iso'], ts['date'], ts['time'], ts['day_of_week'], ts['unix_ms'],
                track_id, campaign_id,
                sender, recipient, subject, sent_at,
                ip, geo['country'], geo['region'], geo['city'],
                geo['lat'], geo['lon'],
                geo['isp'], geo.get('org', ''), geo.get('asn', ''),
                ua,
                ua_info['browser'], ua_info['browser_version'],
                ua_info['os'], ua_info['os_version'],
                ua_info['device_type'], ua_info['device_brand'],
                ua_info['is_mobile'], ua_info['is_bot'],
                referer,
                0, 1, 0,  # open_count, click_count, forward_count
                0, 0,     # is_repeat, is_forward
                ts['iso'], ts['iso'],
            )
            placeholders = ', '.join([P] * len(track_cols))
            cursor.execute(
                f"INSERT INTO tracks ({', '.join(track_cols)}) VALUES ({placeholders})",
                track_vals
            )
        else:
            cursor.execute(
                f'''UPDATE tracks
                    SET click_count = click_count + 1,
                        last_seen   = {P},
                        -- Network / geo
                        ip_address    = COALESCE(ip_address, {P}),
                        country       = COALESCE(NULLIF(country, 'Local'), NULLIF(country, 'Unknown'), {P}),
                        region        = COALESCE(NULLIF(region,  'Local'), NULLIF(region,  'Unknown'), {P}),
                        city          = COALESCE(NULLIF(city,    'Local'), NULLIF(city,    'Unknown'), {P}),
                        latitude      = CASE WHEN latitude IS NULL OR latitude = 0 THEN {P} ELSE latitude END,
                        longitude     = CASE WHEN longitude IS NULL OR longitude = 0 THEN {P} ELSE longitude END,
                        timezone      = COALESCE(NULLIF(timezone, 'Local'), NULLIF(timezone, 'Unknown'), {P}),
                        isp           = COALESCE(NULLIF(isp,      'Local'), NULLIF(isp,      'Unknown'), {P}),
                        org           = COALESCE(NULLIF(org, ''), {P}),
                        asn           = COALESCE(NULLIF(asn, ''), {P}),
                        -- Device / UA
                        user_agent    = COALESCE(user_agent, {P}),
                        browser       = COALESCE(NULLIF(browser, 'Unknown'), {P}),
                        browser_version = COALESCE(browser_version, {P}),
                        os            = COALESCE(NULLIF(os, 'Unknown'), {P}),
                        os_version    = COALESCE(os_version, {P}),
                        device_type   = COALESCE(NULLIF(device_type, 'Unknown'), {P}),
                        device_brand  = COALESCE(NULLIF(device_brand, 'Unknown'), {P}),
                        is_mobile     = COALESCE(is_mobile, {P}),
                        is_bot        = COALESCE(is_bot, {P})
                    WHERE track_id  = {P}''',
                (
                    ts['iso'],
                    ip, geo['country'], geo['region'], geo['city'],
                    geo['lat'], geo['lon'], geo['timezone'], geo['isp'],
                    geo.get('org', ''), geo.get('asn', ''),
                    ua, ua_info['browser'], ua_info['browser_version'],
                    ua_info['os'], ua_info['os_version'], ua_info['device_type'],
                    ua_info['device_brand'], ua_info['is_mobile'], ua_info['is_bot'],
                    track_id
                )
            )

        conn.commit()
        log.info(
            "[CLICK] Click recorded: track_id=%s url=%s ip=%s device=%s",
            track_id, safe_url[:60], ip[:10] + '***', ua_info.get('device_type', '?'),
        )

    except Exception as e:
        log.error("[CLICK] DB error for track_id=%s: %s", track_id, e)
        try:
            conn.rollback()
        except Exception:
            pass

    send_webhook('click', {
        'track_id':  track_id,
        'url':       safe_url,
        'sender':    sender,
        'recipient': recipient,
        'date':      ts['date'],
        'time':      ts['time'],
        'day':       ts['day_of_week'],
        'ip':        ip,
        'isp':       geo.get('isp', ''),
        'location':  f"{geo['city']}, {geo['region']}, {geo['country']}",
        'lat':       geo.get('lat'),
        'lon':       geo.get('lon'),
        'device':    ua_info.get('device_type', ''),
        'browser':   ua_info.get('browser', ''),
        'os':        ua_info.get('os', ''),
    })

    return redirect(safe_url)


# ── Analytics summary endpoint ────────────────────────────────────────

@bp_track.route('/analytics/<track_id>', methods=['GET'])
def get_analytics(track_id):
    """
    Return a JSON summary for one track_id.

    Response shape
    ──────────────
    {
      "track_id":        "...",
      "sender":          "...",
      "recipient":       "...",
      "subject":         "...",
      "sent_at":         "...",
      "campaign_id":     "...",
      "first_seen":      "ISO",
      "last_seen":       "ISO",
      "total_opens":     N,
      "unique_opens":    N,   ← distinct fingerprints in open_events
      "repeat_opens":    N,
      "forward_opens":   N,
      "total_clicks":    N,
      "unique_clicks":   N,   ← distinct fingerprints in clicks
      "devices":         {...},
      "browsers":        {...},
      "countries":       {...},
      "opens_timeline":  [...],
      "clicks_timeline": [...]
    }
    """
    P  = placeholder()
    tid = sanitize_id(track_id)
    conn   = get_db()
    cursor = get_cursor(conn)

    # ── Master track row ─────────────────────────────────────────────────
    cursor.execute(
        f'''SELECT track_id, sender, recipient, subject, sent_at,
                   campaign_id, first_seen, last_seen,
                   open_count, click_count, forward_count
            FROM tracks WHERE track_id = {P}''',
        (tid,)
    )
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': 'track_id not found'}), 404

    def val(r, idx, key):
        return r[key] if hasattr(r, 'keys') else r[idx]

    summary = {
        'track_id':    val(row, 0, 'track_id'),
        'sender':      val(row, 1, 'sender'),
        'recipient':   val(row, 2, 'recipient'),
        'subject':     val(row, 3, 'subject'),
        'sent_at':     val(row, 4, 'sent_at'),
        'campaign_id': val(row, 5, 'campaign_id'),
        'first_seen':  val(row, 6, 'first_seen'),
        'last_seen':   val(row, 7, 'last_seen'),
        'total_opens': val(row, 8, 'open_count'),
        'total_clicks': val(row, 9, 'click_count'),
        'forward_opens': val(row, 10, 'forward_count'),
    }

    # ── Unique / repeat opens from open_events ────────────────────────────
    cursor.execute(
        f'SELECT COUNT(DISTINCT fingerprint) FROM open_events WHERE track_id = {P}',
        (tid,)
    )
    r = cursor.fetchone()
    summary['unique_opens'] = r[0] if r else 0
    summary['repeat_opens'] = max(0, summary['total_opens'] - summary['unique_opens'])

    # ── Unique clicks ─────────────────────────────────────────────────────
    cursor.execute(
        f'SELECT COUNT(DISTINCT fingerprint) FROM clicks WHERE track_id = {P}',
        (tid,)
    )
    r = cursor.fetchone()
    summary['unique_clicks'] = r[0] if r else 0

    # ── Device breakdown ──────────────────────────────────────────────────
    cursor.execute(
        f'''SELECT device_type, COUNT(*) as cnt
            FROM open_events WHERE track_id = {P}
            GROUP BY device_type''',
        (tid,)
    )
    summary['devices'] = {
        (r['device_type'] if hasattr(r, 'keys') else r[0]): (r['cnt'] if hasattr(r, 'keys') else r[1])
        for r in cursor.fetchall()
    }

    # ── Browser breakdown ─────────────────────────────────────────────────
    cursor.execute(
        f'''SELECT browser, COUNT(*) as cnt
            FROM open_events WHERE track_id = {P}
            GROUP BY browser''',
        (tid,)
    )
    summary['browsers'] = {
        (r['browser'] if hasattr(r, 'keys') else r[0]): (r['cnt'] if hasattr(r, 'keys') else r[1])
        for r in cursor.fetchall()
    }

    # ── Country breakdown ─────────────────────────────────────────────────
    cursor.execute(
        f'''SELECT country, COUNT(*) as cnt
            FROM open_events WHERE track_id = {P}
            GROUP BY country''',
        (tid,)
    )
    summary['countries'] = {
        (r['country'] if hasattr(r, 'keys') else r[0]): (r['cnt'] if hasattr(r, 'keys') else r[1])
        for r in cursor.fetchall()
    }

    # ── Opens timeline (per day) ──────────────────────────────────────────
    cursor.execute(
        f'''SELECT open_date, COUNT(*) as cnt
            FROM open_events WHERE track_id = {P}
            GROUP BY open_date ORDER BY open_date''',
        (tid,)
    )
    summary['opens_timeline'] = [
        {'date': (r['open_date'] if hasattr(r, 'keys') else r[0]),
         'count': (r['cnt'] if hasattr(r, 'keys') else r[1])}
        for r in cursor.fetchall()
    ]

    # ── Clicks timeline (per day) ─────────────────────────────────────────
    cursor.execute(
        f'''SELECT click_date, COUNT(*) as cnt
            FROM clicks WHERE track_id = {P}
            GROUP BY click_date ORDER BY click_date''',
        (tid,)
    )
    summary['clicks_timeline'] = [
        {'date': (r['click_date'] if hasattr(r, 'keys') else r[0]),
         'count': (r['cnt'] if hasattr(r, 'keys') else r[1])}
        for r in cursor.fetchall()
    ]

    return jsonify(summary)



