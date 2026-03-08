"""
Naarad - API Controller
All /api/* endpoints. Auth is required by default (REQUIRE_AUTH=true).
"""

import io
import csv
import logging
from collections import defaultdict
from functools import wraps
from time import time
from flask import Blueprint, request, jsonify, Response, abort, stream_with_context
from ..database import get_db, get_cursor, placeholder
from ..config import Config
from ..utils import sanitize_id, now_iso, safe_str_compare

log = logging.getLogger(__name__)

bp_api = Blueprint('api', __name__, url_prefix='/api')

# ── API Rate Limiter ────────────────────────────────────────────────────────
_api_rate_buckets: dict = defaultdict(list)
_api_rate_last_evict: float = 0.0


def _is_api_rate_limited(ip: str) -> bool:
    """Return True if this IP has exceeded API_RATE_LIMIT_PER_MINUTE."""
    global _api_rate_last_evict
    limit = Config.API_RATE_LIMIT_PER_MINUTE
    if not limit:
        return False
    now_ts = time()
    window = 60.0
    hits = _api_rate_buckets[ip]
    hits[:] = [t for t in hits if now_ts - t < window]
    if len(hits) >= limit:
        return True
    hits.append(now_ts)
    # Periodic eviction
    if now_ts - _api_rate_last_evict > 300.0:
        _api_rate_last_evict = now_ts
        stale = [k for k, v in _api_rate_buckets.items() if not v or (now_ts - v[-1]) > window]
        for k in stale:
            del _api_rate_buckets[k]
    return False


def require_api_key(f):
    """Require API key via X-API-Key header for protected endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not Config.REQUIRE_AUTH:
            return f(*args, **kwargs)
        # Rate limit API endpoints (L-15)
        from ..controllers.tracking import get_client_ip
        ip = get_client_ip()
        if _is_api_rate_limited(ip):
            abort(429)
        # Key must come from header only — query string leaks it into logs
        api_key = request.headers.get('X-API-Key')
        # H-04: Timing-safe comparison prevents side-channel attacks
        if not api_key or not safe_str_compare(api_key, Config.API_KEY):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


@bp_api.route('/stats')
@require_api_key
def stats():
    """Get aggregate statistics."""
    P = placeholder()
    conn = get_db()
    cursor = get_cursor(conn)

    cursor.execute(
        'SELECT COUNT(*) as total, SUM(open_count) as opens, SUM(click_count) as clicks FROM tracks'
    )
    row = cursor.fetchone()
    basic = dict(row) if hasattr(row, 'keys') else {
        'total': row[0], 'opens': row[1], 'clicks': row[2]
    }

    cursor.execute(
        'SELECT country, COUNT(*) as count FROM tracks GROUP BY country ORDER BY count DESC LIMIT 10'
    )
    countries = [
        dict(r) if hasattr(r, 'keys') else {'country': r[0], 'count': r[1]}
        for r in cursor.fetchall()
    ]

    cursor.execute('SELECT device_type, COUNT(*) as count FROM tracks GROUP BY device_type')
    devices = [
        dict(r) if hasattr(r, 'keys') else {'device_type': r[0], 'count': r[1]}
        for r in cursor.fetchall()
    ]

    cursor.execute(
        'SELECT browser, COUNT(*) as count FROM tracks GROUP BY browser ORDER BY count DESC'
    )
    browsers = [
        dict(r) if hasattr(r, 'keys') else {'browser': r[0], 'count': r[1]}
        for r in cursor.fetchall()
    ]

    total = basic['total'] or 0
    opens = basic['opens'] or 0
    clicks = basic['clicks'] or 0

    return jsonify({
        'summary': {
            'total_unique':  total,
            'total_opens':   opens,
            'total_clicks':  clicks,
            'avg_opens':     round(opens / max(total, 1), 2),
        },
        'geographic': countries,
        'devices':    devices,
        'browsers':   browsers,
    })


@bp_api.route('/tracks')
@require_api_key
def tracks():
    """List tracking events with optional search, pagination."""
    P = placeholder()
    limit  = min(request.args.get('limit', 100, type=int), 500)
    offset = request.args.get('offset', 0, type=int)
    q      = request.args.get('q', '').strip()

    conn   = get_db()
    cursor = get_cursor(conn)

    if q:
        pattern = f'%{q}%'
        cursor.execute(f'''
            SELECT * FROM tracks
            WHERE track_id LIKE {P} OR label LIKE {P} OR recipient LIKE {P} OR subject LIKE {P}
            ORDER BY last_seen DESC LIMIT {P} OFFSET {P}
        ''', (pattern, pattern, pattern, pattern, limit, offset))
        items = [dict(r) if hasattr(r, 'keys') else dict(r) for r in cursor.fetchall()]

        cursor.execute(f'''
            SELECT COUNT(*) as cnt FROM tracks
            WHERE track_id LIKE {P} OR label LIKE {P} OR recipient LIKE {P} OR subject LIKE {P}
        ''', (pattern, pattern, pattern, pattern))
    else:
        cursor.execute(
            f'SELECT * FROM tracks ORDER BY last_seen DESC LIMIT {P} OFFSET {P}',
            (limit, offset)
        )
        items = [dict(r) if hasattr(r, 'keys') else dict(r) for r in cursor.fetchall()]
        cursor.execute('SELECT COUNT(*) as cnt FROM tracks')

    row   = cursor.fetchone()
    total = (row['cnt'] if hasattr(row, 'keys') else row[0]) if row else 0

    # Convert SQLite integer booleans to Python booleans for consistent JSON
    for item in items:
        for bool_col in ('is_mobile', 'is_bot'):
            if bool_col in item and item[bool_col] is not None:
                item[bool_col] = bool(item[bool_col])

    return jsonify({'tracks': items, 'total': total})


@bp_api.route('/track', methods=['POST'])
@require_api_key
def create_track():
    """Create a new tracking entry (pre-register before sending).
    
    This is the correct place to attach PII metadata (sender, recipient, subject)
    rather than in pixel query params.
    """
    P = placeholder()
    data     = request.json or {}
    track_id = sanitize_id(data.get('track_id', ''))
    label    = data.get('label', '')

    # PII metadata — attached here safely, not in the pixel URL
    sender    = data.get('sender', '')
    recipient = data.get('recipient', '')
    subject   = data.get('subject', '')
    sent_at   = data.get('sent_at', '')

    if not track_id:
        import uuid
        track_id = f"track-{uuid.uuid4().hex[:8]}"

    conn   = get_db()
    cursor = get_cursor(conn)

    cursor.execute(f'SELECT id FROM tracks WHERE track_id = {P}', (track_id,))
    if cursor.fetchone():
        return jsonify({'error': 'Track ID already exists'}), 400

    timestamp    = now_iso()
    cols         = ['timestamp', 'track_id', 'label', 'sender', 'recipient', 'subject', 'sent_at',
                    'first_seen', 'last_seen', 'open_count', 'click_count']
    placeholders = ', '.join([P] * len(cols))
    cursor.execute(
        f"INSERT INTO tracks ({', '.join(cols)}) VALUES ({placeholders})",
        (timestamp, track_id, label, sender, recipient, subject, sent_at,
         timestamp, timestamp, 0, 0)
    )
    conn.commit()
    return jsonify({'track_id': track_id, 'label': label})


@bp_api.route('/track/<track_id>', methods=['PUT'])
@require_api_key
def update_track(track_id):
    """Update track label and metadata."""
    P    = placeholder()
    track_id = sanitize_id(track_id)  # L-14: Sanitize URL path param
    data  = request.json or {}
    label = data.get('label', '')

    conn   = get_db()
    cursor = get_cursor(conn)

    cursor.execute(f'SELECT id FROM tracks WHERE track_id = {P}', (track_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Not found'}), 404

    cursor.execute(f'UPDATE tracks SET label = {P} WHERE track_id = {P}', (label, track_id))
    conn.commit()
    return jsonify({'success': True})


@bp_api.route('/track/<track_id>', methods=['DELETE'])
@require_api_key
def delete_track(track_id):
    """Delete a track and all its click history."""
    P = placeholder()
    track_id = sanitize_id(track_id)  # L-14: Sanitize URL path param
    conn   = get_db()
    cursor = get_cursor(conn)

    cursor.execute(f'DELETE FROM tracks WHERE track_id = {P}', (track_id,))
    tracks_deleted = cursor.rowcount if hasattr(cursor, 'rowcount') else 0
    cursor.execute(f'DELETE FROM clicks WHERE track_id = {P}', (track_id,))
    conn.commit()

    # L-13: Return 404 if nothing was actually deleted
    if tracks_deleted == 0:
        return jsonify({'error': 'Not found'}), 404

    return jsonify({'success': True})


@bp_api.route('/track/<track_id>')
@require_api_key
def track_detail(track_id):
    """Get full details for a specific track including click history."""
    P = placeholder()
    track_id = sanitize_id(track_id)  # L-14
    conn   = get_db()
    cursor = get_cursor(conn)

    cursor.execute(f'SELECT * FROM tracks WHERE track_id = {P}', (track_id,))
    track = cursor.fetchone()
    if not track:
        return jsonify({'error': 'Not found'}), 404

    track_dict = dict(track) if hasattr(track, 'keys') else dict(track)
    for bool_col in ('is_mobile', 'is_bot'):
        if bool_col in track_dict and track_dict[bool_col] is not None:
            track_dict[bool_col] = bool(track_dict[bool_col])

    cursor.execute(
        f'SELECT * FROM clicks WHERE track_id = {P} ORDER BY timestamp DESC', (track_id,)
    )
    clicks = [dict(r) if hasattr(r, 'keys') else dict(r) for r in cursor.fetchall()]

    return jsonify({'track': track_dict, 'clicks': clicks})


@bp_api.route('/export')
@require_api_key
def export():
    """Export tracking data as CSV or JSON. Streams CSV to avoid loading all into memory."""
    fmt = request.args.get('format', 'json').lower()

    conn   = get_db()
    cursor = get_cursor(conn)

    if fmt == 'csv':
        # M-07: Stream CSV to avoid loading entire dataset into memory
        # First get column names
        cursor.execute('SELECT * FROM tracks ORDER BY timestamp DESC LIMIT 1')
        sample = cursor.fetchone()

        if not sample:
            # M-09: Return proper empty CSV with standard headers
            empty_csv = 'id,timestamp,track_id,campaign_id,label\n'
            return Response(
                empty_csv,
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=naarad_export.csv'}
            )

        fieldnames = list(dict(sample).keys()) if hasattr(sample, 'keys') else \
            [desc[0] for desc in cursor.description]

        def generate_csv():
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            # Re-query all rows and stream them
            inner_cursor = get_cursor(conn)
            inner_cursor.execute('SELECT * FROM tracks ORDER BY timestamp DESC')
            batch_size = 100
            while True:
                rows = inner_cursor.fetchmany(batch_size)
                if not rows:
                    break
                for row in rows:
                    row_dict = dict(row) if hasattr(row, 'keys') else dict(row)
                    writer.writerow(row_dict)
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

        return Response(
            stream_with_context(generate_csv()),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=naarad_export.csv'}
        )

    # JSON format
    cursor.execute('SELECT * FROM tracks ORDER BY timestamp DESC')
    items = [dict(r) if hasattr(r, 'keys') else dict(r) for r in cursor.fetchall()]
    return jsonify({'tracks': items})


# ── Node Sync (Hybrid Architecture) ──────────────────────────────────────────

@bp_api.route('/sync/status', methods=['GET'])
@require_api_key
def sync_status():
    """Return whether this node is configured to pull from a remote node."""
    is_sync_enabled = bool(Config.SYNC_REMOTE_URL and Config.SYNC_API_KEY)
    return jsonify({
        'enabled': is_sync_enabled,
        'remote': Config.SYNC_REMOTE_URL if is_sync_enabled else None
    })

@bp_api.route('/sync', methods=['GET'])
@require_api_key
def get_sync_data():
    """Export tracks and clicks that happened after a given timestamp."""
    P = placeholder()
    since = request.args.get('since', '1970-01-01T00:00:00Z')

    conn   = get_db()
    cursor = get_cursor(conn)

    cursor.execute(f'SELECT * FROM tracks WHERE last_seen > {P} ORDER BY last_seen ASC', (since,))
    tracks = [dict(r) if hasattr(r, 'keys') else dict(r) for r in cursor.fetchall()]

    cursor.execute(f'SELECT * FROM clicks WHERE timestamp > {P} ORDER BY timestamp ASC', (since,))
    clicks = [dict(r) if hasattr(r, 'keys') else dict(r) for r in cursor.fetchall()]

    return jsonify({'tracks': tracks, 'clicks': clicks})


@bp_api.route('/sync', methods=['DELETE'])
@require_api_key
def wipe_sync_data():
    """Wipe tracks and clicks that happened before a given timestamp."""
    P = placeholder()
    until = request.args.get('until')
    if not until:
        return jsonify({'error': 'Missing until parameter'}), 400

    # M-10: Validate that 'until' is a valid ISO timestamp
    from datetime import datetime
    try:
        datetime.fromisoformat(until.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return jsonify({'error': 'Invalid timestamp format. Use ISO 8601.'}), 400

    conn   = get_db()
    cursor = get_cursor(conn)

    cursor.execute(f'DELETE FROM tracks WHERE last_seen <= {P}', (until,))
    tracks_deleted = cursor.rowcount if hasattr(cursor, 'rowcount') else 0

    cursor.execute(f'DELETE FROM clicks WHERE timestamp <= {P}', (until,))
    clicks_deleted = cursor.rowcount if hasattr(cursor, 'rowcount') else 0

    conn.commit()

    return jsonify({
        'success': True,
        'deleted_tracks': tracks_deleted,
        'deleted_clicks': clicks_deleted
    })
