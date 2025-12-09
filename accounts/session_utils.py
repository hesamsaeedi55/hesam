"""
Session Management Utilities
Device fingerprinting, session tracking, and helper functions
"""

from django.utils import timezone
from datetime import timedelta
import re

# Optional import - if user_agents is not installed, use fallback
try:
    import user_agents
    USER_AGENTS_AVAILABLE = True
except ImportError:
    USER_AGENTS_AVAILABLE = False
    user_agents = None


def parse_device_info(request):
    """
    Extract device information from the request.
    Supports both mobile app (with device_info in body) and web browsers.
    
    Returns dict with:
    - device_name: str
    - device_type: str (ios, android, web, etc.)
    - device_id: str
    - app_version: str
    - os_version: str
    - user_agent: str
    """
    result = {
        'device_name': '',
        'device_type': '',
        'device_id': '',
        'app_version': '',
        'os_version': '',
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
    }
    
    # Check if device_info is provided in request body (mobile app)
    device_info = request.data.get('device_info', {}) if hasattr(request, 'data') else {}
    
    if device_info:
        # Mobile app provides structured device info
        result['device_name'] = device_info.get('name', '')  # e.g., "iPhone 14 Pro"
        result['device_type'] = device_info.get('platform', '').lower()  # ios, android
        result['device_id'] = device_info.get('id', '')  # identifierForVendor
        result['app_version'] = device_info.get('app_version', '')  # "1.0.5"
        result['os_version'] = device_info.get('os_version', '')  # "iOS 17.1"
    else:
        # Web browser - parse from user agent
        user_agent_str = result['user_agent']
        if user_agent_str and USER_AGENTS_AVAILABLE:
            try:
                ua = user_agents.parse(user_agent_str)
                
                # Device type
                if ua.is_mobile:
                    result['device_type'] = 'mobile_web'
                elif ua.is_tablet:
                    result['device_type'] = 'tablet_web'
                elif ua.is_pc:
                    result['device_type'] = 'desktop_web'
                else:
                    result['device_type'] = 'web'
                
                # Device name (browser + device)
                parts = []
                if ua.browser.family:
                    parts.append(ua.browser.family)
                if ua.os.family:
                    parts.append(ua.os.family)
                if ua.device.family and ua.device.family != 'Other':
                    parts.append(ua.device.family)
                
                result['device_name'] = ' - '.join(parts) if parts else 'Web Browser'
                
                # OS version
                if ua.os.family and ua.os.version_string:
                    result['os_version'] = f"{ua.os.family} {ua.os.version_string}"
            except Exception:
                # Fallback if parsing fails
                result['device_type'] = 'web'
                result['device_name'] = 'Web Browser'
        elif user_agent_str:
            # Fallback without user_agents library
            result['device_type'] = 'web'
            result['device_name'] = 'Web Browser'
    
    return result


def get_client_ip(request):
    """
    Get the client's real IP address, considering proxies.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def get_location_from_ip(ip_address):
    """
    Get approximate location from IP address.
    Uses a simple approach - in production, use a service like MaxMind GeoIP2.
    
    Returns dict with:
    - city: str
    - country: str
    """
    # Placeholder implementation
    # In production, use:
    # - MaxMind GeoIP2: https://dev.maxmind.com/geoip/geoip2/geolite2/
    # - ipapi: https://ipapi.com/
    # - ip-api: https://ip-api.com/
    
    return {
        'city': '',
        'country': ''
    }


def create_or_update_session(user, request, access_token, refresh_token):
    """
    Create or update user session after successful login.
    
    Args:
        user: Customer instance
        request: Django request object
        access_token: JWT access token object
        refresh_token: JWT refresh token object
    
    Returns:
        UserSession instance
    """
    from .models import UserSession
    
    # Parse device info
    device_info = parse_device_info(request)
    ip_address = get_client_ip(request)
    location = get_location_from_ip(ip_address)
    
    # Get JWT IDs
    access_jti = str(access_token.get('jti', ''))
    refresh_jti = str(refresh_token.get('jti', ''))
    
    # Calculate expiration (from refresh token)
    refresh_exp = refresh_token.get('exp')
    if refresh_exp:
        expires_at = timezone.datetime.fromtimestamp(refresh_exp, tz=timezone.utc)
    else:
        # Default: 30 days
        expires_at = timezone.now() + timedelta(days=30)
    
    # Check if session already exists for this device
    device_id = device_info.get('device_id')
    existing_session = None
    
    if device_id:
        # Try to find existing session by device_id
        existing_session = UserSession.objects.filter(
            user=user,
            device_id=device_id,
            is_active=True
        ).first()
    
    if existing_session:
        # Update existing session
        existing_session.session_key = access_jti
        existing_session.refresh_token_jti = refresh_jti
        existing_session.ip_address = ip_address
        existing_session.user_agent = device_info['user_agent']
        existing_session.last_activity = timezone.now()
        existing_session.expires_at = expires_at
        existing_session.location_city = location['city']
        existing_session.location_country = location['country']
        existing_session.save()
        return existing_session
    else:
        # Create new session
        session = UserSession.objects.create(
            user=user,
            session_key=access_jti,
            refresh_token_jti=refresh_jti,
            device_name=device_info['device_name'],
            device_type=device_info['device_type'],
            device_id=device_id,
            app_version=device_info['app_version'],
            os_version=device_info['os_version'],
            ip_address=ip_address,
            user_agent=device_info['user_agent'],
            location_city=location['city'],
            location_country=location['country'],
            expires_at=expires_at,
        )
        return session


def validate_token_version(user, token):
    """
    Validate that the token's version matches the user's current token_version.
    If version mismatch, the token has been invalidated.
    
    Args:
        user: Customer instance
        token: JWT token payload (dict)
    
    Returns:
        bool: True if valid, False if invalidated
    """
    token_version = token.get('token_version', 0)
    try:
        user_token_version = getattr(user, 'token_version', 0)
    except Exception:
        # Column doesn't exist, assume version 0
        user_token_version = 0
    return token_version == user_token_version


def cleanup_expired_sessions():
    """
    Clean up expired sessions.
    Should be run periodically (e.g., daily cron job).
    """
    from .models import UserSession
    
    cutoff = timezone.now()
    expired = UserSession.objects.filter(
        is_active=True,
        expires_at__lt=cutoff
    )
    
    count = expired.count()
    expired.update(
        is_active=False,
        revoked_at=cutoff,
        revoked_reason='expired'
    )
    
    return count

