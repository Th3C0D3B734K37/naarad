
import re

def parse_user_agent(ua):
    """Parse user agent string for device/browser info."""
    if not ua:
        return {'browser': 'Unknown', 'browser_version': '', 'os': 'Unknown',
                'os_version': '', 'device_type': 'Unknown', 'device_brand': 'Unknown',
                'is_mobile': False, 'is_bot': False}
    
    ua_lower = ua.lower()
    
    browser, browser_version = 'Other', ''
    patterns = [
        (r'edg[e]?/([\d.]+)', 'Edge'),
        (r'opr/([\d.]+)', 'Opera'),
        (r'chrome/([\d.]+)', 'Chrome'),
        (r'firefox/([\d.]+)', 'Firefox'),
        (r'safari/([\d.]+)', 'Safari'),
    ]
    for pattern, name in patterns:
        match = re.search(pattern, ua_lower)
        if match:
            browser, browser_version = name, match.group(1)
            break
    
    if browser == 'Safari' and 'chrome' in ua_lower:
        match = re.search(r'chrome/([\d.]+)', ua_lower)
        if match:
            browser, browser_version = 'Chrome', match.group(1)
    
    os_name, os_version = 'Other', ''
    os_patterns = [
        (r'windows nt ([\d.]+)', 'Windows'),
        (r'mac os x ([\d_.]+)', 'macOS'),
        (r'android ([\d.]+)', 'Android'),
        (r'iphone os ([\d_]+)', 'iOS'),
        (r'linux', 'Linux'),
    ]
    for pattern, name in os_patterns:
        match = re.search(pattern, ua_lower)
        if match:
            os_name = name
            if match.lastindex:
                os_version = match.group(1).replace('_', '.')
            break
    
    is_mobile = any(x in ua_lower for x in ['mobile', 'android', 'iphone'])
    is_tablet = 'ipad' in ua_lower or 'tablet' in ua_lower
    is_bot = any(x in ua_lower for x in ['bot', 'crawler', 'spider', 'preview'])
    
    device_type = 'Desktop'
    if is_bot:
        device_type = 'Bot'
    elif is_mobile:
        device_type = 'Mobile'
    elif is_tablet:
        device_type = 'Tablet'
    
    device_brand = 'Unknown'
    if 'iphone' in ua_lower or 'ipad' in ua_lower or 'mac' in ua_lower:
        device_brand = 'Apple'
    elif 'samsung' in ua_lower:
        device_brand = 'Samsung'
    elif 'pixel' in ua_lower:
        device_brand = 'Google'
    
    return {
        'browser': browser, 'browser_version': browser_version,
        'os': os_name, 'os_version': os_version,
        'device_type': device_type, 'device_brand': device_brand,
        'is_mobile': is_mobile, 'is_bot': is_bot
    }
