# Setup Guide

This guide covers how to set up naarad on your local machine for personal use or development.

## Prerequisites
- Python 3.8+
- SQLite (included in Python) or PostgreSQL (for production)
- Git

## Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Th3C0D3B734K37/naarad.git
   cd naarad
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database:**
   ```bash
   python manage.py init_all
   ```
   This will create a `data/tracking.db` SQLite database with the necessary tables.

5. **Run the server:**
   ```bash
   python server.py
   ```
   The server will start on `http://localhost:8080`.

## Configuration Options

You can set various environment variables before running the server to customize its behavior.

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Port to listen on |
| `DEBUG` | `false` | Enables debug mode and generates ephemeral keys |
| `API_KEY` | *(auto-generated if DEBUG)* | Secret key to access the dashboard |
| `SECRET_KEY` | *(auto-generated if DEBUG)* | Flask secret key for sessions |

Create a `.env` file in the root directory and place these variables there, or export them in your shell session.

Next, you might want to look at the [Testing](Testing.md) guide or the [Deployment](Deployment.md) guide.
