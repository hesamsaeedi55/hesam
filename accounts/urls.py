from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views
from .views import (
    CustomerAddressesListView, 
    CustomerAddressUpdateView, 
    GoogleAuthView, 
    CustomTokenRefreshView,
    UnlockAccountView,
    ResendVerificationCodeView,
    SecurityDashboardView,
    CheckSecurityStatusView,
    DeleteAccountView,
    UserSessionsListView,
    RevokeSessionView,
    RevokeAllSessionsView,
    CurrentSessionView,
    ChangePasswordView,
)

app_name = 'accounts'

urlpatterns = [
    # ========================================================================
    # EXISTING WEB VIEWS
    # ========================================================================
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verify-email/<uuid:token>/', views.verify_email, name='verify_email'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/<uuid:token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('profile/', views.profile, name='profile'),
    path('admin/addresses/', views.admin_address_view, name='admin_addresses'),
    path('admin/addresses/update/', views.admin_update_address_field, name='admin_address_update'),
    path('shopping/', views.customer_shopping_interface, name='customer_shopping'),
    
    # ========================================================================
    # JWT TOKEN ENDPOINTS (Enhanced with Security)
    # ========================================================================
    path('token/', views.EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    
    # ========================================================================
    # USER DETAIL ENDPOINTS
    # ========================================================================
    path('user/', views.UserDetailView.as_view(), name='user_detail'),
    path('customer/', views.CustomerUserDetailView.as_view(), name='customer_detail'),
    path('customer/address/', views.CustomerAddressView.as_view(), name='customer_address'),
    path('customer/addresses/', CustomerAddressesListView.as_view(), name='customer_addresses'),
    path('customer/addresses/<int:address_id>/', CustomerAddressUpdateView.as_view(), name='customer_address_update'),
    
    # ========================================================================
    # SECURITY ENDPOINTS (NEW)
    # ========================================================================
    # Unlock account via email link
    path('unlock/<str:token>/', UnlockAccountView.as_view(), name='unlock_account'),
    
    # Resend verification code
    path('resend-code/', ResendVerificationCodeView.as_view(), name='resend_verification_code'),
    
    # Check security status
    path('security/status/', CheckSecurityStatusView.as_view(), name='security_status'),
    
    # Security dashboard
    path('security/dashboard/', SecurityDashboardView.as_view(), name='security_dashboard'),
    
    # ========================================================================
    # ACCOUNT MANAGEMENT (Apple App Store Requirements)
    # ========================================================================
    # Change password (requires authentication + current password)
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    # Delete account (requires authentication + password confirmation)
    path('delete-account/', DeleteAccountView.as_view(), name='delete_account'),
    
    # ========================================================================
    # SESSION MANAGEMENT - Multi-device tracking and control
    # ========================================================================
    # List all active sessions/devices
    path('sessions/', UserSessionsListView.as_view(), name='sessions_list'),
    
    # Get current session info
    path('sessions/current/', CurrentSessionView.as_view(), name='current_session'),
    
    # Revoke all sessions (logout from all devices)
    path('sessions/revoke-all/', RevokeAllSessionsView.as_view(), name='revoke_all_sessions'),
    
    # Revoke specific session (logout from one device)
    path('sessions/<int:session_id>/', RevokeSessionView.as_view(), name='revoke_session'),
    
    # ========================================================================
    # AUTHENTICATION
    # ========================================================================
    path('auth/google', GoogleAuthView.as_view(), name='google-auth'),
]
