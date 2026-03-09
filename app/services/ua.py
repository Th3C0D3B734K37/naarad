"""
naarad - User-Agent Parsing
"""

import re


def _get_empty_ua():
    """Returns a dictionary with default 'Unknown' values for UA parsing."""
    return {
        'browser': 'Unknown', 'browser_version': '', 'os': 'Unknown',
        'os_version': '', 'device_type': 'Unknown', 'device_brand': 'Unknown',
        'is_mobile': False, 'is_bot': False
    }


def parse_user_agent(ua_string):
    """
    Parse a User-Agent string to extract browser, OS, and device type.
    Returns a dict with: browser, browser_version, os, os_version,
    device_type, device_brand, is_mobile, is_bot
    """
    if not ua_string:
        return _get_empty_ua()

    ua_lower = ua_string.lower()

    # ── Browser Detection ───────────────────────────────────────────────────
    # Order matters: most specific first to avoid misidentification.
    # Edge must come before Chrome; Opera before Chrome; Chromium before Chrome.
    browser, browser_version = 'Other', ''
    patterns = [
        (r'edg(?:e|\/)([\d.]+)', 'Edge'),
        (r'opr\/([\d.]+)', 'Opera'),
        (r'chromium\/([\d.]+)', 'Chromium'),
        (r'chrome\/([\d.]+)', 'Chrome'),
        (r'firefox\/([\d.]+)', 'Firefox'),
        # Safari must be last: Chrome/Edge UAs also contain "Safari/"
        (r'version\/([\d.]+).*safari', 'Safari'),
    ]
    for pattern, name in patterns:
        match = re.search(pattern, ua_lower)
        if match:
            browser, browser_version = name, match.group(1)
            break

    # ── OS Detection ────────────────────────────────────────────────────────
    os_name, os_version = 'Other', ''
    os_patterns = [
        (r'windows nt ([\d.]+)', 'Windows'),
        (r'mac os x ([\d_.]+)', 'macOS'),
        (r'android ([\d.]+)', 'Android'),
        (r'iphone os ([\d_]+)', 'iOS'),
        (r'ipad.*os ([\d_]+)', 'iPadOS'),
        (r'linux', 'Linux'),
    ]
    for pattern, name in os_patterns:
        match = re.search(pattern, ua_lower)
        if match:
            os_name = name
            if match.lastindex:
                os_version = match.group(1).replace('_', '.')
            break

    # ── Device Classification ───────────────────────────────────────────────
    # Check tablet before mobile: iPad sends "mobile safari" in some UAs.
    is_bot = any(x in ua_lower for x in [
        'bot', 'crawler', 'spider', 'preview', 'googlebot', 'bingbot',
        'slurp', 'duckduckbot', 'facebot', 'ia_archiver', 'ahrefsbot',
    ])
    is_tablet = (
        'ipad' in ua_lower or
        'tablet' in ua_lower or
        ('android' in ua_lower and 'mobile' not in ua_lower)  # Android tablet pattern
    )
    is_mobile = (
        not is_tablet and
        any(x in ua_lower for x in ['mobile', 'iphone', 'ipod'])
    )

    device_type = 'Desktop'
    if is_bot:
        device_type = 'Bot'
    elif is_tablet:
        device_type = 'Tablet'
    elif is_mobile:
        device_type = 'Mobile'

    # ── Brand Detection ─────────────────────────────────────────────────────
    device_brand = 'Unknown'
    if 'iphone' in ua_lower or 'ipad' in ua_lower or 'macintosh' in ua_lower:
        device_brand = 'Apple'
    elif 'samsung' in ua_lower:
        device_brand = 'Samsung'
    elif 'pixel' in ua_lower:
        device_brand = 'Google'
    elif 'huawei' in ua_lower:
        device_brand = 'Huawei'
    elif 'xiaomi' in ua_lower or 'redmi' in ua_lower:
        device_brand = 'Xiaomi'

    return {
        'browser': browser,
        'browser_version': browser_version,
        'os': os_name,
        'os_version': os_version,
        'device_type': device_type,
        'device_brand': device_brand,
        'is_mobile': is_mobile,
        'is_bot': is_bot,
    }
