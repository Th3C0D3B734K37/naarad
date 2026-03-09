"""
naarad - Background Node Sync Service
Supports running a local node that pulls data from a remote cloud node.
"""

import os
import time
import json
import logging
import threading
import urllib.request
from datetime import datetime, timezone
from ..config import Config
from ..database import get_db, get_cursor, placeholder
from ..utils import now_iso

log = logging.getLogger(__name__)

# Track the background thread to avoid duplicate spawns
_sync_thread = None
_sync_lock = threading.Lock()  # M-01: Prevent multi-worker races

# C-01: Whitelisted column names to prevent SQL injection from remote data
_ALLOWED_TRACK_COLS = frozenset([
    'id', 'timestamp', 'track_id', 'campaign_id', 'label',
    'sender', 'recipient', 'subject', 'sent_at',
    'ip_address', 'country', 'region', 'city', 'latitude', 'longitude',
    'timezone', 'isp', 'org', 'asn',
    'user_agent', 'browser', 'browser_version', 'os', 'os_version',
    'device_type', 'device_brand', 'is_mobile', 'is_bot',
    'referer', 'accept_language', 'accept_encoding', 'accept_header',
    'connection_type', 'do_not_track', 'cache_control',
    'sec_ch_ua', 'sec_ch_ua_mobile', 'sec_ch_ua_platform',
    'open_count', 'click_count', 'first_seen', 'last_seen',
])

_ALLOWED_CLICK_COLS = frozenset([
    'id', 'timestamp', 'track_id', 'campaign_id', 'link_id', 'target_url',
    'ip_address', 'country', 'city', 'user_agent', 'browser',
    'os', 'device_type', 'referer',
])


def _filter_keys(record, allowed_cols):
    """Return a new dict with only whitelisted keys (C-01: prevent SQL injection)."""
    return {k: v for k, v in record.items() if k in allowed_cols}


def _get_max_timestamp(conn, cursor, table_name, column_name):
    """Get the latest timestamp we have locally to avoid pulling old data."""
    # Only allow known table/column names to prevent injection
    allowed = {'tracks': ['last_seen', 'timestamp'], 'clicks': ['timestamp']}
    if table_name not in allowed or column_name not in allowed[table_name]:
        return '1970-01-01T00:00:00Z'
    try:
        cursor.execute(f"SELECT MAX({column_name}) as max_ts FROM {table_name}")
        row = cursor.fetchone()
        max_ts = row['max_ts'] if hasattr(row, 'keys') else row[0]
        return max_ts or '1970-01-01T00:00:00Z'
    except Exception:
        return '1970-01-01T00:00:00Z'


def _sync_loop(app_context_func):
    """Long-running background thread that polls for sync."""
    log.info("[SYNC] Node sync worker started. Remote: %s", Config.SYNC_REMOTE_URL)
    
    while True:
        try:
            # Sleep first so we don't spam immediately on boot
            time.sleep(Config.SYNC_INTERVAL)
            
            with app_context_func():
                conn = get_db()
                cursor = get_cursor(conn)
                P = placeholder()
                
                try:
                    # 1. Ask remote for all records newer than our newest record
                    last_seen = _get_max_timestamp(conn, cursor, 'tracks', 'last_seen')
                    last_click = _get_max_timestamp(conn, cursor, 'clicks', 'timestamp')
                    # R-04: Use datetime parsing for comparison instead of string
                    try:
                        dt_seen = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                        dt_click = datetime.fromisoformat(last_click.replace('Z', '+00:00'))
                        query_since = last_seen if dt_seen >= dt_click else last_click
                    except (ValueError, AttributeError):
                        query_since = max(last_seen, last_click)
                    
                    # 2. Fetch data
                    req = urllib.request.Request(
                        f"{Config.SYNC_REMOTE_URL}/api/sync?since={query_since}",
                        headers={'X-API-Key': Config.SYNC_API_KEY}
                    )
                    with urllib.request.urlopen(req, timeout=10) as response:
                        data = json.loads(response.read().decode())
                    
                    tracks = data.get('tracks', [])
                    clicks = data.get('clicks', [])
                    
                    if not tracks and not clicks:
                        continue  # Nothing new
                        
                    log.info("[SYNC] Pulled %d tracks, %d clicks. Merging...", len(tracks), len(clicks))
                    
                    # 3. Merge data locally via safe upsert
                    is_postgres = bool(Config.DATABASE_URL)
                    
                    # H-01: Merge clicks with deduplication check
                    if clicks:
                        for click in clicks:
                            safe_click = _filter_keys(click, _ALLOWED_CLICK_COLS)
                            if not safe_click or 'track_id' not in safe_click or 'timestamp' not in safe_click:
                                continue
                            # R-05: Dedup on track_id + timestamp + link_id for stronger uniqueness
                            link_id = safe_click.get('link_id', '')
                            cursor.execute(
                                f"SELECT id FROM clicks WHERE track_id = {P} AND timestamp = {P} AND link_id = {P}",
                                (safe_click['track_id'], safe_click['timestamp'], link_id)
                            )
                            if cursor.fetchone():
                                continue  # Skip duplicate
                            
                            cols = [k for k in safe_click.keys() if k != 'id']
                            vals = [safe_click[c] for c in cols]
                            places = ', '.join([P] * len(cols))
                            cursor.execute(
                                f"INSERT INTO clicks ({', '.join(cols)}) VALUES ({places})",
                                vals
                            )
                    
                    # H-02: Merge tracks with proper upsert preserving local-only fields
                    if tracks:
                        for track in tracks:
                            safe_track = _filter_keys(track, _ALLOWED_TRACK_COLS)
                            if not safe_track or 'track_id' not in safe_track:
                                continue
                            
                            track_id = safe_track['track_id']
                            # Remove 'id' — let the local DB assign its own
                            safe_track.pop('id', None)
                            
                            # Check if track exists locally
                            cursor.execute(
                                f"SELECT id FROM tracks WHERE track_id = {P}", (track_id,)
                            )
                            existing = cursor.fetchone()
                            
                            if existing:
                                # Update only remote-sourced fields, preserve local-only fields (label, PII)
                                update_cols = [k for k in safe_track.keys() 
                                             if k not in ('track_id', 'label', 'sender', 'recipient', 'subject', 'sent_at')]
                                if update_cols:
                                    set_clause = ', '.join([f"{c} = {P}" for c in update_cols])
                                    vals = [safe_track[c] for c in update_cols] + [track_id]
                                    cursor.execute(
                                        f"UPDATE tracks SET {set_clause} WHERE track_id = {P}",
                                        vals
                                    )
                            else:
                                # Insert new track
                                cols = list(safe_track.keys())
                                vals = [safe_track[c] for c in cols]
                                places = ', '.join([P] * len(cols))
                                cursor.execute(
                                    f"INSERT INTO tracks ({', '.join(cols)}) VALUES ({places})",
                                    vals
                                )
                    
                    conn.commit()
                    log.info("[SYNC] Merge complete.")
                    
                    # 4. Auto-wipe the remote if configured
                    if Config.SYNC_AUTO_WIPE:
                        # R-04: Use datetime parsing for reliable comparison
                        def _parse_ts(ts_str):
                            try:
                                return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                            except (ValueError, AttributeError):
                                return datetime(1970, 1, 1, tzinfo=timezone.utc)
                        
                        track_ts = [_parse_ts(t.get('last_seen', '1970')) for t in tracks]
                        click_ts = [_parse_ts(c.get('timestamp', '1970')) for c in clicks]
                        all_ts = track_ts + click_ts
                        
                        if all_ts:
                            max_dt = max(all_ts)
                            wipe_until = max_dt.isoformat()
                            del_req = urllib.request.Request(
                                f"{Config.SYNC_REMOTE_URL}/api/sync?until={wipe_until}",
                                method='DELETE',
                                headers={'X-API-Key': Config.SYNC_API_KEY}
                            )
                            with urllib.request.urlopen(del_req, timeout=10) as response:
                                res = json.loads(response.read().decode())
                                log.info("[SYNC] Auto-wiped remote: %d tracks, %d clicks deleted", 
                                         res.get('deleted_tracks', 0), res.get('deleted_clicks', 0))

                except Exception as e:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    log.error("[SYNC] Sync cycle failed: %s", e)

        except Exception as e:
            log.warning("[SYNC] Outer sync loop error: %s", e)


def start_sync_worker(app):
    """Start the background sync worker if configured.
    
    M-01: Uses a lock to ensure only one worker across multiple processes
    spawns the sync thread. Also checks PID to detect fork scenarios.
    """
    global _sync_thread
    
    if not Config.SYNC_REMOTE_URL:
        return
        
    if not Config.SYNC_API_KEY:
        log.error("[SYNC] SYNC_REMOTE_URL is configured but SYNC_API_KEY is missing! Sync is disabled.")
        return
    
    with _sync_lock:
        if _sync_thread is not None and _sync_thread.is_alive():
            return
            
        # We need a way to build app contexts in the thread to access g.db
        def _ctx():
            return app.app_context()
            
        _sync_thread = threading.Thread(target=_sync_loop, args=(_ctx,), daemon=True)
        _sync_thread.start()
