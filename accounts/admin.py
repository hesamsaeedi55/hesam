"""
Django Admin configuration for accounts app with security models
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Customer,
    Address,
    LoginAttempt,
    AccountLock,
    VerificationCode,
    UserSession,
)


# ============================================================================
# CUSTOMER ADMIN
# ============================================================================

@admin.register(Customer)
class CustomerAdmin(UserAdmin):
    """Custom admin for Customer model"""
    list_display = ['email', 'first_name', 'last_name', 'is_active', 'is_email_verified', 'created_at']
    list_filter = ['is_active', 'is_email_verified', 'is_staff', 'created_at']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number', 'date_of_birth')}),
        ('Address', {'fields': ('street_address', 'city', 'state', 'country', 'postal_code')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Email Verification', {'fields': ('is_email_verified', 'email_verification_token', 'email_verification_sent_at')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'email_verification_token']


# ============================================================================
# ADDRESS ADMIN
# ============================================================================

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Admin for Address model"""
    list_display = ['customer', 'label', 'receiver_name', 'city', 'province', 'phone', 'created_at']
    list_filter = ['city', 'province', 'created_at']
    search_fields = ['customer__email', 'receiver_name', 'city', 'street_address']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Customer', {'fields': ('customer',)}),
        ('Address Details', {
            'fields': ('label', 'receiver_name', 'street_address', 'city', 'province', 'vahed', 'postal_code', 'country')
        }),
        ('Contact', {'fields': ('phone',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    readonly_fields = ['created_at', 'updated_at']


# ============================================================================
# SECURITY MODELS ADMIN
# ============================================================================

@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Admin for LoginAttempt model - Security monitoring"""
    list_display = [
        'email',
        'ip_address',
        'success',
        'security_tier',
        'failure_reason',
        'created_at'
    ]
    list_filter = [
        'success',
        'security_tier',
        'failure_reason',
        'created_at'
    ]
    search_fields = ['email', 'ip_address', 'user_agent']
    ordering = ['-created_at']
    readonly_fields = [
        'email',
        'ip_address',
        'user_agent',
        'success',
        'failure_reason',
        'security_tier',
        'response_time_ms',
        'country_code',
        'created_at'
    ]
    
    fieldsets = (
        ('Attempt Details', {
            'fields': ('email', 'ip_address', 'success', 'failure_reason')
        }),
        ('Security', {
            'fields': ('security_tier', 'response_time_ms')
        }),
        ('Location', {
            'fields': ('country_code',)
        }),
        ('Device', {
            'fields': ('user_agent',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual addition of login attempts"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion only for superusers"""
        return request.user.is_superuser
    
    actions = ['delete_selected']
    
    def get_queryset(self, request):
        """Optimize query by prefetching related objects"""
        qs = super().get_queryset(request)
        return qs.select_related()


@admin.register(AccountLock)
class AccountLockAdmin(admin.ModelAdmin):
    """Admin for AccountLock model - Locked accounts management"""
    list_display = [
        'email',
        'is_active',
        'reason',
        'attempt_count',
        'locked_at',
        'expires_at',
        'unlocked_by'
    ]
    list_filter = [
        'is_active',
        'reason',
        'unlocked_by',
        'locked_at'
    ]
    search_fields = ['email', 'ip_addresses']
    ordering = ['-locked_at']
    readonly_fields = [
        'email',
        'customer',
        'locked_at',
        'unlock_token',
        'unlock_token_expires',
        'reason',
        'attempt_count',
        'ip_addresses',
        'email_sent',
        'email_sent_at',
        'unlocked_at',
        'unlocked_by'
    ]
    
    fieldsets = (
        ('Account Info', {
            'fields': ('email', 'customer', 'is_active')
        }),
        ('Lock Details', {
            'fields': ('reason', 'attempt_count', 'locked_at', 'expires_at')
        }),
        ('Unlock Token', {
            'fields': ('unlock_token', 'unlock_token_expires'),
            'classes': ('collapse',)
        }),
        ('Attack Context', {
            'fields': ('ip_addresses',),
            'classes': ('collapse',)
        }),
        ('Email Notification', {
            'fields': ('email_sent', 'email_sent_at')
        }),
        ('Unlock Status', {
            'fields': ('unlocked_at', 'unlocked_by')
        }),
    )
    
    actions = ['unlock_accounts', 'delete_selected']
    
    def unlock_accounts(self, request, queryset):
        """Admin action to manually unlock selected accounts"""
        count = 0
        for lock in queryset.filter(is_active=True):
            lock.unlock(method='admin')
            count += 1
        
        self.message_user(
            request,
            f'Successfully unlocked {count} account(s).'
        )
    
    unlock_accounts.short_description = "Unlock selected accounts"
    
    def has_add_permission(self, request):
        """Prevent manual addition of locks"""
        return False


@admin.register(VerificationCode)
class VerificationCodeAdmin(admin.ModelAdmin):
    """Admin for VerificationCode model - Email verification codes"""
    list_display = [
        'email',
        'code',
        'is_used',
        'attempts',
        'created_at',
        'expires_at'
    ]
    list_filter = [
        'is_used',
        'created_at'
    ]
    search_fields = ['email', 'code', 'ip_address']
    ordering = ['-created_at']
    readonly_fields = [
        'email',
        'code',
        'ip_address',
        'created_at',
        'expires_at',
        'is_used',
        'used_at',
        'attempts',
        'max_attempts'
    ]
    
    fieldsets = (
        ('Code Details', {
            'fields': ('email', 'code', 'ip_address')
        }),
        ('Usage Status', {
            'fields': ('is_used', 'used_at', 'attempts', 'max_attempts')
        }),
        ('Validity', {
            'fields': ('created_at', 'expires_at')
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual addition of codes"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion only for superusers"""
        return request.user.is_superuser
    
    actions = ['delete_expired_codes']
    
    def delete_expired_codes(self, request, queryset):
        """Delete expired verification codes"""
        from django.utils import timezone
        expired = queryset.filter(expires_at__lt=timezone.now())
        count = expired.count()
        expired.delete()
        
        self.message_user(
            request,
            f'Deleted {count} expired code(s).'
        )
    
    delete_expired_codes.short_description = "Delete expired codes"


# ============================================================================
# ADMIN SITE CUSTOMIZATION
# ============================================================================

admin.site.site_header = "Customer Platform Admin"
admin.site.site_title = "Admin Portal"
admin.site.index_title = "Welcome to Customer Platform Administration"



# ============================================================================
# USER SESSION ADMIN - Multi-device tracking
# ============================================================================

# Register UserSession admin (only if model exists and table is created)
try:
    from .models import UserSession
    
    @admin.register(UserSession)
    class UserSessionAdmin(admin.ModelAdmin):
        list_display = (
            'user', 
            'device_display', 
            'device_type',
            'ip_address',
            'location_display',
            'is_active',
            'created_at',
            'last_activity'
        )
        list_filter = ('is_active', 'device_type', 'created_at')
        search_fields = ('user__email', 'device_name', 'ip_address', 'device_id')
        readonly_fields = (
            'user',
            'session_key',
            'refresh_token_jti',
            'device_name',
            'device_type',
            'device_id',
            'app_version',
            'os_version',
            'ip_address',
            'user_agent',
            'location_city',
            'location_country',
            'created_at',
            'last_activity',
            'expires_at',
            'revoked_at',
            'revoked_reason'
        )
        
        fieldsets = (
            ('Session Info', {
                'fields': ('user', 'session_key', 'refresh_token_jti', 'is_active')
            }),
            ('Device Info', {
                'fields': (
                    'device_name',
                    'device_type',
                    'device_id',
                    'app_version',
                    'os_version',
                    'user_agent'
                )
            }),
            ('Network Info', {
                'fields': ('ip_address', 'location_city', 'location_country')
            }),
            ('Timestamps', {
                'fields': ('created_at', 'last_activity', 'expires_at', 'revoked_at', 'revoked_reason')
            }),
        )
        
        actions = ['revoke_selected_sessions']
        
        def device_display(self, obj):
            return obj.get_device_display()
        device_display.short_description = 'Device'
        
        def location_display(self, obj):
            return obj.get_location_display()
        location_display.short_description = 'Location'
        
        def revoke_selected_sessions(self, request, queryset):
            """Admin action to revoke multiple sessions"""
            active_sessions = queryset.filter(is_active=True)
            count = active_sessions.count()
            
            for session in active_sessions:
                session.revoke(reason='admin_action')
            
            self.message_user(request, f"{count} session(s) revoked.")
        revoke_selected_sessions.short_description = "Revoke selected active sessions"
except ImportError:
    # UserSession model not available (migrations not run yet)
    pass
