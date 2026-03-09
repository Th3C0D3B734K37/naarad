# Deployment Guide

Deploying naarad makes it accessible from the internet, which is required if you want to track email opens sent to real clients (like Gmail or Outlook).

## Where to Deploy

naarad is a standard Python (Flask) application, meaning it can be deployed on almost any modern Platform as a Service (PaaS) or on a traditional VPS.

**Recommended PaaS Providers (Free/Low Cost):**
1. **Render** - Excellent free tier, native Python support, easy PostgreSQL integration.
2. **Railway** - Similar to Render, very fast deployments, includes database provisioning.
3. **Fly.io** - Good for deploying close to your users via Docker.
4. **Heroku** - Traditional choice, though free tiers are no longer available.

**Traditional VPS (Advanced):**
- **DigitalOcean, Linode (Akamai), AWS EC2** - You manage the OS, reverse proxy (Nginx/Caddy), and SSL yourself.

## How to Deploy (Render / Railway Example)

1. **Push to GitHub:** Ensure your naarad repository is updated on GitHub.
2. **Connect your PaaS:** Create an account on Render or Railway, and choose "New Web Service" (or Project).
3. **Select Repository:** Choose your `naarad` repository.
4. **Configure the Environment:**
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -w 1 -b 0.0.0.0:$PORT server:app` (or just `python server.py` if handled by Procfile)
5. **Set Environment Variables (CRITICAL):**
   - `SECRET_KEY`: Generate a random string (e.g., using `openssl rand -hex 32`)
   - `API_KEY`: A strong password you will use to log into the dashboard.
   - `DATABASE_URL`: Add a PostgreSQL database to your project and paste its connection URL here.
6. **Deploy:** Click Deploy. The system will build and run the app. The `Procfile` and `server.py` logic will automatically run database migrations if configured.

## Managing & Maintaining

### Database Backups
If using SQLite locally, simply copy the `data/tracking.db` file.
If using PostgreSQL on a PaaS, use your provider's built-in backup tools (e.g., `pg_dump`).

### Updating the Application
When new features are pushed to the GitHub repository:
1. Pull the latest changes.
2. If deploying on a PaaS, the new commit will usually trigger an automatic rebuild and deployment.
3. Database migrations (`manage.py init_all` or `server.py` production init) run automatically on boot to keep your schema updated.

### Monitoring
Check your PaaS dashboard for CPU, Memory usage, and standard HTTP logs. naarad logs errors and API requests to standard output.
