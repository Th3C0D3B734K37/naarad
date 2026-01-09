
from flask import Blueprint, request, Response, redirect
from ..database import get_db, get_cursor, placeholder
from ..services.geo import get_geo_info, now_iso
from ..services.ua import parse_user_agent
from ..utils import sanitize_id, hash_url, send_webhook

bp_track = Blueprint('track', __name__)

# Transparent 1x1 PNG
PIXEL = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

# SQL placeholder for current database
P = placeholder()

def get_client_ip():
    """Get real client IP from headers (supports proxies/CDNs)."""
    for header in ['CF-Connecting-IP', 'X-Real-IP', 'X-Forwarded-For']:
        ip = request.headers.get(header)
        if ip:
            return ip.split(',')[0].strip()
    return request.remote_addr

def extract_headers():
    """Extract all useful headers from request."""
    return {
        'referer': request.headers.get('Referer', 'Direct'),
        'accept_language': request.headers.get('Accept-Language', ''),
        'accept_encoding': request.headers.get('Accept-Encoding', ''),
        'accept_header': request.headers.get('Accept', ''),
        'connection_type': request.headers.get('Connection', ''),
        'do_not_track': request.headers.get('DNT', ''),
        'cache_control': request.headers.get('Cache-Control', ''),
        'sec_ch_ua': request.headers.get('Sec-CH-UA', ''),
        'sec_ch_ua_mobile': request.headers.get('Sec-CH-UA-Mobile', ''),
        'sec_ch_ua_platform': request.headers.get('Sec-CH-UA-Platform', ''),
    }

@bp_track.route('/favicon.ico')
def favicon():
    return Response(status=204)

@bp_track.route('/track')
@bp_track.route('/pixel')
@bp_track.route('/t/<track_id>')
def track_open(track_id=None):
    """Track email open with maximum data capture."""
    track_id = sanitize_id(track_id or request.args.get('id', 'unknown'))
    campaign_id = request.args.get('c') or request.args.get('campaign')
    sender = request.args.get('sender') or request.args.get('from')
    recipient = request.args.get('recipient') or request.args.get('to')
    subject = request.args.get('subject')
    sent_at = request.args.get('sent_at')
    
    ip = get_client_ip()
    geo = get_geo_info(ip)
    
    ua = request.headers.get('User-Agent', '')
    ua_info = parse_user_agent(ua)
    
    headers = extract_headers()
    timestamp = now_iso()
    
    conn = get_db()
    cursor = get_cursor(conn)
    
    cursor.execute(f'SELECT id FROM tracks WHERE track_id = {P}', (track_id,))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute(f'UPDATE tracks SET open_count = open_count + 1, last_seen = {P} WHERE track_id = {P}',
                       (timestamp, track_id))
    else:
        placeholders = ', '.join([P] * 38)
        cursor.execute(f'''
            INSERT INTO tracks (
                timestamp, track_id, campaign_id, sender, recipient, subject, sent_at,
                ip_address, country, region, city, latitude, longitude, timezone, isp, org, asn,
                user_agent, browser, browser_version, os, os_version, device_type, 
                device_brand, is_mobile, is_bot,
                referer, accept_language, accept_encoding, accept_header,
                connection_type, do_not_track, cache_control,
                sec_ch_ua, sec_ch_ua_mobile, sec_ch_ua_platform,
                first_seen, last_seen
            ) VALUES ({placeholders})
        ''', (
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
            timestamp, timestamp
        ))
    
    conn.commit()
    
    send_webhook('open', {'track_id': track_id, 'location': f"{geo['city']}, {geo['country']}"})
    
    return Response(PIXEL, mimetype='image/png', headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'Accept-CH': 'Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform'
    })

@bp_track.route('/click/<track_id>/<path:target_url>')
@bp_track.route('/c/<track_id>/<path:target_url>')
def track_click(track_id, target_url):
    """Track link click and redirect."""
    from urllib.parse import unquote
    track_id = sanitize_id(track_id)
    target_url = unquote(target_url)
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url
    
    campaign_id = request.args.get('c')
    link_id = hash_url(target_url)
    
    ip = get_client_ip()
    ua = request.headers.get('User-Agent', '')
    ua_info = parse_user_agent(ua)
    geo = get_geo_info(ip)
    referer = request.headers.get('Referer', 'Direct')
    timestamp = now_iso()
    
    conn = get_db()
    cursor = get_cursor(conn)
    
    placeholders = ', '.join([P] * 13)
    cursor.execute(f'''
        INSERT INTO clicks (timestamp, track_id, campaign_id, link_id, target_url,
                            ip_address, country, city, user_agent, browser, os, device_type, referer)
        VALUES ({placeholders})
    ''', (timestamp, track_id, campaign_id, link_id, target_url, ip, geo['country'],
          geo['city'], ua, ua_info['browser'], ua_info['os'], ua_info['device_type'], referer))
    
    # Ensure track exists (e.g. if user clicked link but blocked pixel, or SMS link)
    cursor.execute(f'SELECT id FROM tracks WHERE track_id = {P}', (track_id,))
    if not cursor.fetchone():
         placeholders = ', '.join([P] * 18) # Minimal fields
         cursor.execute(f'''
            INSERT INTO tracks (
                timestamp, track_id, campaign_id, 
                ip_address, country, region, city, latitude, longitude,
                user_agent, browser, os, device_type, first_seen, last_seen,
                click_count, open_count, referer
            ) VALUES ({placeholders})
         ''', (
             timestamp, track_id, campaign_id,
             ip, geo['country'], geo['region'], geo['city'], geo['lat'], geo['lon'],
             ua, ua_info['browser'], ua_info['os'], ua_info['device_type'], timestamp, timestamp,
             1, 0, referer
         ))
    else:
        cursor.execute(f'UPDATE tracks SET click_count = click_count + 1, last_seen = {P} WHERE track_id = {P}',
                       (timestamp, track_id))
    
    conn.commit()
    
    send_webhook('click', {'track_id': track_id, 'url': target_url})
    
    return redirect(target_url)
