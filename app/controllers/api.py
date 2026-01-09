
import io
import csv
from functools import wraps
from flask import Blueprint, request, jsonify, Response
from ..database import get_db
from ..config import Config
from ..utils import sanitize_id

bp_api = Blueprint('api', __name__, url_prefix='/api')

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
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as total, SUM(open_count) as opens, SUM(click_count) as clicks FROM tracks')
    basic = dict(cursor.fetchone())
    
    cursor.execute('SELECT country, COUNT(*) as count FROM tracks GROUP BY country ORDER BY count DESC LIMIT 10')
    countries = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('SELECT device_type, COUNT(*) as count FROM tracks GROUP BY device_type')
    devices = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('SELECT browser, COUNT(*) as count FROM tracks GROUP BY browser ORDER BY count DESC')
    browsers = [dict(row) for row in cursor.fetchall()]
    
    
    # conn.close() - Handled by teardown_appcontext
    
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
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tracks ORDER BY last_seen DESC LIMIT ? OFFSET ?', (limit, offset))
    items = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute('SELECT COUNT(*) FROM tracks')
    total = cursor.fetchone()[0]
    # conn.close() - Handled by teardown_appcontext
    
    return jsonify({'tracks': items, 'total': total})

@bp_api.route('/track/<track_id>')
@require_api_key
def track_detail(track_id):
    """Get details for a specific track."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM tracks WHERE track_id = ?', (track_id,))
    track = cursor.fetchone()
    
    if not track:
        # conn.close() - Handled by teardown_appcontext
        return jsonify({'error': 'Not found'}), 404
    
    cursor.execute('SELECT * FROM clicks WHERE track_id = ? ORDER BY timestamp DESC', (track_id,))
    clicks = [dict(row) for row in cursor.fetchall()]
    # conn.close() - Handled by teardown_appcontext
    
    return jsonify({'track': dict(track), 'clicks': clicks})

@bp_api.route('/export')
@require_api_key
def export():
    """Export data as CSV or JSON."""
    fmt = request.args.get('format', 'json')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tracks ORDER BY timestamp DESC')
    items = [dict(row) for row in cursor.fetchall()]
    # conn.close() - Handled by teardown_appcontext
    
    if fmt == 'csv' and items:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=items[0].keys())
        writer.writeheader()
        writer.writerows(items)
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment; filename=export.csv'})
    
    return jsonify({'tracks': items})
