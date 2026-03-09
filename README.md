# naarad (नारद) - Email Tracker

A simple, self-hosted email tracking pixel and link analytics service.

## Features
- **Open Tracking**: Invisible 1×1 pixel to track email opens
- **Link Tracking**: Secure click-through redirect with open-redirect protection
- **Modern Dashboard**: Responsive UI with search, inline detail drawer, charts, and pagination
- **Rich Analytics**: Geo-location, ISP/ASN, device, browser, OS, and full HTTP header fingerprint
- **Security**: Timing-safe API key auth, HMAC-signed webhooks, HSTS, CSP, rate limiting
- **Privacy First**: Self-hosted — you own the data
- **Multi-Node Sync**: Optional pull-based sync from edge nodes to a central server

## Quick Start (Local)

```bash
pip install -r requirements.txt
python manage.py init_all
python server.py                 # http://localhost:8080
```

Set `DEBUG=true` if you want auto-generated ephemeral keys (printed in the console).

## Deployment

### Local / LAN
1. Follow Quick Start above.
2. Server binds to `0.0.0.0:8080` by default. Open `http://<YOUR_IP>:8080` from any device on your network.

### Production (Railway / Render / Fly.io)
1. Push this repo to GitHub and connect it to your PaaS.
2. Add a **PostgreSQL** service and set its `DATABASE_URL`.
3. **Set required env vars** (the app refuses to start without them in production):
   - `SECRET_KEY` — any random string (e.g. `openssl rand -hex 32`)
   - `API_KEY` — authenticates dashboard and API calls
4. Deploy. The `Procfile` runs migrations automatically on every deploy.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | HTTP listen port |
| `DEBUG` | `false` | Enable debug mode (auto-generates ephemeral keys) |
| `DATABASE_URL` | *(none)* | PostgreSQL connection string. Uses SQLite if unset. |
| `SECRET_KEY` | **required in prod** | Flask session signing key |
| `API_KEY` | **required in prod** | Dashboard / API authentication key |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |
| `TRUSTED_PROXY_COUNT` | `0` | Number of reverse proxies in front of the app |
| `WEBHOOK_URL` | *(none)* | URL to POST open/click events to |
| `WEBHOOK_SECRET` | *(none)* | HMAC-SHA256 signing key for webhook payloads |
| `GEO_API_URL` | `http://ip-api.com/json/{ip}` | Geo-lookup endpoint template |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max tracking requests per IP per minute |
| `API_RATE_LIMIT_PER_MINUTE` | `120` | Max API requests per IP per minute |
| `SYNC_REMOTE_URL` | *(none)* | Remote Naarad node URL for pull-sync |
| `SYNC_API_KEY` | *(none)* | API key for the remote sync node |
| `SYNC_INTERVAL` | `300` | Seconds between sync cycles |
| `SYNC_AUTO_WIPE` | `false` | Delete synced records from the remote after pull |

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/track?id=…` | — | Serve 1×1 tracking pixel |
| `GET` | `/click/<id>/<url>` | — | Record click and redirect |
| `GET` | `/dashboard` | — | Dashboard HTML |
| `GET` | `/api/health` | — | Health check (DB status) |
| `GET` | `/api/stats` | ✔ | Aggregated statistics |
| `GET` | `/api/tracks` | ✔ | List tracked pixels |
| `POST` | `/api/track` | ✔ | Create a new pixel |
| `GET` | `/api/track/<id>` | ✔ | Pixel detail + click history |
| `PUT` | `/api/track/<id>` | ✔ | Update label / metadata |
| `DELETE` | `/api/track/<id>` | ✔ | Delete pixel and its data |
| `GET` | `/api/export` | ✔ | CSV / JSON export |
| `GET` | `/api/sync/status` | ✔ | Sync configuration status |
| `POST` | `/api/sync` | ✔ | Trigger manual sync |

Auth = `X-API-Key` header required.

## Troubleshooting

See [troubleshoot.md](troubleshoot.md) for common issues.
