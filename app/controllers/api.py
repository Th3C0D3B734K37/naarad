
import io
import csv
from functools import wraps
from flask import Blueprint, request, jsonify, Response
from ..database import get_db, get_cursor, placeholder
from ..config import Config
from ..utils import sanitize_id

bp_api = Blueprint('api', __name__, url_prefix='/api')

# SQL placeholder for current database
P = placeholder()

def require_api_key(f):
    """Require API key for protected endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not Config.REQUIRE_AUTH:
            return f(*args, **kwargs)
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if api_key != Config.API_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

@bp_api.route('/stats')
@require_api_key
def stats():
    """Get aggregate statistics."""
    conn = get_db()
    cursor = get_cursor(conn)
    
    cursor.execute('SELECT COUNT(*) as total, SUM(open_count) as opens, SUM(click_count) as clicks FROM tracks')
    row = cursor.fetchone()
    basic = dict(row) if hasattr(row, 'keys') else {'total': row[0], 'opens': row[1], 'clicks': row[2]}
    
    cursor.execute('SELECT country, COUNT(*) as count FROM tracks GROUP BY country ORDER BY count DESC LIMIT 10')
    countries = [dict(row) if hasattr(row, 'keys') else {'country': row[0], 'count': row[1]} for row in cursor.fetchall()]
    
    cursor.execute('SELECT device_type, COUNT(*) as count FROM tracks GROUP BY device_type')
    devices = [dict(row) if hasattr(row, 'keys') else {'device_type': row[0], 'count': row[1]} for row in cursor.fetchall()]
    
    cursor.execute('SELECT browser, COUNT(*) as count FROM tracks GROUP BY browser ORDER BY count DESC')
    browsers = [dict(row) if hasattr(row, 'keys') else {'browser': row[0], 'count': row[1]} for row in cursor.fetchall()]
    
    return jsonify({
        'summary': {
            'total_unique': basic['total'] or 0,
            'total_opens': basic['opens'] or 0,
            'total_clicks': basic['clicks'] or 0,
            'avg_opens': round((basic['opens'] or 0) / max(basic['total'] or 1, 1), 2)
        },
        'geographic': countries,
        'devices': devices,
        'browsers': browsers
    })

from datetime import datetime, timezone

def now_iso():
    return datetime.now(timezone.utc).isoformat()

@bp_api.route('/tracks')
@require_api_key
def tracks():
    """List tracking events with optional search."""
    limit = min(request.args.get('limit', 100, type=int), 500)
    offset = request.args.get('offset', 0, type=int)
    q = request.args.get('q', '').strip()
    
    conn = get_db()
    cursor = get_cursor(conn)
    
    items = []
    total = 0
    
    if q:
        # Search mode
        pattern = f'%{q}%'
        cursor.execute(f'''
            SELECT * FROM tracks 
            WHERE track_id LIKE {P} OR label LIKE {P} OR recipient LIKE {P} OR subject LIKE {P}
            ORDER BY last_seen DESC LIMIT {P} OFFSET {P}
        ''', (pattern, pattern, pattern, pattern, limit, offset))
        items = [dict(row) if hasattr(row, 'keys') else row for row in cursor.fetchall()]
        
        cursor.execute(f'''
            SELECT COUNT(*) FROM tracks 
            WHERE track_id LIKE {P} OR label LIKE {P} OR recipient LIKE {P} OR subject LIKE {P}
        ''', (pattern, pattern, pattern, pattern))
        row = cursor.fetchone()
        
    else:
        cursor.execute(f'SELECT * FROM tracks ORDER BY last_seen DESC LIMIT {P} OFFSET {P}', (limit, offset))
        items = [dict(row) if hasattr(row, 'keys') else row for row in cursor.fetchall()]
        
        cursor.execute('SELECT COUNT(*) FROM tracks')
        row = cursor.fetchone()
        
    total = row[0] if row and (isinstance(row, tuple) or not hasattr(row, 'keys')) else row['count'] if row else 0
    if hasattr(row, 'values'): total = list(row.values())[0] # Fallback for dict without 'count' key if specific driver behavior differs
    
    return jsonify({'tracks': items, 'total': total})

@bp_api.route('/track', methods=['POST'])
@require_api_key
def create_track():
    """Create a new tracking pixel."""
    data = request.json or {}
    track_id = sanitize_id(data.get('track_id', ''))
    label = data.get('label', '')
    
    if not track_id:
        import uuid
        track_id = f"track-{uuid.uuid4().hex[:8]}"
        
    conn = get_db()
    cursor = get_cursor(conn)
    
    # Check existence
    cursor.execute(f'SELECT id FROM tracks WHERE track_id = {P}', (track_id,))
    if cursor.fetchone():
        return jsonify({'error': 'Track ID exists'}), 400
        
    timestamp = now_iso()
    placeholders = ', '.join([P] * 6)
    cursor.execute(f'''
        INSERT INTO tracks (timestamp, track_id, label, first_seen, last_seen, open_count)
        VALUES ({placeholders})
    ''', (timestamp, track_id, label, timestamp, timestamp, 0))
    
    conn.commit()
    return jsonify({'track_id': track_id, 'label': label})

@bp_api.route('/track/<track_id>', methods=['PUT'])
@require_api_key
def update_track(track_id):
    """Update track metadata (label)."""
    data = request.json or {}
    label = data.get('label', '')
    
    conn = get_db()
    cursor = get_cursor(conn)
    
    cursor.execute(f'UPDATE tracks SET label = {P} WHERE track_id = {P}', (label, track_id))
    conn.commit()
    
    return jsonify({'success': True})

@bp_api.route('/track/<track_id>', methods=['DELETE'])
@require_api_key
def delete_track(track_id):
    """Delete a track and its history."""
    conn = get_db()
    cursor = get_cursor(conn)
    
    cursor.execute(f'DELETE FROM tracks WHERE track_id = {P}', (track_id,))
    cursor.execute(f'DELETE FROM clicks WHERE track_id = {P}', (track_id,))
    conn.commit()
    
    return jsonify({'success': True})

@bp_api.route('/track/<track_id>')
@require_api_key
def track_detail(track_id):
    """Get details for a specific track."""
    conn = get_db()
    cursor = get_cursor(conn)
    
    cursor.execute(f'SELECT * FROM tracks WHERE track_id = {P}', (track_id,))
    track = cursor.fetchone()
    
    if not track:
        return jsonify({'error': 'Not found'}), 404
    
    cursor.execute(f'SELECT * FROM clicks WHERE track_id = {P} ORDER BY timestamp DESC', (track_id,))
    clicks = [dict(row) if hasattr(row, 'keys') else row for row in cursor.fetchall()]
    
    return jsonify({'track': dict(track) if hasattr(track, 'keys') else track, 'clicks': clicks})

@bp_api.route('/export')
@require_api_key
def export():
    """Export data as CSV or JSON."""
    fmt = request.args.get('format', 'json')
    
    conn = get_db()
    cursor = get_cursor(conn)
    cursor.execute('SELECT * FROM tracks ORDER BY timestamp DESC')
    items = [dict(row) if hasattr(row, 'keys') else row for row in cursor.fetchall()]
    
    if fmt == 'csv' and items:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=items[0].keys())
        writer.writeheader()
        writer.writerows(items)
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment; filename=export.csv'})
    
    return jsonify({'tracks': items})


