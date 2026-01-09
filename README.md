# Naarad (नारद)

A lightweight, open-source email tracking server for personal use and learning.

Developed by [musashi](https://www.linkedin.com/in/gayathra-bhatt/)

---

## Features

- **Tracking Pixel** - Invisible 1x1 PNG served on email open
- **Click Tracking** - Track link clicks with automatic redirect
- **Geolocation** - IP-based location lookup (country, city, ISP, org, ASN)
- **Device Detection** - Browser, OS, device type parsing from User-Agent
- **Client Hints** - Modern browser detection via Sec-CH-UA headers
- **Dashboard** - Dark-themed responsive UI with real-time stats
- **REST API** - JSON endpoints for all data
- **Export** - CSV/JSON data export
- **Webhooks** - Optional notifications on events

---

## Quick Start

```bash
# Clone
git clone https://github.com/Th3C0D3B734K37/naarad.git
cd naarad

# Install
pip install -r requirements.txt

# Run
python server.py

# Open
http://localhost:8080
```

---

## Usage

### Track Email Opens

```html
<img src="https://YOUR_SERVER/track?id=recipient@email.com" width="1" height="1" />
```

### With Metadata

```html
<img src="https://YOUR_SERVER/track?id=proposal_v1&sender=me&recipient=client@gmail.com&subject=Quote" width="1" height="1" />
```

### Track Link Clicks

```html
<a href="https://YOUR_SERVER/click/recipient/https%3A%2F%2Fexample.com">Click here</a>
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/track?id=ID` | GET | Serve tracking pixel |
| `/click/ID/URL` | GET | Track click & redirect |
| `/api/stats` | GET | Dashboard statistics |
| `/api/tracks` | GET | List tracking events |
| `/api/track/ID` | GET | Event details |
| `/api/export` | GET | Export data (CSV/JSON) |
| `/api/generate` | POST | Generate trackable links |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Server port |
| `HOST` | 0.0.0.0 | Bind address |
| `DEBUG` | false | Debug mode |
| `REQUIRE_AUTH` | false | Require API key |
| `API_KEY` | (random) | API key for protected endpoints |
| `WEBHOOK_URL` | none | Webhook notification URL |

---

## Documentation

| Guide | Description |
|-------|-------------|
| [SETUP.md](Documentation/SETUP.md) | Installation & deployment (Railway, Render, Docker) |
| [USAGE.md](Documentation/USAGE.md) | User guide for tracking emails |
| [TESTING.md](Documentation/TESTING.md) | Testing locally, on network, and with email clients |
| [DEVELOPERS.md](Documentation/DEVELOPERS.md) | Code architecture, workflows, and extension guide |
| [ARCHITECTURE.md](Documentation/ARCHITECTURE.md) | Project structure overview |

---

## Project Structure

```
naarad/
├── app/
│   ├── controllers/     # Route handlers (tracking, api, generators)
│   ├── services/        # Business logic (geo, ua parsing)
│   ├── static/css/      # Modular CSS (4 files)
│   ├── templates/       # Dashboard HTML
│   ├── config.py        # Environment configuration
│   ├── database.py      # SQLite interface + migrations
│   └── utils.py         # Sanitization, hashing, webhooks
├── Documentation/       # 5 guide files
├── server.py            # Entry point
├── Procfile             # Production server (gunicorn)
└── requirements.txt     # Flask, Flask-CORS, gunicorn
```

---

## Data Captured

Each tracking event captures:

**Network:** IP address, country, city, region, timezone, ISP, organization, ASN

**Device:** User-Agent, browser, OS, device type, brand, mobile/bot detection

**Headers:** Accept, Accept-Encoding, Accept-Language, DNT, Cache-Control, Referer

**Client Hints:** Sec-CH-UA, Sec-CH-UA-Mobile, Sec-CH-UA-Platform

**Custom:** sender, recipient, subject, campaign, sent_at

---

## License

MIT License - See [LICENSE](LICENSE)

---

## Disclaimer

For educational and personal use. Comply with privacy laws (GDPR, CAN-SPAM) when tracking emails.
