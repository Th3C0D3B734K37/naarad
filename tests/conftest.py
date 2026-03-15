import os
import pytest
import sqlite3
import tempfile
from app import create_app
from app.database import init_db, migrate_db
from app.config import Config
import app.database as app_db

@pytest.fixture
def app():
    # Set up a temporary database file
    db_fd, db_path = tempfile.mkstemp()
    
    # Force Config to use temporary DB
    Config.DB_FILE = db_path
    Config.DATABASE_URL = None
    app_db.USE_POSTGRES = False
    
    flask_app = create_app()
    # Configure app for testing
    flask_app.config.update({
        "TESTING": True,
        "DB_FILE": db_path,
    })
    
    # Initialize the database
    with flask_app.app_context():
        init_db()
        migrate_db()
        
    yield flask_app
    
    # Teardown
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def db(app):
    with app.app_context():
        conn = sqlite3.connect(app.config['DB_FILE'])
        conn.row_factory = sqlite3.Row
        yield conn
        conn.close()
