"""
Rate Limiting Utilities for Cart Endpoints
Provides IP-based and Device ID-based rate limiting with proper security measures
"""
import uuid
import logging
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status
from accounts.utils import get_client_ip

logger = logging.getLogger('security')


def validate_device_id(device_id):
    """
    Validate device ID format (must be valid UUID).
    
    Args:
        device_id: Device ID string to validate
        
    Returns:
        tuple: (is_valid: bool, normalized_device_id: str or None)
    """
    if not device_id:
        return False, None
    
    # Normalize: trim spaces, lowercase
    device_id = device_id.strip().lower()
    
    # Validate UUID format
    try:
        # This will raise ValueError if not valid UUID
        uuid.UUID(device_id)
        return True, device_id
    except (ValueError, AttributeError, TypeError):
        # Invalid UUID format
        logger.warning(f"Invalid device ID format detected: {device_id[:20]}...")
        return False, None


def check_rate_limit(request, max_requests_per_minute=50, window_seconds=60):
    """
    Check rate limit for both IP address and device ID.
    Returns error response if rate limit exceeded, None otherwise.
    
    Args:
        request: Django request object
        max_requests_per_minute: Maximum requests allowed per minute
        window_seconds: Time window in seconds (default 60 = 1 minute)
        
    Returns:
        Response object if rate limited, None if OK
    """
    # Get client IP
    client_ip = get_client_ip(request)
    
    # Get device ID from header
    device_id = request.headers.get('X-Device-ID', '').strip()
    
    # Validate device ID format (only for guest users)
    if device_id and not request.user.is_authenticated:
        is_valid, normalized_device_id = validate_device_id(device_id)
        if not is_valid:
            logger.warning(f"Invalid device ID from IP {client_ip}")
            return Response({
                'detail': 'Invalid device ID format'
            }, status=status.HTTP_400_BAD_REQUEST)
        device_id = normalized_device_id
    
    # Rate limit by IP address
    ip_cache_key = f'rate_limit_ip_{client_ip}'
    ip_count = cache.get(ip_cache_key, 0)
    
    if ip_count >= max_requests_per_minute:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return Response({
            'detail': 'Too many requests, please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    # Increment IP counter
    cache.set(ip_cache_key, ip_count + 1, window_seconds)
    
    # Rate limit by device ID (for guest users)
    if device_id and not request.user.is_authenticated:
        device_cache_key = f'rate_limit_device_{device_id}'
        device_count = cache.get(device_cache_key, 0)
        
        if device_count >= max_requests_per_minute:
            logger.warning(f"Rate limit exceeded for device ID: {device_id[:8]}...")
            return Response({
                'detail': 'Too many requests, please try again later.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Increment device ID counter
        cache.set(device_cache_key, device_count + 1, window_seconds)
    
    # Rate limit passed
    return None


def enforce_cart_access_control(cart, request, normalized_device_id):
    """
    Ensure user can only access their own cart.
    
    Args:
        cart: Cart object
        request: Django request object
        normalized_device_id: Already validated and normalized device ID (for guest users)
        
    Returns:
        Response object if unauthorized, None if OK
    """
    # Authenticated users: cart must belong to them
    if request.user.is_authenticated:
        if cart.customer != request.user:
            logger.warning(f"Unauthorized cart access attempt: User {request.user.id} tried to access cart {cart.id}")
            return Response({
                'detail': 'Unauthorized cart access'
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Guest users: device ID must match cart's session_key
    else:
        if not normalized_device_id:
            return Response({
                'detail': 'Device ID required for guest users'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if device ID matches cart's session_key
        if cart.session_key != normalized_device_id:
            logger.warning(f"Unauthorized cart access attempt: Device {normalized_device_id[:8]}... tried to access cart {cart.id}")
            return Response({
                'detail': 'Unauthorized cart access'
            }, status=status.HTTP_403_FORBIDDEN)
    
    return None

