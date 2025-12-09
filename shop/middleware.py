"""
Global Rate Limiting Middleware
Applies rate limiting to all API endpoints with configurable limits per URL pattern
"""
import re
import logging
from django.core.cache import cache
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from accounts.utils import get_client_ip

logger = logging.getLogger('security')


class GlobalRateLimitMiddleware:
    """
    Middleware that applies rate limiting to all requests based on URL patterns.
    More restrictive limits for critical endpoints (login, registration, etc.)
    """
    
    # URL patterns with their specific rate limits
    # Format: (pattern_regex, max_requests, window_seconds, description)
    RATE_LIMIT_RULES = [
        # Critical authentication endpoints - reasonable limits for production
        (r'^/accounts/token/$', 20, 60, 'Login'),  # 20 requests per minute (allows tier system to work)
        (r'^/accounts/register/', 20, 3600, 'Registration'),  # 20 registrations per hour (reasonable for real users)
        (r'^/accounts/password-reset/', 10, 3600, 'Password Reset'),  # 10 password resets per hour
        (r'^/accounts/verify-email/', 10, 60, 'Email Verification'),  # 10 requests per minute
        (r'^/accounts/token/refresh/', 20, 60, 'Token Refresh'),  # 20 requests per minute
        
        # Supplier authentication
        (r'^/suppliers/auth/login/', 5, 60, 'Supplier Login'),
        (r'^/suppliers/auth/register/', 2, 3600, 'Supplier Registration'),
        (r'^/suppliers/auth/password-reset/', 3, 3600, 'Supplier Password Reset'),
        
        # High-priority endpoints - already have specific limits in views
        # (These will be handled by view-level rate limiting, but middleware provides backup)
        (r'^/shop/api/customer/checkout/', 30, 60, 'Checkout'),
        (r'^/shop/api/customer/cart/', 50, 60, 'Cart'),
        
        # Order management endpoints
        (r'^/shop/api/customer/orders/.*/cancel/', 10, 3600, 'Order Cancellation'),  # 10 per hour
        (r'^/shop/api/customer/orders/.*/return/', 5, 3600, 'Order Return'),  # 5 per hour
        (r'^/shop/api/customer/orders/', 30, 60, 'Order Queries'),  # 30 per minute
        
        # Address and profile management
        (r'^/accounts/customer/addresses/', 100, 3600, 'Address Management'),  # 100 per hour
        (r'^/accounts/profile/', 20, 3600, 'Profile Update'),  # 20 per hour
        
        # Wishlist operations
        (r'^/shop/api/wishlist/', 30, 60, 'Wishlist'),
        (r'^/shop/api/v1/wishlist/', 30, 60, 'Wishlist API'),
        
        # Search endpoints - prevent scraping
        (r'^/shop/api/products/advanced-search/', 50, 60, 'Advanced Search'),  # 50 per minute
        (r'^/shop/api/products/search/', 100, 60, 'Product Search'),  # 100 per minute
        
        # Default rate limit for all other API endpoints
        (r'^/.*api/.*', 100, 60, 'General API'),  # 100 requests per minute for any API
    ]
    
    # URLs to exclude from rate limiting
    EXCLUDED_PATTERNS = [
        r'^/$',  # Root/home page
        r'^/admin/',  # Admin panel (has its own authentication)
        r'^/static/',  # Static files
        r'^/media/',   # Media files
        r'^/favicon\.ico',  # Favicon
        r'^/__debug__/',  # Django debug toolbar (if used)
        r'^/health/',  # Health check endpoint
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Compile regex patterns for performance
        self.rate_limit_patterns = [
            (re.compile(pattern), max_req, window, desc)
            for pattern, max_req, window, desc in self.RATE_LIMIT_RULES
        ]
        self.excluded_patterns = [
            re.compile(pattern) for pattern in self.EXCLUDED_PATTERNS
        ]
    
    def __call__(self, request):
        try:
            # Skip rate limiting for excluded URLs
            if self._is_excluded(request.path):
                return self.get_response(request)
            
            # Get rate limit for this URL
            rate_limit = self._get_rate_limit(request.path)
            
            if rate_limit:
                max_requests, window_seconds, description = rate_limit
                
                # Check rate limit
                error_response = self._check_rate_limit(
                    request, 
                    max_requests, 
                    window_seconds, 
                    description
                )
                
                if error_response:
                    return error_response
            
            # Continue with the request
            return self.get_response(request)
        except Exception as e:
            # If middleware fails completely, log and continue (fail open)
            logger.error(f"Critical error in rate limit middleware: {str(e)}")
            return self.get_response(request)
    
    def _is_excluded(self, path):
        """Check if URL path should be excluded from rate limiting"""
        for pattern in self.excluded_patterns:
            if pattern.match(path):
                return True
        return False
    
    def _get_rate_limit(self, path):
        """
        Get rate limit configuration for a given URL path.
        Returns (max_requests, window_seconds, description) or None
        """
        # Check patterns in order (most specific first)
        for pattern, max_req, window, desc in self.rate_limit_patterns:
            if pattern.match(path):
                return (max_req, window, desc)
        return None
    
    def _check_rate_limit(self, request, max_requests, window_seconds, description):
        """
        Check if request exceeds rate limit.
        Returns error response if rate limited, None otherwise.
        """
        try:
            # Get client IP
            client_ip = get_client_ip(request)
            
            # Create cache key based on IP and path
            cache_key = f'rate_limit_middleware_{client_ip}_{request.path}'
            
            # Get current request count (with error handling)
            try:
                request_count = cache.get(cache_key, 0)
            except Exception as e:
                # If cache fails, log and allow request (fail open)
                logger.error(f"Cache error in rate limiting: {str(e)}")
                return None
            
            # Check if limit exceeded
            if request_count >= max_requests:
                logger.warning(
                    f"Rate limit exceeded: {description} - "
                    f"IP: {client_ip}, Path: {request.path}, "
                    f"Count: {request_count}/{max_requests}"
                )
                
                # Return appropriate response based on request type
                if request.headers.get('Content-Type') == 'application/json' or \
                   request.path.startswith('/api/') or \
                   request.path.startswith('/shop/api/') or \
                   request.path.startswith('/accounts/token/') or \
                   request.path.startswith('/suppliers/auth/'):
                    # API request - return JSON
                    return JsonResponse({
                        'detail': f'Too many requests. Limit: {max_requests} requests per {window_seconds} seconds.'
                    }, status=429)
                else:
                    # Regular request - return JSON anyway for consistency
                    return JsonResponse({
                        'detail': f'Too many requests. Please try again later.'
                    }, status=429)
            
            # Increment counter (with error handling)
            try:
                cache.set(cache_key, request_count + 1, window_seconds)
            except Exception as e:
                # If cache fails, log but allow request (fail open)
                logger.error(f"Cache error setting rate limit: {str(e)}")
            
            return None
        except Exception as e:
            # If anything fails, log and allow request (fail open)
            logger.error(f"Error in rate limit middleware: {str(e)}")
            return None

