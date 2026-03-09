"""
naarad - App Package
"""
import logging
from flask import Flask, jsonify

from .config import Config
from .database import close_db

# Configure structured logging for the entire app
logging.basicConfig(
    level=logging.DEBUG if Config.DEBUG else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
)

log = logging.getLogger(__name__)


def create_app():
    """Create and configure Flask app."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # S-04: Trust proxy headers if we're behind a reverse proxy
    proxy_count = Config.TRUSTED_PROXY_COUNT
    if proxy_count > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=proxy_count,
            x_proto=proxy_count,
            x_host=proxy_count,
            x_prefix=proxy_count
        )

    app.teardown_appcontext(close_db)

    # ── CORS ─────────────────────────────────────────────────────────────
    from flask_cors import CORS
    if Config.DEBUG:
        CORS(app)
    elif Config.CORS_ORIGINS:
        # Explicit allowed origins (comma-separated env var)
        origins = [o.strip() for o in Config.CORS_ORIGINS.split(',') if o.strip()]
        CORS(app, resources={r'/api/*': {'origins': origins}})
    else:
        # Same-origin only — no extra CORS headers needed
        CORS(app, resources={r'/api/*': {'origins': []}})

    # ── Register Blueprints ──────────────────────────────────────────────
    from .controllers.tracking import bp_track
    from .controllers.api import bp_api
    from .controllers.generators import bp_gen
    from .controllers.main import bp_main

    app.register_blueprint(bp_track)
    app.register_blueprint(bp_api)
    app.register_blueprint(bp_gen)
    app.register_blueprint(bp_main)

    # ── Security Headers (CSP, CSRF-adjacent) ────────────────────────────
    @app.after_request
    def add_security_headers(response):
        # L-10: Content-Security-Policy
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=()'
        # S-03: HSTS in production to enforce HTTPS
        if not Config.DEBUG:
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )
        return response

    # ── Global Error Handlers ────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error': 'Bad request', 'message': str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'error': 'Unauthorized'}), 401

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'error': 'Method not allowed'}), 405

    @app.errorhandler(429)
    def too_many_requests(e):
        return jsonify({'error': 'Too many requests'}), 429

    @app.errorhandler(500)
    def internal_error(e):
        log.exception("Unhandled 500 error")
        return jsonify({'error': 'Internal server error'}), 500

    # ── Start Background Sync ────────────────────────────────────────────
    from .services.sync import start_sync_worker
    start_sync_worker(app)

    return app
