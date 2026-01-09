
import os
import zlib
import struct
from flask import Blueprint, request, jsonify
from urllib.parse import quote
from .api import require_api_key
from ..utils import sanitize_id

bp_gen = Blueprint('generators', __name__, url_prefix='/api')

@bp_gen.route('/generate', methods=['POST'])
@require_api_key
def generate_link():
    """Generate trackable link."""
    data = request.json or {}
    track_id = sanitize_id(data.get('track_id', 'unknown'))
    target_url = data.get('url')
    
    if not target_url:
        return jsonify({'error': 'URL required'}), 400
    
    encoded = quote(target_url, safe='')
    return jsonify({
        'pixel_url': f"/track?id={track_id}",
        'click_url': f"/click/{track_id}/{encoded}",
        'track_id': track_id
    })

@bp_gen.route('/pixels/generate', methods=['POST'])
@require_api_key
def generate_pixels():
    """Generate batch of colored tracking pixels."""
    data = request.json or {}
    names = data.get('names', [])
    
    if not names or not isinstance(names, list):
        return jsonify({'error': 'Provide list of names'}), 400
    
    # Default colors to cycle through
    colors = [
        (255, 0, 0), (0, 0, 255), (0, 255, 0), (255, 165, 0),
        (128, 0, 128), (0, 255, 255), (255, 0, 255), (255, 255, 0),
        (255, 105, 180), (0, 128, 128)
    ]
    
    pixels_dir = 'pixels'
    os.makedirs(pixels_dir, exist_ok=True)
    
    generated = []
    for i, name in enumerate(names[:20]):  # Max 20
        safe_name = sanitize_id(name)
        color = colors[i % len(colors)]
        
        # Create PNG
        png_data = create_colored_png(*color)
        filepath = os.path.join(pixels_dir, f"{safe_name}.png")
        
        with open(filepath, 'wb') as f:
            f.write(png_data)
        
        generated.append({
            'name': safe_name,
            'file': filepath,
            'color': f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}",
            'track_url': f"/track?id={safe_name}"
        })
    
    return jsonify({'generated': generated})

def create_colored_png(r, g, b):
    """Create a 1x1 PNG with specified color."""
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = zlib.crc32(c) & 0xffffffff
        return struct.pack('>I', len(data)) + c + struct.pack('>I', crc)
    
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b'IDAT', zlib.compress(bytes([0, r, g, b])))
    iend = chunk(b'IEND', b'')
    
    return sig + ihdr + idat + iend
