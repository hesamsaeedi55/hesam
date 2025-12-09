from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from .models import Customer, Address
from .security_service import LoginSecurityService
from .email_service import SecurityEmailService
import logging

logger = logging.getLogger('security')
User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Enhanced JWT Token serializer with 5-tier progressive security.
    Implements rate limiting, progressive delays, CAPTCHA, email verification, and account locking.
    """
    username_field = User.EMAIL_FIELD
    
    # Add optional field for email verification (Tier 4)
    verification_code = serializers.CharField(required=False, allow_blank=True, write_only=True)
    
    def validate(self, attrs):
        """
        Enhanced validation with complete security checks.
        Falls back to basic authentication if security features fail.
        """
        # Extract email and normalize
        email = attrs.get(self.username_field, '').lower().strip()
        password = attrs.get('password')
        
        # Get request object (passed from view)
        request = self.context.get('request')
        
        # Try to use security features, fallback to basic auth if they fail
        use_security = request and hasattr(request, 'META')
        security = None
        security_check = None
        
        if use_security:
            try:
                # Initialize security service
                security = LoginSecurityService(request, email)
                
                # ====================================================================
                # STEP 1: Pre-authentication security checks
                # ====================================================================
                security_check = security.check_security()
                
                if not security_check['allowed']:
                    # Account is locked or rate limited
                    try:
                        security.record_attempt(
                            success=False,
                            failure_reason=security_check.get('message', 'rate_limited'),
                            security_tier=security_check['tier']
                        )
                    except Exception as record_error:
                        # If recording fails, log but don't fail the request
                        logger.warning(f"Failed to record login attempt: {str(record_error)}")
                    
                    raise AuthenticationFailed(security_check['message'])
            except AuthenticationFailed:
                # Re-raise authentication failures (they're intentional)
                raise
            except Exception as e:
                # Security features failed, log and continue without them
                logger.warning(f"Security features unavailable: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                security = None
                security_check = None
        
        tier = security_check['tier'] if security_check else 1
        
        # ====================================================================
        # STEP 2: Tier-specific requirements BEFORE authentication
        # ====================================================================
        
        # Only check tier-specific requirements if security is active
        if security and security_check:
            # Tier 3: NO CAPTCHA (removed - not needed for mobile apps)
            # Just continues to normal authentication
            
            # Tier 4: Email Verification Required
            if security_check.get('requires_verification'):
                verification_code = attrs.get('verification_code', '')
                
                if not verification_code:
                    # Generate and send code
                    code_obj = security.create_verification_code()
                    SecurityEmailService.send_verification_code_email(
                        email=email,
                        code=code_obj.code,
                        expires_minutes=10,
                        ip_address=security.ip_address
                    )
                    
                    security.record_attempt(
                        success=False,
                        failure_reason='verification_required',
                        security_tier=tier
                    )
                    
                    raise ValidationError({
                        'verification_required': True,
                        'message': 'Verification code sent to your email. Please enter it to continue.'
                    })
                
                # Verify the code
                is_valid, message = security.verify_code(verification_code)
                if not is_valid:
                    security.record_attempt(
                        success=False,
                        failure_reason='verification_required',
                        security_tier=tier
                    )
                    raise ValidationError({
                        'verification_required': True,
                        'message': message
                    })
                
                # Code verified successfully - continue to authentication
        
        # ====================================================================
        # STEP 3: Attempt authentication
        # ====================================================================
        try:
            # Call parent class validation (performs actual authentication)
            data = super().validate(attrs)
            
            # Authentication successful!
            if security:
                try:
                    security.handle_successful_login()
                except Exception as e:
                    logger.warning(f"Could not record successful login: {str(e)}")
            
            # ================================================================
            # SESSION MANAGEMENT: Create or update user session
            # ================================================================
            try:
                from .session_utils import create_or_update_session
                from rest_framework_simplejwt.tokens import RefreshToken
                from django.db import OperationalError
                
                # Get the tokens
                refresh = RefreshToken(data['refresh'])
                access = refresh.access_token
                
                # Create/update session
                session = create_or_update_session(
                    user=self.user,
                    request=request,
                    access_token=access.payload,
                    refresh_token=refresh.payload
                )
                
                logger.info(
                    f"Session created/updated: {self.user.email} - "
                    f"{session.get_device_display()} (ID: {session.id})"
                )
            except OperationalError as e:
                # Table doesn't exist (migrations not run) - don't fail login
                logger.warning(f"UserSession table not found (migrations pending): {str(e)}")
            except Exception as session_error:
                # Don't fail login if session tracking fails
                logger.error(f"Failed to create session: {str(session_error)}")
            
            # Add user_id to response
            data['user_id'] = self.user.id
            
            # Add security context to response
            data['security'] = {
                'tier': tier,
                'message': 'Login successful'
            }
            
            return data
            
        except AuthenticationFailed as e:
            # ================================================================
            # STEP 4: Handle failed authentication
            # ================================================================
            if security:
                try:
                    result = security.handle_failed_login(reason='invalid_credentials')
                    
                    # ============================================================
                    # Handle tier-specific actions BEFORE raising exception
                    # ============================================================
                    
                    # Tier 5: Lock account
                    if result.get('lock_created'):
                        lock_token = result.get('unlock_token')
                        
                        # Send lock email
                        from .models import AccountLock
                        lock = AccountLock.objects.get(unlock_token=lock_token)
                        SecurityEmailService.send_account_locked_email(lock)
                        
                        raise AuthenticationFailed(result['message'])
                    
                    # Tier 4: Send verification code
                    elif result.get('verification_code_sent'):
                        raise ValidationError({
                            'verification_required': True,
                            'message': result['message']
                        })
                    
                    # Tier 1-3: Generic error (no email spam)
                    else:
                        raise AuthenticationFailed(result.get('message', 'Invalid email or password'))
                    
                except Exception as security_error:
                    logger.error(f"Security handling failed: {str(security_error)}")
                    # Fallback: raise basic authentication error
                    raise AuthenticationFailed("Invalid email or password")
            else:
                # No security features - basic error message
                raise AuthenticationFailed("Invalid email or password")
    
    @classmethod
    def get_token(cls, user):
        """Add custom claims to token including token_version for instant invalidation"""
        token = super().get_token(user)
        
        # Add custom claims
        token['email'] = user.email
        token['name'] = user.get_full_name()
        token['user_id'] = user.id
        
        # Safely get token_version (handle missing column)
        try:
            token['token_version'] = getattr(user, 'token_version', 0)
        except Exception:
            token['token_version'] = 0
        
        return token


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Custom token refresh serializer with token_version validation.
    Prevents use of tokens that were invalidated via "logout all devices".
    """
    def validate(self, attrs):
        from .session_utils import validate_token_version
        
        # First validate the refresh token normally
        refresh = self.token_class(attrs["refresh"])
        
        # Get user and validate token version
        try:
            user_id = refresh.payload.get('user_id')
            User = get_user_model()
            user = User.objects.get(id=user_id)
            
            # Check if token version matches
            if not validate_token_version(user, refresh.payload):
                raise TokenError("Token has been invalidated. Please login again.")
        
        except User.DoesNotExist:
            raise TokenError("User no longer exists")
        
        # Continue with normal validation
        data = super().validate(attrs)
        data['user_id'] = refresh.payload.get('user_id')
        return data

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('id', 'email', 'first_name', 'last_name', 'phone_number', 'is_active', 'is_email_verified', 'login_method')

class CustomerInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('id', 'email', 'first_name', 'last_name', 'phone_number', 'is_active', 'is_email_verified', 'login_method')

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ('id', 'label', 'receiver_name', 'street_address', 'city', 'province', 'vahed', 'phone', 'country', 'postal_code', 'full_address', 'created_at', 'updated_at')
        read_only_fields = ('id', 'full_address', 'created_at', 'updated_at')
        extra_kwargs = {
            'receiver_name': {'required': True},
            'phone': {'required': True},
        } 