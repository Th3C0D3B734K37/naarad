
from flask import Blueprint, render_template

bp_main = Blueprint('main', __name__)

@bp_main.route('/')
@bp_main.route('/dashboard')
def dashboard():
    """Serve dashboard UI."""
    return render_template('dashboard.html')
