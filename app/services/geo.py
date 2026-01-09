
import json
from datetime import datetime, timedelta, timezone
from ..config import Config
from ..database import get_db

def now():
    """Get current UTC time."""
    return datetime.now(timezone.utc)

def now_iso():
    """Get current UTC time as ISO string."""
    return now().isoformat()

def get_geo_info(ip):
    """Get geolocation from IP with caching."""
    import urllib.request
    
    if not ip or ip.startswith(('127.', '192.168.', '10.', '172.', '::1', 'localhost')):
        return {'country': 'Local', 'region': 'Local', 'city': 'Local',
                'lat': 0.0, 'lon': 0.0, 'timezone': 'Local', 'isp': 'Local'}
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT data, cached_at FROM geo_cache WHERE ip_address = ?', (ip,))
    cached = cursor.fetchone()
    
    if cached:
        try:
            cached_time = datetime.fromisoformat(cached['cached_at'].replace('Z', '+00:00'))
            if now() - cached_time < timedelta(minutes=Config.GEO_CACHE_MINUTES):
                conn.close()
                return json.loads(cached['data'])
        except ValueError:
            pass
            
    try:
        url = f'http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon,timezone,isp,org,as'
        req = urllib.request.Request(url, headers={'User-Agent': 'Naarad/1.0'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            
            if data.get('status') == 'success':
                result = {
                    'country': data.get('country', 'Unknown'),
                    'region': data.get('regionName', 'Unknown'),
                    'city': data.get('city', 'Unknown'),
                    'lat': data.get('lat', 0.0),
                    'lon': data.get('lon', 0.0),
                    'timezone': data.get('timezone', 'Unknown'),
                    'isp': data.get('isp', 'Unknown'),
                    'org': data.get('org', ''),
                    'asn': data.get('as', '')
                }
                
                cursor.execute('''
                    INSERT OR REPLACE INTO geo_cache (ip_address, data, cached_at)
                    VALUES (?, ?, ?)
                ''', (ip, json.dumps(result), now_iso()))
                conn.commit()
                conn.close()
                return result
    except Exception as e:
        print(f"[GEO] Error: {e}")
    
    conn.close()
    return {'country': 'Unknown', 'region': 'Unknown', 'city': 'Unknown',
            'lat': 0.0, 'lon': 0.0, 'timezone': 'Unknown', 'isp': 'Unknown',
            'org': '', 'asn': ''}
