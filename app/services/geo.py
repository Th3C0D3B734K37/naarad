"""
Naarad - Geolocation Service
IP geolocation with caching, rate-limit handling, and proper private IP detection.
"""

import json
import logging
import ipaddress
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from ..config import Config
from ..database import get_db, get_cursor, placeholder
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
    """Get geolocation from IP with caching and rate-limit resilience."""

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

    # ── External Lookup ──────────────────────────────────────────────────
    try:
        # H-07: Use configurable GEO_API_URL. Default ip-api.com free tier is HTTP-only;
        # HTTPS requires their Pro plan. Set GEO_API_URL env var to use your own HTTPS endpoint.
        base_url = Config.GEO_API_URL
        url = (
            f'{base_url}/{ip}'
            '?fields=status,message,country,regionName,city,lat,lon,timezone,isp,org,as'
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'Naarad/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        if data.get('status') == 'success':
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
            is_postgres = bool(Config.DATABASE_URL)
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

                # Periodic cleanup: evict expired entries while we have the connection
                _cleanup_expired_cache(conn, cursor, P)
            except Exception as e:
                log.debug("[GEO] Cache write error: %s", e)

            return result

        # Rate-limited or API failure
        log.warning("[GEO] ip-api.com returned status=%s message=%s for ip=%s",
                    data.get('status'), data.get('message', ''), ip)

    except urllib.error.HTTPError as e:
        log.warning("[GEO] HTTP error %s for ip=%s", e.code, ip)
    except Exception as e:
        log.warning("[GEO] Lookup error for ip=%s: %s", ip, e)

    return _UNKNOWN_GEO.copy()
