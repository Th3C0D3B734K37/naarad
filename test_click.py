import sqlite3

conn = sqlite3.connect('tracking.db')
cursor = conn.cursor()

# Test the click tracking record
cursor.execute('SELECT track_id, sender, recipient, subject, sent_at, ip_address, country, city, target_url, browser, device_type FROM clicks WHERE track_id = "test-enhanced" ORDER BY timestamp DESC LIMIT 1')
row = cursor.fetchone()

if row:
    print('=== Click Tracking Test Results ===')
    print(f'Track ID: {row[0]}')
    print(f'Sender: {row[1]}')
    print(f'Recipient: {row[2]}')
    print(f'Subject: {row[3]}')
    print(f'Sent At: {row[4]}')
    print(f'IP: {row[5]}')
    print(f'Location: {row[6]}, {row[7]}')
    print(f'Target URL: {row[8]}')
    print(f'Device: {row[9]} ({row[10]})')
    print('===================================')
else:
    print('No click record found for test-enhanced')

conn.close()
