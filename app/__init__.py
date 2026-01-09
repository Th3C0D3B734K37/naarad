"""
Naarad - App Package
"""
from flask import Flask
from flask_cors import CORS

from .config import Config
from .database import init_db, close_db

def create_app():
    """Create and configure Flask app."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    app.teardown_appcontext(close_db)
    CORS(app)
    
    # Register Modular Blueprints
    from .controllers.tracking import bp_track
    from .controllers.api import bp_api
    from .controllers.generators import bp_gen
    from .controllers.main import bp_main
    
    app.register_blueprint(bp_track)
    app.register_blueprint(bp_api)
    app.register_blueprint(bp_gen)
    app.register_blueprint(bp_main)
    
    return app
