
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from ..config import Config
from ..database import get_db, get_cursor, placeholder

def now():
    """Get current UTC time."""
    return datetime.now(timezone.utc)

def now_iso():
    """Get current UTC time as ISO string."""
    return now().isoformat()

def get_geo_info(ip):
    """Get geolocation from IP with caching."""
    
    if not ip or ip.startswith(('127.', '192.168.', '10.', '172.', '::1', 'localhost')):
        return {'country': 'Local', 'region': 'Local', 'city': 'Local',
                'lat': 0.0, 'lon': 0.0, 'timezone': 'Local', 'isp': 'Local'}
    
    conn = get_db()
    cursor = get_cursor(conn)
    P = placeholder()
    
    try:
        cursor.execute(f'SELECT data, cached_at FROM geo_cache WHERE ip_address = {P}', (ip,))
        row = cursor.fetchone()
        
        # Handle dict or tuple
        if row:
            cached_data = row['data'] if hasattr(row, 'get') else row[0]
            cached_at = row['cached_at'] if hasattr(row, 'get') else row[1]
            
            try:
                cached_time = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
                if now() - cached_time < timedelta(minutes=Config.GEO_CACHE_MINUTES):
                    # conn.close() - handled by app context
                    return json.loads(cached_data)
            except ValueError:
                pass
    except Exception:
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
                
                # Check DB type for upsert syntax
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
                except Exception:
                    pass # Fail silently on cache write error
                
                return result
    except Exception as e:
        print(f"[GEO] Error: {e}")
    
    # conn.close() - handled by app context
    return {'country': 'Unknown', 'region': 'Unknown', 'city': 'Unknown',
            'lat': 0.0, 'lon': 0.0, 'timezone': 'Unknown', 'isp': 'Unknown',
            'org': '', 'asn': ''}
