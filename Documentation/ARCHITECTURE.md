# Naarad (नारद) - Architecture

## System Overview

Naarad is a modular, lightweight Flask application designed for email tracking. It uses a clean separation of concerns with dedicated packages for controllers, services, and utilities.

## Directory Structure

```
/
├── app/                        # Main Application Package
│   ├── __init__.py             # Flask App Factory
│   ├── config.py               # Configuration & Environment Variables
│   ├── database.py             # SQLite Database Interface
│   ├── utils.py                # Core Helpers (Sanitization, Hashing)
│   │
│   ├── controllers/            # Route Handlers (Blueprints)
│   │   ├── tracking.py         # Pixel & Click Tracking (/track, /click)
│   │   ├── api.py              # Dashboard Data API (/api/*)
│   │   ├── generators.py       # Link & Pixel Generation
│   │   └── main.py             # UI Routes (/, /dashboard)
│   │
│   ├── services/               # Business Logic
│   │   ├── geo.py              # IP Geolocation (ip-api.com)
│   │   └── ua.py               # User-Agent Parsing
│   │
│   ├── templates/              
│   │   └── dashboard.html      # Dashboard UI Template
│   │
│   └── static/
│       ├── style.css           # Main CSS (imports modules)
│       ├── script.js           # Frontend Logic
│       └── css/                # Modular CSS
│           ├── base.css        # Variables, Reset, Typography
│           ├── layout.css      # Header, Footer, Container
│           ├── components.css  # Cards, Buttons, Tables
│           └── modal.css       # Drawer/Modal Styles
│
├── Documentation/              # Project Documentation
│   ├── ARCHITECTURE.md         # This file (structure overview)
│   ├── DEVELOPERS.md           # Code logic & extension guide
│   ├── SETUP.md                # Installation & Deployment
│   ├── TESTING.md              # Testing guide (local/network/internet)
│   └── USAGE.md                # User Guide
│
├── data/                       # Runtime Data
│   └── tracking.db             # SQLite Database (Auto-generated)
│
├── server.py                   # Application Entry Point
├── Procfile                    # Production Server Command
├── README.md                   # Project Overview
└── requirements.txt            # Python Dependencies
```

## Key Modules

### Controllers (`app/controllers/`)
- **tracking.py**: Serves 1x1 pixel, records opens/clicks.
- **api.py**: JSON endpoints for dashboard stats and data.
- **generators.py**: Creates trackable links and batch pixels.
- **main.py**: Serves the dashboard HTML.

### Services (`app/services/`)
- **geo.py**: Fetches location data from ip-api.com with caching.
- **ua.py**: Parses User-Agent strings for device/browser info.

### Database (`app/database.py`)
Tables:
- `tracks`: Stores open events (IP, UA, Geo, Sender, Recipient).
- `clicks`: Stores link click events.
- `geo_cache`: Caches IP geolocation lookups.

## Data Flow

1. **Email Open**: User opens email → Request to `/track` → `tracking.track_open` → DB Insert → Return 1x1 PNG.
2. **Dashboard**: Admin visits `/dashboard` → `main.dashboard` → Render `dashboard.html` → Fetch `/api/stats` → JS renders data.
