from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from shop.views import delete_product_image, home
from .admin import admin_site
from . import views

# Import views with error handling to prevent startup failures
try:
    from accounts.views import EmailTokenObtainPairView, UserDetailView, CustomerUserDetailView, CustomTokenRefreshView
except ImportError as e:
    # If import fails, log and use fallback
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import account views: {str(e)}")
    # Use a simple fallback view that will show the error
    from rest_framework.views import APIView
    from rest_framework.response import Response
    from rest_framework import status
    
    class EmailTokenObtainPairView(APIView):
        def post(self, request):
            return Response({
                'error': 'Login endpoint not available',
                'detail': 'Account views failed to load. Check server logs.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    class CustomTokenRefreshView(APIView):
        def post(self, request):
            return Response({
                'error': 'Token refresh not available',
                'detail': 'Account views failed to load. Check server logs.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    class UserDetailView(APIView):
        def get(self, request):
            return Response({'error': 'User detail not available'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    class CustomerUserDetailView(APIView):
        def get(self, request):
            return Response({'error': 'Customer detail not available'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

urlpatterns = [
    # Health check endpoint (simple, no dependencies)
    path('health/', views.health_check, name='health_check'),
    
    # JWT endpoints
    path('token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    
    # Admin and other endpoints
    path('admin/', admin_site.urls),  # Custom admin site
    path('', home, name='home'),  # Root URL for home page
    path('accounts/', include('accounts.urls')),  # custom urls
    path('accounts/', include('django.contrib.auth.urls')),  # built-in views
    path('accounts/', include('allauth.urls')),
    path('shop/', include('shop.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('image-editor/', include('image_editor.urls')),
    path('admin/shop/productimage/<int:image_id>/delete/', delete_product_image, name='delete_product_image'),
    path('user/', UserDetailView.as_view(), name='user_detail'),
    path('customer/user/', CustomerUserDetailView.as_view(), name='customer_user_detail'),
    path('auth/google', views.google_auth_view, name='google_auth'),
]

# Serve media files in both DEBUG and production (Render)
# In production, you should use a CDN or cloud storage, but this works for now
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # For production on Render, serve media files
    from django.views.static import serve
    from django.urls import re_path
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]




