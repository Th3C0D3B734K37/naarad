"""
naarad - Geolocation Service
IP geolocation with caching, rate-limit handling, circuit breaker, and proper private IP detection.
"""

import json
import logging
import ipaddress
import threading
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from ..config import Config
from ..database import get_db, get_cursor, placeholder, USE_POSTGRES
from ..utils import now, now_iso

log = logging.getLogger(__name__)


# Private / non-routable IPv4 networks
_PRIVATE_NETS_V4 = [
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('100.64.0.0/10'),   # CGNAT
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),  # Link-local
    ipaddress.ip_network('172.16.0.0/12'),   # Correct private range
    ipaddress.ip_network('192.0.0.0/24'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('198.18.0.0/15'),
    ipaddress.ip_network('198.51.100.0/24'),
    ipaddress.ip_network('203.0.113.0/24'),
    ipaddress.ip_network('240.0.0.0/4'),
    ipaddress.ip_network('255.255.255.255/32'),
]

_UNKNOWN_GEO = {
    'country': 'Unknown', 'region': 'Unknown', 'city': 'Unknown',
    'lat': 0.0, 'lon': 0.0, 'timezone': 'Unknown', 'isp': 'Unknown',
    'org': '', 'asn': ''
}

_LOCAL_GEO = {
    'country': 'Local', 'region': 'Local', 'city': 'Local',
    'lat': 0.0, 'lon': 0.0, 'timezone': 'Local', 'isp': 'Local',
    'org': '', 'asn': ''
}

# ── Circuit Breaker State (R-03) ─────────────────────────────────────────
_cb_lock = threading.Lock()
_cb_failures = 0
_cb_last_failure = 0.0          # time.time() of last failure
_CB_THRESHOLD = 3               # Open circuit after N consecutive failures
_CB_COOLDOWN = 60.0             # Seconds to wait before retrying after open


def _cb_record_success():
    """Reset circuit breaker on success."""
    global _cb_failures
    with _cb_lock:
        _cb_failures = 0


def _cb_record_failure():
    """Increment failure counter and record time."""
    global _cb_failures, _cb_last_failure
    import time
    with _cb_lock:
        _cb_failures += 1
        _cb_last_failure = time.time()


def _cb_is_open():
    """Return True if circuit breaker is open (too many recent failures)."""
    import time
    with _cb_lock:
        if _cb_failures >= _CB_THRESHOLD:
            if time.time() - _cb_last_failure < _CB_COOLDOWN:
                return True
            # Cooldown expired — allow one retry (half-open state)
            return False
        return False


def _is_private_ip(ip_str: str) -> bool:
    """Return True if the IP is private, loopback, link-local, or non-routable."""
    if not ip_str:
        return True
    try:
        addr = ipaddress.ip_address(ip_str)
        if addr.version == 6:
            # Loopback (::1), link-local (fe80::/10), unique-local (fc00::/7)
            return addr.is_loopback or addr.is_link_local or addr.is_private or addr.is_unspecified
        # IPv4 — check against all known private/reserved ranges
        return any(addr in net for net in _PRIVATE_NETS_V4)
    except ValueError:
        return True  # Unparseable → treat as local


def _cleanup_expired_cache(conn, cursor, P):
    """Remove stale geo_cache entries older than GEO_CACHE_MINUTES."""
    try:
        cutoff = (now() - timedelta(minutes=Config.GEO_CACHE_MINUTES)).isoformat()
        cursor.execute(
            f'DELETE FROM geo_cache WHERE cached_at < {P}', (cutoff,)
        )
        conn.commit()
    except Exception as e:
        log.debug("[GEO] Cache cleanup failed: %s", e)


def get_geo_info(ip):
    """Get geolocation from IP with caching, circuit breaker, and rate-limit resilience."""

    if _is_private_ip(ip):
        return _LOCAL_GEO.copy()

    conn = get_db()
    cursor = get_cursor(conn)
    P = placeholder()

    # ── Cache Lookup ─────────────────────────────────────────────────────
    try:
        cursor.execute(
            f'SELECT data, cached_at FROM geo_cache WHERE ip_address = {P}', (ip,)
        )
        row = cursor.fetchone()

        if row:
            cached_data = row['data'] if hasattr(row, 'keys') else row[0]
            cached_at = row['cached_at'] if hasattr(row, 'keys') else row[1]
            try:
                cached_time = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
                if now() - cached_time < timedelta(minutes=Config.GEO_CACHE_MINUTES):
                    return json.loads(cached_data)
            except ValueError:
                pass
    except Exception as e:
        log.debug("[GEO] Cache read error: %s", e)

    # ── Circuit Breaker Check (R-03) ─────────────────────────────────────
    if _cb_is_open():
        log.debug("[GEO] Circuit breaker open — skipping external lookup for ip=%s", ip)
        return _UNKNOWN_GEO.copy()

    # ── External Lookup ──────────────────────────────────────────────────
    try:
        base_url = Config.GEO_API_URL
        url = (
            f'{base_url}/{ip}'
            '?fields=status,message,country,regionName,city,lat,lon,timezone,isp,org,as'
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'naarad/1.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())

        if data.get('status') == 'success':
            _cb_record_success()
            result = {
                'country':  data.get('country', 'Unknown'),
                'region':   data.get('regionName', 'Unknown'),
                'city':     data.get('city', 'Unknown'),
                'lat':      data.get('lat', 0.0),
                'lon':      data.get('lon', 0.0),
                'timezone': data.get('timezone', 'Unknown'),
                'isp':      data.get('isp', 'Unknown'),
                'org':      data.get('org', ''),
                'asn':      data.get('as', ''),
            }

            # ── Cache Write (upsert) ──────────────────────────────────────
            is_postgres = USE_POSTGRES
            timestamp = now_iso()
            json_data = json.dumps(result)

            try:
                if is_postgres:
                    cursor.execute(f'''
                        INSERT INTO geo_cache (ip_address, data, cached_at)
                        VALUES ({P}, {P}, {P})
                        ON CONFLICT (ip_address)
                        DO UPDATE SET data = EXCLUDED.data, cached_at = EXCLUDED.cached_at
                    ''', (ip, json_data, timestamp))
                else:
                    cursor.execute(f'''
                        INSERT OR REPLACE INTO geo_cache (ip_address, data, cached_at)
                        VALUES ({P}, {P}, {P})
                    ''', (ip, json_data, timestamp))
                conn.commit()

                # P-02: Probabilistic cleanup (1-in-50 instead of every write)
                import random
                if random.randint(1, 50) == 1:
                    _cleanup_expired_cache(conn, cursor, P)
            except Exception as e:
                log.debug("[GEO] Cache write error: %s", e)

            return result

        # Rate-limited or API failure
        _cb_record_failure()
        log.warning("[GEO] ip-api.com returned status=%s message=%s for ip=%s",
                    data.get('status'), data.get('message', ''), ip)

    except urllib.error.HTTPError as e:
        _cb_record_failure()
        log.warning("[GEO] HTTP error %s for ip=%s", e.code, ip)
    except Exception as e:
        _cb_record_failure()
        log.warning("[GEO] Lookup error for ip=%s: %s", ip, e)

    return _UNKNOWN_GEO.copy()


def enrich_track_async(app, track_id, ip):
    """R-01: Enrich a track record with geo data in a background thread.
    
    Called after the pixel/click response is already sent.
    Used only when the track was created without geo data.
    """
    def _do_enrich():
        try:
            with app.app_context():
                geo = get_geo_info(ip)
                if geo['country'] == 'Unknown' and geo['city'] == 'Unknown':
                    return  # No useful data to enrich with

                conn = get_db()
                cursor = get_cursor(conn)
                P = placeholder()
                cursor.execute(
                    f'''UPDATE tracks SET 
                        country = {P}, region = {P}, city = {P}, 
                        latitude = {P}, longitude = {P}, timezone = {P},
                        isp = {P}, org = {P}, asn = {P}
                    WHERE track_id = {P} AND (country IS NULL OR country = 'Unknown')''',
                    (geo['country'], geo['region'], geo['city'],
                     geo['lat'], geo['lon'], geo['timezone'],
                     geo['isp'], geo.get('org', ''), geo.get('asn', ''),
                     track_id)
                )
                conn.commit()
        except Exception as e:
            log.debug("[GEO] Background enrichment failed for track_id=%s: %s", track_id, e)

    t = threading.Thread(target=_do_enrich, daemon=True)
    t.start()
