from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid
import secrets
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

class CustomerManager(BaseUserManager):
    _token_version_column_exists = None
    
    def get_queryset(self):
        """Override to exclude token_version if column doesn't exist"""
        from django.db import connection
        from django.db import OperationalError
        
        # Cache the check result (check once per process)
        if CustomerManager._token_version_column_exists is None:
            try:
                with connection.cursor() as cursor:
                    if connection.vendor == 'sqlite':
                        cursor.execute("PRAGMA table_info(accounts_customer)")
                        columns = [row[1] for row in cursor.fetchall()]
                        CustomerManager._token_version_column_exists = 'token_version' in columns
                    elif connection.vendor == 'postgresql':
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name='accounts_customer' 
                            AND column_name='token_version'
                        """)
                        CustomerManager._token_version_column_exists = cursor.fetchone() is not None
                    else:
                        # For other databases, assume it exists (will fail gracefully if not)
                        CustomerManager._token_version_column_exists = True
            except Exception as e:
                # If check fails, assume column doesn't exist to be safe
                import logging
                logger = logging.getLogger('accounts.models')
                logger.warning(f"Could not check token_version column: {e}")
                CustomerManager._token_version_column_exists = False
        
        # Get base queryset
        queryset = super().get_queryset()
        
        # If column doesn't exist, defer it to prevent SELECT errors
        if not CustomerManager._token_version_column_exists:
            try:
                queryset = queryset.defer('token_version')
            except Exception:
                # If defer fails, return queryset as-is (will handle error in __getattribute__)
                pass
        
        return queryset
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        # Generate username from email
        username = email.split('@')[0]
        # Ensure username is unique
        base_username = username
        counter = 1
        while Customer.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        extra_fields['username'] = username
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)

class Customer(AbstractUser):
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=15, blank=True)
    
    # Address fields
    address = models.TextField(blank=True)  # Keep for backward compatibility
    street_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    date_of_birth = models.DateField(null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    password_reset_token = models.UUIDField(null=True, blank=True)
    password_reset_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ========================================================================
    # SESSION MANAGEMENT - Multi-device tracking and instant token invalidation
    # ========================================================================
    # Note: This field may not exist in database until migrations run
    # Code handles missing column gracefully via Manager.get_queryset() and __getattribute__
    token_version = models.IntegerField(
        default=0,
        null=True,  # Allow NULL during migration period
        blank=True,
        db_column='token_version',  # Explicit column name
        help_text='Increment this to invalidate all existing JWT tokens immediately'
    )
    
    # Fix field clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='customer_set',
        related_query_name='customer'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='customer_set',
        related_query_name='customer'
    )
    
    LOGIN_METHOD_CHOICES = [
        ('email', 'Email'),
        ('google', 'Google'),
        ('other', 'Other'),
    ]
    login_method = models.CharField(
        max_length=20,
        choices=LOGIN_METHOD_CHOICES,
        default='email',
        help_text='How the user logged in or registered (email, google, etc.)'
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = CustomerManager()
    
    class Meta:
        verbose_name = _('customer')
        verbose_name_plural = _('customers')
        
    def __str__(self):
        return self.email
    
    def __getattribute__(self, name):
        """Override to handle token_version gracefully when column doesn't exist"""
        if name == 'token_version':
            try:
                # Try to get the value normally
                return super().__getattribute__(name)
            except (AttributeError, Exception):
                # If column doesn't exist or value is None, return 0 (default)
                # Set it as an attribute to avoid repeated lookups
                object.__setattr__(self, name, 0)
                return 0
        return super().__getattribute__(name)
    
    # ========================================================================
    # SESSION MANAGEMENT METHODS
    # ========================================================================
    
    def invalidate_all_tokens(self):
        """
        Invalidate all existing JWT tokens for this user immediately.
        All devices will be forced to re-login.
        """
        from django.db import OperationalError
        
        try:
            self.token_version += 1
            self.save(update_fields=['token_version'])
        except OperationalError:
            # token_version column doesn't exist yet (migrations pending)
            # Just skip token invalidation - migrations will add the field
            pass
        
        # Also deactivate all sessions (if table exists)
        try:
            self.sessions.filter(is_active=True).update(
                is_active=False,
                revoked_at=timezone.now(),
                revoked_reason='tokens_invalidated'
            )
        except OperationalError:
            # UserSession table doesn't exist yet (migrations pending)
            pass
    
    def get_active_sessions(self):
        """Get all active sessions for this user"""
        from django.db import OperationalError
        try:
            return self.sessions.filter(is_active=True).order_by('-last_activity')
        except OperationalError:
            # UserSession table doesn't exist yet (migrations pending)
            return self.sessions.none()  # Return empty queryset
    
    def get_session_count(self):
        """Get count of active sessions"""
        from django.db import OperationalError
        try:
            return self.sessions.filter(is_active=True).count()
        except OperationalError:
            # UserSession table doesn't exist yet (migrations pending)
            return 0
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_full_address(self):
        """Return formatted full address"""
        address_parts = []
        if self.street_address:
            address_parts.append(self.street_address)
        if self.city:
            address_parts.append(self.city)
        if self.state:
            address_parts.append(self.state)
        if self.postal_code:
            address_parts.append(self.postal_code)
        if self.country:
            address_parts.append(self.country)
        return ', '.join(address_parts) if address_parts else self.address
    
    def generate_email_verification_token(self):
        self.email_verification_token = uuid.uuid4()
        self.email_verification_sent_at = timezone.now()
        # Save only the fields we're updating (exclude token_version if column doesn't exist)
        self.save(update_fields=['email_verification_token', 'email_verification_sent_at'])
        return self.email_verification_token

    def save(self, *args, **kwargs):
        from django.db import OperationalError
        
        if not self.username:
            # Generate username from email if not set
            self.username = self.email.split('@')[0]
            # Ensure username is unique
            base_username = self.username
            counter = 1
            while Customer.objects.filter(username=self.username).exists():
                self.username = f"{base_username}{counter}"
                counter += 1
        
        # Check if token_version column exists before trying to save
        from django.db import connection
        has_token_version_column = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='accounts_customer' 
                    AND column_name='token_version'
                """)
                has_token_version_column = cursor.fetchone() is not None
        except Exception:
            # If we can't check, assume it exists and try normal save
            pass
        
        # Only set token_version if column exists
        if has_token_version_column:
            if self.pk is not None and self.token_version is None:
                self.token_version = 0
        elif self.pk is None:
            # For new instances, if column doesn't exist, we need to use raw SQL
            # But that's complex. Instead, let's just try to save and catch the error
            # Then provide a helpful message
            pass
        
        # Try to save normally
        try:
            super().save(*args, **kwargs)
        except OperationalError as e:
            error_str = str(e).lower()
            # If error is about missing token_version column
            if 'token_version' in error_str or ('column' in error_str and ('does not exist' in error_str or 'unknown column' in error_str)):
                import logging
                logger = logging.getLogger('accounts.models')
                logger.warning(f"token_version column doesn't exist: {str(e)}")
                
                # For UPDATE operations, use update_fields (this works)
                if self.pk is not None:
                    update_fields = kwargs.get('update_fields', None)
                    if update_fields:
                        kwargs['update_fields'] = [f for f in update_fields if f != 'token_version']
                    else:
                        field_names = [
                            f.name for f in self._meta.get_fields() 
                            if hasattr(f, 'name') and f.name != 'token_version' and not f.auto_created
                        ]
                        kwargs['update_fields'] = field_names
                    super().save(*args, **kwargs)
                else:
                    # For INSERT, Django will try to insert all fields
                    # Since update_fields doesn't work for INSERT, we need a workaround
                    # Use Django's model_to_dict to get all field values, then use raw SQL
                    try:
                        from django.forms.models import model_to_dict
                        from django.db import connection
                        
                        # Get all field values except token_version and M2M fields
                        # M2M fields need the instance to have an ID first
                        columns = []
                        placeholders = []
                        values = []
                        
                        for field in self._meta.get_fields():
                            # Skip token_version and auto-created fields
                            if not hasattr(field, 'name') or field.name == 'token_version' or field.auto_created:
                                continue
                            
                            # Check if it's a M2M field FIRST (before accessing it)
                            if hasattr(field, 'many_to_many') and field.many_to_many:
                                # M2M fields are handled after INSERT
                                continue
                            
                            # Skip if it doesn't have a column (relations, etc.)
                            if not hasattr(field, 'column'):
                                continue
                            
                            # Skip if it doesn't have get_prep_value (not a concrete field)
                            if not hasattr(field, 'get_prep_value'):
                                continue
                            
                            # Now get the value (safe because we've excluded M2M fields)
                            if hasattr(self, field.name):
                                try:
                                    value = getattr(self, field.name)
                                    # Prepare value for database
                                    prep_value = field.get_prep_value(value)
                                    
                                    # Handle special types that psycopg2 doesn't support directly
                                    if prep_value is not None:
                                        # Convert UUID to string (psycopg2 doesn't support UUID type directly)
                                        try:
                                            import uuid as uuid_module
                                            if isinstance(prep_value, uuid_module.UUID):
                                                prep_value = str(prep_value)
                                            elif isinstance(value, uuid_module.UUID):
                                                prep_value = str(value)
                                        except:
                                            pass
                                        
                                        # Convert other special types that might not be supported
                                        if not isinstance(prep_value, (str, int, float, bool, type(None), bytes)):
                                            # Try to convert to string if it's a special type
                                            try:
                                                # Check if it's a UUID-like object
                                                if hasattr(prep_value, 'hex') or hasattr(prep_value, '__str__'):
                                                    prep_value = str(prep_value)
                                            except:
                                                pass
                                    
                                    # Only include if not None or field allows null
                                    if prep_value is not None or field.null:
                                        columns.append(field.column)
                                        placeholders.append('%s')
                                        values.append(prep_value)
                                except Exception as field_error:
                                    # Skip fields that can't be prepared or accessed
                                    logger.warning(f"Skipping field {field.name}: {str(field_error)}")
                                    pass
                        
                        if not columns:
                            raise ValueError("No fields to insert")
                        
                        table_name = self._meta.db_table
                        sql = f"""
                            INSERT INTO {table_name} ({', '.join(columns)}) 
                            VALUES ({', '.join(placeholders)}) 
                            RETURNING id
                        """
                        
                        with connection.cursor() as cursor:
                            cursor.execute(sql, values)
                            self.pk = cursor.fetchone()[0]
                        
                        # M2M fields (groups, user_permissions) are handled automatically by Django
                        # after the instance has an ID, so we don't need to set them manually
                        # They're empty by default for new users anyway
                        
                        # Don't refresh from database - it will try to load token_version column
                        # Just mark the instance as saved
                        self._state.adding = False
                        self._state.db = connection.alias
                        
                        # Set token_version to None since column doesn't exist
                        # This prevents errors if code tries to access it
                        if hasattr(self, 'token_version'):
                            self.token_version = None
                        
                        logger.info(f"Successfully inserted Customer {self.pk} without token_version column")
                    except Exception as sql_error:
                        logger.error(f"Raw SQL INSERT failed: {str(sql_error)}")
                        import traceback
                        logger.error(traceback.format_exc())
                        raise OperationalError(
                            f"The 'token_version' database column doesn't exist and raw SQL insert failed: {str(sql_error)}. "
                            "Please check Render build logs to see if migrations completed. "
                            "The migration file '0022_customer_token_version_usersession.py' should create this column."
                        )
            else:
                raise e

# --- SIGNAL TO CREATE CUSTOMER ON USER CREATION ---
@receiver(post_save, sender=Customer)
def create_customer_profile(sender, instance, created, **kwargs):
    # This ensures that a Customer object is created for every new user (including social login)
    if created:
        # You can add additional logic here if needed
        pass  # Customer is already the user model, so nothing to do

class Address(models.Model):
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=50, blank=True, help_text='e.g. Home, Work, etc.')
    receiver_name = models.CharField(max_length=100, blank=False, help_text='Name of the person receiving the package')
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100, blank=True)
    vahed = models.CharField(max_length=20, help_text='واحد', default="")
    phone = models.CharField(max_length=20, help_text='Phone number', default="")
    country = models.CharField(max_length=100, default='ایران')
    postal_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def full_address(self):
        parts = [
            self.receiver_name if self.receiver_name else None,
            self.street_address,
            f"واحد {self.vahed}",
            self.city,
            self.province,
            self.country,
            self.postal_code,
            f"تلفن {self.phone}"
        ]
        return ', '.join([str(p) for p in parts if p])

    def __str__(self):
        return f"{self.label or 'Address'}: {self.full_address}"


# ============================================================================
# SECURITY MODELS - Login Protection System
# ============================================================================

class LoginAttempt(models.Model):
    """
    Tracks all login attempts for security monitoring and rate limiting.
    Used for both failed and successful attempts.
    """
    email = models.EmailField(db_index=True, help_text="Email address attempted")
    ip_address = models.GenericIPAddressField(db_index=True, help_text="IP address of the request")
    user_agent = models.TextField(blank=True, help_text="Browser/device user agent")
    success = models.BooleanField(default=False, help_text="Whether login was successful")
    failure_reason = models.CharField(
        max_length=100, 
        blank=True,
        choices=[
            ('invalid_credentials', 'Invalid Credentials'),
            ('account_locked', 'Account Locked'),
            ('rate_limited', 'Rate Limited'),
            ('captcha_required', 'CAPTCHA Required'),
            ('verification_required', 'Verification Required'),
        ],
        help_text="Reason for failure"
    )
    security_tier = models.IntegerField(
        default=1,
        choices=[
            (1, 'Tier 1: Normal'),
            (2, 'Tier 2: Warning'),
            (3, 'Tier 3: CAPTCHA'),
            (4, 'Tier 4: Email Verification'),
            (5, 'Tier 5: Account Lock'),
        ],
        help_text="Security tier triggered"
    )
    response_time_ms = models.IntegerField(null=True, blank=True, help_text="Response time in milliseconds")
    country_code = models.CharField(max_length=2, blank=True, help_text="Country from IP geolocation")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Login Attempt'
        verbose_name_plural = 'Login Attempts'
    
    def __str__(self):
        status = "✓ Success" if self.success else "✗ Failed"
        return f"{status} - {self.email} from {self.ip_address} [{self.created_at}]"


class AccountLock(models.Model):
    """
    Tracks account locks due to suspicious activity.
    Supports both automatic expiration and manual unlock via email.
    """
    email = models.EmailField(db_index=True, help_text="Email of locked account")
    customer = models.ForeignKey(
        'Customer', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='locks',
        help_text="Customer account (if exists)"
    )
    
    # Lock metadata
    locked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True, help_text="When lock auto-expires")
    
    # Unlock tracking
    is_active = models.BooleanField(default=True, db_index=True, help_text="Whether lock is currently active")
    unlocked_at = models.DateTimeField(null=True, blank=True)
    unlocked_by = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('auto_expire', 'Automatic Expiration'),
            ('email_link', 'Email Unlock Link'),
            ('admin', 'Admin Override'),
            ('password_reset', 'Password Reset'),
        ],
        help_text="How the lock was released"
    )
    
    # Security tokens
    unlock_token = models.CharField(
        max_length=64, 
        unique=True, 
        db_index=True,
        help_text="Secure token for unlock link"
    )
    unlock_token_expires = models.DateTimeField(help_text="When unlock token expires")
    
    # Lock reason and context
    reason = models.CharField(
        max_length=100,
        default='too_many_attempts',
        choices=[
            ('too_many_attempts', 'Too Many Failed Attempts'),
            ('suspicious_location', 'Suspicious Location'),
            ('distributed_attack', 'Distributed Attack Detected'),
            ('manual_lock', 'Manual Security Lock'),
        ],
        help_text="Why account was locked"
    )
    attempt_count = models.IntegerField(default=0, help_text="Number of failed attempts that triggered lock")
    ip_addresses = models.JSONField(default=list, help_text="IPs involved in failed attempts")
    
    # Notification tracking
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-locked_at']
        indexes = [
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['unlock_token']),
            models.Index(fields=['is_active', '-locked_at']),
        ]
        verbose_name = 'Account Lock'
        verbose_name_plural = 'Account Locks'
    
    def __str__(self):
        status = "🔒 Active" if self.is_active else "🔓 Released"
        return f"{status} - {self.email} locked at {self.locked_at}"
    
    def save(self, *args, **kwargs):
        # Generate secure unlock token if not exists
        if not self.unlock_token:
            self.unlock_token = secrets.token_urlsafe(48)
        
        # Set expiration times if not set
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        
        if not self.unlock_token_expires:
            # Token valid for 24 hours (longer than lock duration for user convenience)
            self.unlock_token_expires = timezone.now() + timedelta(hours=24)
        
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Check if lock has expired"""
        return timezone.now() > self.expires_at
    
    def unlock(self, method='email_link'):
        """Unlock the account"""
        self.is_active = False
        self.unlocked_at = timezone.now()
        self.unlocked_by = method
        self.save()


class VerificationCode(models.Model):
    """
    Temporary verification codes sent to users at Tier 4 security level.
    Used when multiple failed login attempts are detected.
    """
    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6, help_text="6-digit verification code")
    ip_address = models.GenericIPAddressField(help_text="IP that triggered code generation")
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True, help_text="Code expiration time")
    
    # Usage tracking
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0, help_text="Number of verification attempts")
    
    # Security
    max_attempts = models.IntegerField(default=3, help_text="Maximum verification attempts allowed")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', '-created_at']),
            models.Index(fields=['code', 'email']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Verification Code'
        verbose_name_plural = 'Verification Codes'
    
    def __str__(self):
        status = "✓ Used" if self.is_used else ("⏰ Expired" if self.is_expired() else "⏳ Active")
        return f"{status} - {self.email} - Code: {self.code}"
    
    def save(self, *args, **kwargs):
        # Generate random 6-digit code if not exists
        if not self.code:
            self.code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        
        # Set expiration (10 minutes from creation)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Check if code has expired"""
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if code is still valid for use"""
        return not self.is_used and not self.is_expired() and self.attempts < self.max_attempts
    
    def verify(self, code_input):
        """Verify the code and track attempts"""
        self.attempts += 1
        self.save()
        
        if not self.is_valid():
            return False
        
        if self.code == code_input:
            self.is_used = True
            self.used_at = timezone.now()
            self.save()
            return True
        
        return False


# ============================================================================
# USER SESSION MODEL - Multi-device tracking
# ============================================================================

class UserSession(models.Model):
    """
    Tracks active user sessions across multiple devices.
    Allows users to:
    - See all logged-in devices
    - Revoke access from specific devices
    - Logout from all devices at once
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sessions',
        help_text='User who owns this session'
    )
    
    # Session identification
    session_key = models.CharField(
        max_length=255,
        unique=True,
        help_text='Unique identifier for this session (from JWT jti claim)'
    )
    
    refresh_token_jti = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text='JTI of the refresh token for this session'
    )
    
    # Device information
    device_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='Device name (e.g., "iPhone 14 Pro", "iPad Air")'
    )
    
    device_type = models.CharField(
        max_length=50,
        blank=True,
        help_text='Device type: ios, android, web, etc.'
    )
    
    device_id = models.CharField(
        max_length=255,
        blank=True,
        help_text='Unique device identifier (e.g., identifierForVendor on iOS)'
    )
    
    app_version = models.CharField(
        max_length=50,
        blank=True,
        help_text='App version (e.g., "1.0.5")'
    )
    
    os_version = models.CharField(
        max_length=50,
        blank=True,
        help_text='OS version (e.g., "iOS 17.1")'
    )
    
    # Network information
    ip_address = models.GenericIPAddressField(
        help_text='IP address of the device'
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text='Full user agent string'
    )
    
    location_city = models.CharField(
        max_length=100,
        blank=True,
        help_text='Approximate city (from IP geolocation)'
    )
    
    location_country = models.CharField(
        max_length=100,
        blank=True,
        help_text='Country (from IP geolocation)'
    )
    
    # Session status
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this session is currently active'
    )
    
    is_current = models.BooleanField(
        default=False,
        help_text='Whether this is the current session (for UI display)'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When this session was created (user logged in)'
    )
    
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text='Last time this session was used'
    )
    
    expires_at = models.DateTimeField(
        help_text='When this session expires (refresh token expiration)'
    )
    
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this session was manually revoked'
    )
    
    revoked_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text='Reason for revocation: user_action, password_change, account_deletion, etc.'
    )
    
    class Meta:
        ordering = ['-last_activity']
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['refresh_token_jti']),
            models.Index(fields=['device_id']),
        ]
    
    def __str__(self):
        device = self.device_name or self.device_type or 'Unknown Device'
        return f"{self.user.email} - {device}"
    
    def revoke(self, reason='user_action'):
        """Revoke this session"""
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoked_reason = reason
        self.save(update_fields=['is_active', 'revoked_at', 'revoked_reason'])
    
    def is_expired(self):
        """Check if this session has expired"""
        return timezone.now() > self.expires_at
    
    def get_device_display(self):
        """Get human-readable device name"""
        if self.device_name:
            return self.device_name
        elif self.device_type:
            return self.device_type.capitalize()
        else:
            return 'Unknown Device'
    
    def get_location_display(self):
        """Get human-readable location"""
        parts = []
        if self.location_city:
            parts.append(self.location_city)
        if self.location_country:
            parts.append(self.location_country)
        return ', '.join(parts) if parts else 'Unknown Location'
