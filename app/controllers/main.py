
from flask import Blueprint, render_template, Response

bp_main = Blueprint('main', __name__)

@bp_main.route('/')
@bp_main.route('/dashboard')
def dashboard():
    """Serve dashboard UI."""
    return render_template('dashboard.html')


@bp_main.route('/robots.txt')
def robots_txt():
    """Prevent search engines from indexing tracking endpoints."""
    return Response(
        "User-agent: *\nDisallow: /\n",
        mimetype='text/plain'
    )
