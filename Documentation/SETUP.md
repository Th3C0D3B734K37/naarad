# Setup Guide

Installation and deployment instructions for Naarad.

**Related Docs:**
- [USAGE.md](USAGE.md) - How to use tracking pixels
- [TESTING.md](TESTING.md) - Testing with email clients
- [DEVELOPERS.md](DEVELOPERS.md) - Code architecture

### Prerequisites

- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/Th3C0D3B734K37/naarad.git
cd naarad

# Install dependencies
pip install -r requirements.txt

# Run
python server.py
```

The server starts at `http://localhost:8080`

## Deployment

### Railway (Recommended)

Railway offers 500 free hours per month.

```bash
# Install CLI
npm install -g @railway/cli

# Login
railway login

# Initialize
railway init

# Deploy
railway up
```

Set environment variables in Railway dashboard:
- `PORT`: 8080
- `REQUIRE_AUTH`: true
- `API_KEY`: your-secret-key

### Render

1. Push code to GitHub
2. Create account at render.com
3. New Web Service > Connect repo
4. Settings:
   - Build: `pip install -r requirements.txt`
   - Start: `python server.py`
5. Add environment variables
6. Deploy

### Fly.io

```bash
# Install
curl -L https://fly.io/install.sh | sh

# Login
flyctl auth login

# Launch
flyctl launch

# Deploy
flyctl deploy
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "server.py"]
```

```bash
docker build -t naarad .
docker run -p 8080:8080 naarad
```

## Environment Variables

Create `.env` file:

```bash
# Server
PORT=8080
HOST=0.0.0.0

# Security
REQUIRE_AUTH=true
API_KEY=your-secret-key-here

# Optional
WEBHOOK_URL=https://your-webhook.com/endpoint
```

## Database

SQLite database is auto-created at `data/tracking.db`.

For production, back up this file regularly.

## Production Server

A `Procfile` is included for platforms like Railway/Heroku:

```
web: gunicorn server:app
```

Make sure `gunicorn` is in your `requirements.txt`.

## HTTPS

All deployment platforms provide automatic HTTPS.

For local development with HTTPS, use ngrok:

```bash
ngrok http 8080
```

