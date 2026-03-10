import sqlite3

conn = sqlite3.connect('tracking.db')
cursor = conn.cursor()

# Test the enhanced tracking record
cursor.execute('SELECT track_id, sender, recipient, subject, sent_at, ip_address, country, city, latitude, longitude, browser, device_type, open_count, open_date, open_time, day_of_week, is_repeat, is_forward, forward_count FROM tracks WHERE track_id = "test-enhanced-v2" ORDER BY timestamp DESC LIMIT 1')
row = cursor.fetchone()

if row:
    print('=== Enhanced Tracking Test Results ===')
    print(f'Track ID: {row[0]}')
    print(f'Sender: {row[1]}')
    print(f'Recipient: {row[2]}')
    print(f'Subject: {row[3]}')
    print(f'Sent At: {row[4]}')
    print(f'IP: {row[5]}')
    print(f'Location: {row[6]}, {row[7]} ({row[8]}, {row[9]})')
    print(f'Device: {row[10]} ({row[11]})')
    print(f'Opens: {row[12]}')
    print(f'Date: {row[13]}')
    print(f'Time: {row[14]}')
    print(f'Day: {row[15]}')
    print(f'Is Repeat: {row[16]}')
    print(f'Is Forward: {row[17]}')
    print(f'Forward Count: {row[18]}')
    print('=====================================')
else:
    print('No record found for test-enhanced-v2')

conn.close()
