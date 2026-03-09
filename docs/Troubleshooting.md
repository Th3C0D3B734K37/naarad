# Troubleshooting

Common issues and how to resolve them when setting up or running naarad.

## Local Development Issues

### Port 8080 is already in use
**Error:** `Address already in use` or `socket.error: [Errno 98]`
**Solution:** Change the `PORT` environment variable.
```bash
# Windows
set PORT=5000
python server.py
# Linux/Mac
export PORT=5000
python server.py
```

### Dashboard returns 401 Unauthorized
**Cause:** You are trying to access an API or dashboard without the correct API Key.
**Solution:** Check the terminal output when the server started. If `DEBUG=true` (or unset locally), it generated an ephemeral API key. Click the "Settings" gear in the UI and paste the key. For production, ensure you've set the `API_KEY` environment variable.

### Database locked error
**Error:** `sqlite3.OperationalError: database is locked`
**Cause:** Multiple processes are trying to write to the SQLite database simultaneously, or a previous process crashed holding a lock.
**Solution:** Stop all running server instances and restart. If deploying to production, switch to PostgreSQL instead of SQLite.

## Tracking & Email Issues

### Pixel isn't tracking in Gmail
**Cause:** Gmail heavily caches images on their own proxy servers. The first open will be logged with a Google IP address, and subsequent opens by the same user might not register if Gmail serves it from cache.
**Solution:** Ensure you are using unique `id` query parameters for each email sent. You can also append random cache-busting parameters if testing, but the primary tracking relies on the first load.

### Link tracking shows incorrect location
**Cause:** The IP-based geolocation isn't 100% accurate, especially for mobile networks and corporate VPNs.
**Solution:** This is normal internet behavior. The geo-service (`ip-api.com`) updates its database regularly, but IPs move.

## Sync Module Issues

### Edge nodes aren't syncing to central server
**Checklist:**
1. Ensure `SYNC_REMOTE_URL` on the edge node strictly points to the central server's domain/IP (e.g., `https://central.my-naarad.com`).
2. Verify `SYNC_API_KEY` on the edge node EXACTLY matches the `API_KEY` of the central server.
3. Check the central server's logs for incoming `POST /api/tracks` requests to see if they are being rejected.
