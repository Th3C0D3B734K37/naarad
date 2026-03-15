import sqlite3
import datetime

def test_enhanced(db):
    """
    Test that the enhanced tracking record is created and correctly retrieved
    (Translated from former test_enhanced.py/test_tracking.py script).
    """
    cursor = db.cursor()
    # Insert a dummy record first because we have a fresh DB in tests!
    now = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO tracks (
            timestamp, open_date, open_time, day_of_week, unix_ms, 
            track_id, sender, recipient, subject, sent_at, 
            ip_address, country, city, latitude, longitude, 
            browser, device_type, open_count, is_repeat, is_forward, forward_count
        ) VALUES (
            ?, ?, ?, ?, ?, 
            ?, ?, ?, ?, ?, 
            ?, ?, ?, ?, ?, 
            ?, ?, ?, ?, ?, ?
        )
    ''', (
        now, "2026-03-15", "10:00:00", "Sunday", 123456789000,
        "test-enhanced", "sender@example.com", "recipient@example.com", "Welcome", "2026-03-15T09:00:00",
        "192.168.1.1", "US", "New York", 40.7128, -74.0060,
        "Chrome", "Desktop", 1, 0, 0, 0
    ))
    db.commit()

    # Original script query
    cursor.execute('''
        SELECT track_id, sender, recipient, subject, sent_at, 
               ip_address, country, city, latitude, longitude, 
               browser, device_type, open_count, open_date, open_time, 
               day_of_week, is_repeat, is_forward, forward_count 
        FROM tracks 
        WHERE track_id = "test-enhanced" 
        ORDER BY timestamp DESC LIMIT 1
    ''')
    row = cursor.fetchone()
    
    assert row is not None
    assert row['track_id'] == "test-enhanced"
    assert row['sender'] == "sender@example.com"
    assert row['recipient'] == "recipient@example.com"
    assert row['subject'] == "Welcome"
    assert row['ip_address'] == "192.168.1.1"
    assert row['country'] == "US"
    assert row['latitude'] == 40.7128
    assert row['browser'] == "Chrome"
    assert row['device_type'] == "Desktop"
    assert row['open_count'] == 1


def test_click(db):
    """
    Test that the click tracking record is created and correctly retrieved
    (Translated from former test_click.py script).
    """
    cursor = db.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO clicks (
            timestamp, click_date, click_time, day_of_week, unix_ms,
            track_id, link_id, target_url, ip_address, country, city, 
            browser, device_type, sender, recipient, subject, sent_at
        ) VALUES (
            ?, ?, ?, ?, ?, 
            ?, ?, ?, ?, ?, ?, 
            ?, ?, ?, ?, ?, ?
        )
    ''', (
        now, "2026-03-15", "11:00:00", "Sunday", 123456789000,
        "test-enhanced", "link123", "https://example.com/target", "192.168.1.1", "US", "New York",
        "Chrome", "Desktop", "sender@example.com", "recipient@example.com", "Welcome", "2026-03-15T09:00:00"
    ))
    db.commit()

    # Original script query
    cursor.execute('''
        SELECT track_id, sender, recipient, subject, sent_at, 
               ip_address, country, city, target_url, browser, device_type 
        FROM clicks 
        WHERE track_id = "test-enhanced" 
        ORDER BY timestamp DESC LIMIT 1
    ''')
    row = cursor.fetchone()

    assert row is not None
    assert row['track_id'] == "test-enhanced"
    assert row['sender'] == "sender@example.com"
    assert row['target_url'] == "https://example.com/target"
    assert row['browser'] == "Chrome"
    assert row['device_type'] == "Desktop"
