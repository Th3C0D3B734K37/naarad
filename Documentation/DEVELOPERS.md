# Developer Guide

Technical documentation for contributors who want to understand, modify, or extend Naarad.

**Related Docs:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - Project structure overview
- [SETUP.md](SETUP.md) - Installation & deployment
- [TESTING.md](TESTING.md) - Testing guide

---

## Code Architecture

### Application Factory Pattern

Naarad uses Flask's application factory pattern in `app/__init__.py`:

```python
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(bp_track)
    app.register_blueprint(bp_api)
    app.register_blueprint(bp_gen)
    app.register_blueprint(bp_main)
    
    return app
```

This allows for easy testing and multiple app instances.

---

## Request Flow

### Email Open Tracking

```
1. Email client requests: GET /track?id=xyz&sender=...
                              │
2. tracking.py: track_open()  │
   ├── Extract query params   │
   ├── get_client_ip()        │ ──► Check proxy headers
   ├── get_geo_info(ip)       │ ──► services/geo.py (IP lookup + cache)
   ├── parse_user_agent(ua)   │ ──► services/ua.py (browser/device parsing)
   ├── extract_headers()      │ ──► Capture all HTTP headers
   │
3. Database                    
   ├── Check if track_id exists
   ├── UPDATE (increment) or INSERT (new)
   │
4. Return 1x1 transparent PNG
   └── Headers: no-cache, Accept-CH (request client hints)
```

### Click Tracking

```
1. User clicks: GET /click/{track_id}/{encoded_url}
                    │
2. tracking.py: track_click()
   ├── Decode target URL
   ├── Collect geo + UA info
   ├── INSERT into clicks table
   ├── UPDATE tracks.click_count
   │
3. HTTP 302 Redirect to target URL
```

### Dashboard

```
1. Browser: GET /dashboard
   └── main.py renders dashboard.html

2. JavaScript (script.js):
   ├── fetch('/api/stats')     ──► Summary + charts
   ├── fetch('/api/tracks')    ──► Recent events table
   └── Render UI, attach event handlers
```

---

## Module Responsibilities

### Controllers (`app/controllers/`)

| File | Purpose |
|------|---------|
| `tracking.py` | Core tracking logic: `/track`, `/click`, `/favicon.ico` |
| `api.py` | Data API: `/api/stats`, `/api/tracks`, `/api/export` |
| `generators.py` | Link generation: `/api/generate`, `/api/pixels/generate` |
| `main.py` | UI routes: `/`, `/dashboard` |

### Services (`app/services/`)

| File | Purpose |
|------|---------|
| `geo.py` | IP geolocation via ip-api.com with SQLite caching |
| `ua.py` | User-Agent string parsing (browser, OS, device detection) |

### Core (`app/`)

| File | Purpose |
|------|---------|
| `config.py` | Environment variables and defaults |
| `database.py` | SQLite connection, schema init, migrations |
| `utils.py` | Helpers: sanitization, hashing, webhooks |

---

## Database Schema

### `tracks` Table

```sql
-- Core identifiers
id              INTEGER PRIMARY KEY
timestamp       TEXT        -- ISO format
track_id        TEXT        -- User-provided ID
campaign_id     TEXT        -- Optional grouping

-- Email context
sender          TEXT
recipient       TEXT
subject         TEXT
sent_at         TEXT

-- Network
ip_address      TEXT
country         TEXT
region          TEXT
city            TEXT
latitude        REAL
longitude       REAL
timezone        TEXT
isp             TEXT
org             TEXT        -- Organization name
asn             TEXT        -- Autonomous System Number

-- Device
user_agent      TEXT
browser         TEXT
browser_version TEXT
os              TEXT
os_version      TEXT
device_type     TEXT        -- Desktop/Mobile/Tablet/Bot
device_brand    TEXT
is_mobile       BOOLEAN
is_bot          BOOLEAN

-- HTTP Headers
referer         TEXT
accept_language TEXT
accept_encoding TEXT
accept_header   TEXT
connection_type TEXT
do_not_track    TEXT
cache_control   TEXT

-- Client Hints
sec_ch_ua           TEXT
sec_ch_ua_mobile    TEXT
sec_ch_ua_platform  TEXT

-- Counters
open_count      INTEGER DEFAULT 1
click_count     INTEGER DEFAULT 0
first_seen      TEXT
last_seen       TEXT
```

### `clicks` Table

```sql
id              INTEGER PRIMARY KEY
timestamp       TEXT
track_id        TEXT
campaign_id     TEXT
link_id         TEXT        -- Hash of target URL
target_url      TEXT
ip_address      TEXT
country         TEXT
city            TEXT
user_agent      TEXT
browser         TEXT
os              TEXT
device_type     TEXT
referer         TEXT
```

### `geo_cache` Table

```sql
ip_address      TEXT PRIMARY KEY
data            TEXT        -- JSON blob
cached_at       TEXT        -- For TTL checking
```

---

## Adding Features

### New API Endpoint

1. Add route to appropriate controller:

```python
# app/controllers/api.py
@bp_api.route('/my-endpoint')
@require_api_key
def my_endpoint():
    # Your logic
    return jsonify({'result': data})
```

### New Database Column

1. Add to schema in `database.py`
2. Add to `migrate_db()` function:

```python
new_columns = [
    ('my_column', 'TEXT'),
]
```

3. Update tracking controller to capture the data
4. Update `openDetail()` in `script.js` to display it

### New Service

1. Create file in `app/services/`
2. Add to `app/services/__init__.py`
3. Import in controllers as needed

---

## Frontend Architecture

### CSS Modules

```
app/static/
├── style.css       # Just imports
├── css/
│   ├── base.css        # Variables: --bg, --accent, --text, etc.
│   ├── layout.css      # Header, footer, container, grid
│   ├── components.css  # Cards, buttons, tables, stats
│   └── modal.css       # Drawer/modal with animations
```

### JavaScript Structure

```javascript
// script.js
load()              // Fetch and render all data
renderChart()       // Render bar charts
renderTracks()      // Render events table
openDetail()        // Show event modal
closeModal()        // Hide modal
esc()               // XSS-safe string escaping
exportData()        // Trigger CSV download
```

---

## Security Considerations

### Input Sanitization

All user input is sanitized:
```python
def sanitize_id(track_id):
    cleaned = re.sub(r'[^\w\-@.+]', '', str(track_id))
    return cleaned[:100]
```

### API Authentication

Optional API key protection:
```python
@require_api_key
def protected_endpoint():
    # Only accessible with valid X-API-Key header
```

### XSS Prevention

JavaScript escapes all dynamic content:
```javascript
function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
```

---

## Testing

### Manual Testing

```bash
# Test pixel
curl "http://localhost:8080/track?id=test"

# Test with params
curl "http://localhost:8080/track?id=dev_test&sender=me&recipient=you"

# Test click
curl -L "http://localhost:8080/click/test/https://example.com"

# Test API
curl "http://localhost:8080/api/stats"
```

### Database Inspection

```bash
sqlite3 data/tracking.db
sqlite> .tables
sqlite> SELECT * FROM tracks LIMIT 5;
sqlite> .quit
```

---

## Performance Notes

- **Geolocation caching**: IP lookups cached for 60 minutes (configurable)
- **Database indexes**: On `track_id`, `timestamp`, `country`, `device_type`
- **No external dependencies**: Pure Python + Flask, no heavy ORMs
- **Lazy imports**: `urllib.request` imported inside functions

---

## Troubleshooting Development

| Issue | Solution |
|-------|----------|
| Import errors | Check `__init__.py` in packages |
| Database locked | Close other connections, restart server |
| Changes not showing | Hard refresh (Ctrl+Shift+R) |
| New columns missing | Run server once to trigger `migrate_db()` |
