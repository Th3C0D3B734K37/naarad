
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

@bp_api.route('/tracks')
@require_api_key
def tracks():
    """List tracking events."""
    limit = min(request.args.get('limit', 100, type=int), 500)
    offset = request.args.get('offset', 0, type=int)
    
    conn = get_db()
    cursor = get_cursor(conn)
    cursor.execute(f'SELECT * FROM tracks ORDER BY last_seen DESC LIMIT {P} OFFSET {P}', (limit, offset))
    items = [dict(row) if hasattr(row, 'keys') else row for row in cursor.fetchall()]
    
    cursor.execute('SELECT COUNT(*) FROM tracks')
    row = cursor.fetchone()
    total = row[0] if isinstance(row, tuple) else row['count'] if 'count' in row else list(row.values())[0]
    
    return jsonify({'tracks': items, 'total': total})

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

from app.database import init_db

@bp_api.route('/debug')
def debug():
    """Debug database connection and state."""
    conn = get_db()
    cursor = get_cursor(conn)
    
    status = {
        'database_url_set': bool(Config.DATABASE_URL),
        'db_type': 'PostgreSQL' if bool(Config.DATABASE_URL) else 'SQLite'
    }
    
    try:
        cursor.execute("SELECT to_regclass('public.tracks')")
        table_exists = cursor.fetchone()[0] is not None
        status['tracks_table_exists'] = table_exists
        
        if not table_exists:
            status['action'] = 'Attempting manual table creation...'
            try:
                init_db()
                status['init_result'] = 'Success'
            except Exception as e:
                status['init_result'] = f'Error: {str(e)}'
                
    except Exception as e:
        import traceback
        status['error'] = str(e)
        status['traceback'] = traceback.format_exc()
        
    return jsonify(status)
