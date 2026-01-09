# Troubleshooting Naarad

## Common Issues

### 1. "Internal Server Error" (500) on Railway
**Cause:** Usually a missing database table or connection issue.
**Fix:**
- Check your Railway "Variables" tab. Ensure `DATABASE_URL` is set to `${{Postgres.DATABASE_URL}}`.
- Check "Deploy Logs". If you see `relation "tracks" does not exist`, the database initialization failed.
- **Solution:** Our new `Procfile` uses `manage.py init_all` to fix this automatically on deploy. Try clicking "Redeploy".

### 2. Logs show "sqlite3.OperationalError: database is locked" (Local)
**Cause:** Multiple processes are trying to write to `tracking.db` at the same time.
**Fix:**
- Stop all running python processes (`Ctrl+C` in all terminals).
- Run `python server.py` strictly in **one** terminal.

### 3. Changes not showing up on Railway
**Cause:** Code wasn't pushed or Railway environment variable is stale.
**Fix:**
- Run `git push origin main`.
- Check Railway dashboard to see if a new build triggered.

### 4. Cannot access Dashboard on Private Network
**Cause:** Firewall or incorrect IP binding.
**Fix:**
- Ensure `server.py` runs with `host='0.0.0.0'` (Default config does this).
- On Windows, when the firewall popup appears, check both "Private" and "Public" networks.
- Access via `http://<YOUR_LOCAL_IP>:8080` (e.g., `http://192.168.1.5:8080`).

## Database Management
We allow two modes:
1. **SQLite (Local)**: zero-config, stores data in `tracking.db`.
2. **PostgreSQL (Production/Railway)**: reliable, persistent.

To manually reset the local database:
```powershell
Remove-Item tracking.db
python manage.py init_all
```
