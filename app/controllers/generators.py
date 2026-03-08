"""
Naarad - Pixel Generator Controller
Generates trackable links and batch colored pixels for testing.
"""

import os
import zlib
import struct
import logging
from flask import Blueprint, request, jsonify, current_app
from urllib.parse import quote
from .api import require_api_key
from ..utils import sanitize_id

log = logging.getLogger(__name__)

# Separate blueprint name from url_prefix to avoid collision with bp_api
bp_gen = Blueprint('generators', __name__, url_prefix='/api/gen')


@bp_gen.route('/link', methods=['POST'])
@require_api_key
def generate_link():
    """Generate a trackable pixel URL and click-through link."""
    data     = request.json or {}
    track_id = sanitize_id(data.get('track_id', 'unknown'))
    target_url = data.get('url')

    if not target_url:
        return jsonify({'error': 'URL required'}), 400

    encoded  = quote(target_url, safe='')
    base_url = request.host_url.rstrip('/')
    return jsonify({
        'pixel_url': f"{base_url}/track?id={track_id}",
        'click_url': f"{base_url}/click/{track_id}/{encoded}",
        'track_id':  track_id,
    })


@bp_gen.route('/pixels', methods=['POST'])
@require_api_key
def generate_pixels():
    """Generate a batch of named colored 1x1 PNG tracking pixels."""
    data  = request.json or {}
    names = data.get('names', [])

    if not names or not isinstance(names, list):
        return jsonify({'error': 'Provide a list of names'}), 400

    # Write pixels to the app's static directory so they can be served
    static_dir    = current_app.static_folder
    pixels_dir    = os.path.join(static_dir, 'pixels')
    os.makedirs(pixels_dir, exist_ok=True)

    colors = [
        (255, 0,   0),   (0,   0,   255), (0,   255, 0),   (255, 165, 0),
        (128, 0,   128), (0,   255, 255), (255, 0,   255), (255, 255, 0),
        (255, 105, 180), (0,   128, 128),
    ]

    generated = []
    for i, name in enumerate(names[:20]):   # sensible cap at 20
        safe_name = sanitize_id(name)
        color     = colors[i % len(colors)]
        png_data  = _create_colored_png(*color)
        filepath  = os.path.join(pixels_dir, f"{safe_name}.png")

        with open(filepath, 'wb') as fh:
            fh.write(png_data)

        generated.append({
            'name':      safe_name,
            'file':      filepath,
            'color':     f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}",
            'track_url': f"/track?id={safe_name}",
        })

    return jsonify({'generated': generated})


def _create_colored_png(r, g, b):
    """Create a 1×1 RGBA PNG with the given colour."""
    def chunk(chunk_type, data):
        c   = chunk_type + data
        crc = zlib.crc32(c) & 0xffffffff
        return struct.pack('>I', len(data)) + c + struct.pack('>I', crc)

    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b'IDAT', zlib.compress(bytes([0, r, g, b])))
    iend = chunk(b'IEND', b'')

    return sig + ihdr + idat + iend
