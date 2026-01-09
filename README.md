# Naarad (नारद) - Email Tracker

A simple, open-source email tracking pixel and link analytics service.

## Features
- **Open Tracking**: Invisible 1x1 pixel to track email opens.
- **Link Tracking**: Redirect service to track link clicks.
- **Detailed Analytics**: Geo-location, Device, Browser, OS, specific timestamps.
- **Privacy Focused**: Self-hosted, you own the data.

## Deployment Options

### 1. Local Development (Windows/Linux/Mac)
Good for testing or personal use on a single machine.

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Initialize Database**:
    ```bash
    python manage.py init_all
    ```
3.  **Run Server**:
    ```bash
    python server.py
    ```
    Access at `http://localhost:8080`.

### 2. Private Network (LAN)
To access the dashboard from other devices on your WiFi (e.g., test on phone):

1.  Follow "Local Development" steps.
2.  The server automatically binds to `0.0.0.0`.
3.  Find your local IP address (`ipconfig` on Windows, `ifconfig` on Mac/Linux).
4.  Open `http://<YOUR_IP>:8080` (e.g., `http://192.168.1.10:8080`) on your other device.
    *Note: Ensure your firewall allows traffic on port 8080.*

### 3. Production (Railway)
**Recommended for always-on usage.**

1.  **Deploy Code**: Push this repository to GitHub and link it in Railway.
2.  **Add Database**: In Railway, add a **PostgreSQL** database service.
3.  **Connect**: Link the Postgres variable `DATABASE_URL` to your web service.
    - Railway usually does this automatically if you add Postgres to the same project.
    - If not, go to Web Service -> Variables -> Add `DATABASE_URL` matching the Postgres connection string.
4.  **Auto-Init**: The app automatically runs database migrations on every deploy (defined in `Procfile`).

## Configuration
- `PORT`: Server port (default: 8080)
- `DATABASE_URL`: Postgres connection string (if set, uses Postgres. If not, uses local SQLite `tracking.db`).
- `API_KEY`: Protects the dashboard/stats (Optional, set in `config.py` or env vars).

## Troubleshooting
See [troubleshoot.md](troubleshoot.md) for common issues like "Internal Server Error" or connection problems.
