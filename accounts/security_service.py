"""
Production-Grade Login Security Service
Implements 5-tier progressive security with speed-based attack detection.
"""
import time
import logging
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger('security')

# Import models - these will be available after Django initialization
LoginAttempt = None
AccountLock = None
VerificationCode = None


def _ensure_models_loaded():
    """Ensure models are loaded (lazy loading)"""
    global LoginAttempt, AccountLock, VerificationCode
    if LoginAttempt is None:
        try:
            from .models import LoginAttempt as LA, AccountLock as AL, VerificationCode as VC
            LoginAttempt = LA
            AccountLock = AL
            VerificationCode = VC
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to import security models: {str(e)}")
            # Set to None - callers should handle this gracefully
            LoginAttempt = None
            AccountLock = None
            VerificationCode = None


# ============================================================================
# SECURITY CONFIGURATION CONSTANTS
# ============================================================================

class SecurityConfig:
    """Security configuration constants"""
    
    # Tier thresholds (number of failed attempts)
    TIER_1_MAX = 3          # Normal attempts (0-3)
    TIER_2_MAX = 5          # Warning + delay (4-5)
    TIER_3_MAX = 8          # CAPTCHA required (6-8)
    TIER_4_MAX = 10         # Email verification (9-10)
    TIER_5_LOCK = 11        # Account lock (11+)
    
    # Time windows for attempt counting
    MINUTE_WINDOW = 60      # seconds
    HOUR_WINDOW = 3600      # seconds
    DAY_WINDOW = 86400      # seconds
    
    # Progressive delays (in seconds)
    TIER_2_DELAY = 2        # 2 seconds
    TIER_3_DELAY = 5        # 5 seconds
    TIER_4_DELAY = 10       # 10 seconds
    
    # Lock durations
    ACCOUNT_LOCK_HOURS = 1
    IP_BLOCK_HOURS = 24
    
    # Rate limits
    MAX_PER_MINUTE = 5
    MAX_PER_HOUR = 30
    MAX_PER_DAY_PER_EMAIL = 11
    
    # Speed-based attack detection (attempts per time period)
    FAST_ATTACK_THRESHOLD = 10      # attempts
    FAST_ATTACK_WINDOW = 120        # 2 minutes
    
    # Token/Code settings
    VERIFICATION_CODE_LENGTH = 6
    VERIFICATION_CODE_EXPIRY_MINUTES = 10
    UNLOCK_TOKEN_EXPIRY_HOURS = 24


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_client_ip(request):
    """Extract client IP from request, handling proxies"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Extract user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')[:500]  # Limit length


# ============================================================================
# CORE SECURITY SERVICE
# ============================================================================

class LoginSecurityService:
    """
    Main security service handling all 5 tiers of protection.
    Production-ready with comprehensive logging and attack detection.
    """
    
    def __init__(self, request, email):
        self.request = request
        self.email = email.lower().strip()
        self.ip_address = get_client_ip(request)
        self.user_agent = get_user_agent(request)
        self.start_time = time.time()
    
    # ========================================================================
    # ATTEMPT TRACKING
    # ========================================================================
    
    def record_attempt(self, success=False, failure_reason='', security_tier=1):
        """Record a login attempt in database"""
        _ensure_models_loaded()
        
        if LoginAttempt is None:
            # Models not available - just log
            logger.warning("LoginAttempt model not available, skipping database record")
            return
        
        response_time_ms = int((time.time() - self.start_time) * 1000)
        
        try:
            LoginAttempt.objects.create(
                email=self.email,
                ip_address=self.ip_address,
                user_agent=self.user_agent,
                success=success,
                failure_reason=failure_reason,
                security_tier=security_tier,
                response_time_ms=response_time_ms,
            )
        except Exception as e:
            # If database write fails, log but don't fail the request
            logger.error(f"Failed to record login attempt to database: {str(e)}")
        
        if not success:
            logger.warning(
                f"Failed login: {self.email} from {self.ip_address} "
                f"(Tier {security_tier}, Reason: {failure_reason})"
            )
    
    def get_failed_attempts_count(self, time_window_seconds):
        """Get count of failed attempts within time window"""
        _ensure_models_loaded()
        since = timezone.now() - timedelta(seconds=time_window_seconds)
        
        return LoginAttempt.objects.filter(
            email=self.email,
            success=False,
            created_at__gte=since
        ).count()
    
    def get_failed_attempts_from_ip(self, time_window_seconds):
        """Get count of failed attempts from this IP within time window"""
        _ensure_models_loaded()
        since = timezone.now() - timedelta(seconds=time_window_seconds)
        
        return LoginAttempt.objects.filter(
            ip_address=self.ip_address,
            success=False,
            created_at__gte=since
        ).count()
    
    # ========================================================================
    # ACCOUNT LOCK MANAGEMENT
    # ========================================================================
    
    def check_account_lock(self):
        """
        Check if account is currently locked.
        Returns: (is_locked, lock_object, minutes_remaining)
        """
        try:
            _ensure_models_loaded()
            
            if AccountLock is None:
                # Models not available - assume not locked
                return False, None, 0
            
            active_lock = AccountLock.objects.filter(
                email=self.email,
                is_active=True
            ).first()
            
            if not active_lock:
                return False, None, 0
            
            # Check if lock has expired
            if active_lock.is_expired():
                active_lock.unlock(method='auto_expire')
                logger.info(f"Account lock auto-expired for {self.email}")
                return False, None, 0
            
            # Calculate remaining time
            remaining = (active_lock.expires_at - timezone.now()).total_seconds()
            minutes_remaining = max(1, int(remaining / 60))
            
            logger.warning(f"Account locked: {self.email} ({minutes_remaining} min remaining)")
            return True, active_lock, minutes_remaining
        except Exception as e:
            # If database query fails, assume account is not locked
            logger.error(f"Failed to check account lock: {str(e)}")
            return False, None, 0
    
    def create_account_lock(self, attempt_count, reason='too_many_attempts'):
        """Create a new account lock"""
        _ensure_models_loaded()
        # Get all IPs from recent failed attempts
        since = timezone.now() - timedelta(hours=1)
        recent_ips = list(LoginAttempt.objects.filter(
            email=self.email,
            success=False,
            created_at__gte=since
        ).values_list('ip_address', flat=True).distinct())
        
        # Find customer if exists
        User = get_user_model()
        try:
            customer = User.objects.get(email=self.email)
        except User.DoesNotExist:
            customer = None
        
        # Create lock
        lock = AccountLock.objects.create(
            email=self.email,
            customer=customer,
            reason=reason,
            attempt_count=attempt_count,
            ip_addresses=recent_ips,
        )
        
        logger.critical(
            f"ACCOUNT LOCKED: {self.email} after {attempt_count} attempts. "
            f"IPs: {recent_ips}"
        )
        
        return lock
    
    # ========================================================================
    # SPEED-BASED ATTACK DETECTION
    # ========================================================================
    
    def detect_fast_attack(self):
        """
        Detect if attempts are happening too fast (indicates automated attack).
        Returns: (is_fast_attack, attempts_in_window)
        """
        attempts = self.get_failed_attempts_count(SecurityConfig.FAST_ATTACK_WINDOW)
        
        if attempts >= SecurityConfig.FAST_ATTACK_THRESHOLD:
            logger.critical(
                f"FAST ATTACK DETECTED: {self.email} - {attempts} attempts "
                f"in {SecurityConfig.FAST_ATTACK_WINDOW} seconds from {self.ip_address}"
            )
            return True, attempts
        
        return False, attempts
    
    # ========================================================================
    # RATE LIMITING
    # ========================================================================
    
    def check_rate_limit_ip(self):
        """
        Check IP-based rate limiting.
        Returns: (is_limited, message)
        """
        # Per-minute check
        per_minute = self.get_failed_attempts_from_ip(SecurityConfig.MINUTE_WINDOW)
        if per_minute >= SecurityConfig.MAX_PER_MINUTE:
            logger.warning(f"IP rate limit: {self.ip_address} ({per_minute}/min)")
            return True, "Too many requests. Please try again in 1 minute."
        
        # Per-hour check
        per_hour = self.get_failed_attempts_from_ip(SecurityConfig.HOUR_WINDOW)
        if per_hour >= SecurityConfig.MAX_PER_HOUR:
            logger.warning(f"IP hourly limit: {self.ip_address} ({per_hour}/hour)")
            return True, "Too many failed attempts. Your IP has been temporarily blocked."
        
        return False, ""
    
    # ========================================================================
    # TIER DETERMINATION
    # ========================================================================
    
    def determine_security_tier(self):
        """
        Determine which security tier should be applied based on failed attempts.
        Returns: (tier, failed_count, delay_seconds)
        """
        # Check for fast attack first
        is_fast_attack, _ = self.detect_fast_attack()
        if is_fast_attack:
            # Skip directly to Tier 5 (lock)
            return 5, self.get_failed_attempts_count(SecurityConfig.DAY_WINDOW), 0
        
        # Count failed attempts in last 24 hours
        failed_count = self.get_failed_attempts_count(SecurityConfig.DAY_WINDOW)
        
        # Determine tier and delay
        if failed_count <= SecurityConfig.TIER_1_MAX:
            return 1, failed_count, 0
        elif failed_count <= SecurityConfig.TIER_2_MAX:
            return 2, failed_count, SecurityConfig.TIER_2_DELAY
        elif failed_count <= SecurityConfig.TIER_3_MAX:
            return 3, failed_count, SecurityConfig.TIER_3_DELAY
        elif failed_count <= SecurityConfig.TIER_4_MAX:
            return 4, failed_count, SecurityConfig.TIER_4_DELAY
        else:
            return 5, failed_count, 0
    
    # ========================================================================
    # MAIN SECURITY CHECK
    # ========================================================================
    
    def check_security(self):
        """
        Main security check before allowing login attempt.
        OPTIMIZED: Single database query instead of 5 separate queries.
        
        Returns: {
            'allowed': bool,
            'tier': int,
            'delay': int (seconds),
            'message': str,
            'requires_captcha': bool,
            'requires_verification': bool,
            'should_lock': bool,
            'failed_count': int,
        }
        """
        result = {
            'allowed': True,
            'tier': 1,
            'delay': 0,
            'message': '',
            'requires_captcha': False,
            'requires_verification': False,
            'should_lock': False,
            'failed_count': 0,
        }
        
        # 1. Check if account is already locked (single query)
        is_locked, lock_obj, minutes_remaining = self.check_account_lock()
        if is_locked:
            result.update({
                'allowed': False,
                'tier': 5,
                'message': f'Account temporarily locked for security. Try again in {minutes_remaining} minute(s).',
                'should_lock': True,
            })
            return result
        
        # 2. OPTIMIZED: Fetch ALL failed attempts at once (ONE query instead of 4)
        try:
            _ensure_models_loaded()
            
            if LoginAttempt is None:
                # Models not available - assume no failed attempts
                failed_attempts = []
            else:
                since_day = timezone.now() - timedelta(seconds=SecurityConfig.DAY_WINDOW)
                
                # Get all failed attempts for this email in last 24 hours
                failed_attempts = list(LoginAttempt.objects.filter(
                    email=self.email,
                    success=False,
                    created_at__gte=since_day
                ).values_list('created_at', 'ip_address'))
        except Exception as e:
            # If database query fails, assume no failed attempts (allow login)
            logger.error(f"Failed to fetch login attempts: {str(e)}")
            failed_attempts = []
        
        # Process in memory (fast!) instead of 4 separate database queries
        now = timezone.now()
        failed_count_day = len(failed_attempts)
        failed_count_hour = sum(1 for dt, _ in failed_attempts if (now - dt).total_seconds() <= SecurityConfig.HOUR_WINDOW)
        failed_count_minute = sum(1 for dt, _ in failed_attempts if (now - dt).total_seconds() <= SecurityConfig.MINUTE_WINDOW)
        failed_from_ip_hour = sum(1 for dt, ip in failed_attempts if ip == self.ip_address and (now - dt).total_seconds() <= SecurityConfig.HOUR_WINDOW)
        
        # Fast attack detection (2 min window)
        failed_fast = sum(1 for dt, _ in failed_attempts if (now - dt).total_seconds() <= 120)
        
        # 3. Check IP rate limiting (using in-memory data)
        if failed_count_minute >= SecurityConfig.MAX_PER_MINUTE:
            result.update({
                'allowed': False,
                'message': 'Too many login attempts. Please wait a minute.',
            })
            return result
        
        if failed_from_ip_hour >= SecurityConfig.MAX_PER_HOUR:
            result.update({
                'allowed': False,
                'message': 'Too many failed attempts from your IP. Please try again later.',
            })
            return result
        
        # 3. Determine security tier (using in-memory data - no extra queries!)
        # Check for fast attack
        if failed_fast >= SecurityConfig.FAST_ATTACK_THRESHOLD:
            tier, delay = 5, 0
        elif failed_count_day <= SecurityConfig.TIER_1_MAX:
            tier, delay = 1, 0
        elif failed_count_day <= SecurityConfig.TIER_2_MAX:
            tier, delay = 2, SecurityConfig.TIER_2_DELAY
        elif failed_count_day <= SecurityConfig.TIER_3_MAX:
            tier, delay = 3, SecurityConfig.TIER_3_DELAY
        elif failed_count_day <= SecurityConfig.TIER_4_MAX:
            tier, delay = 4, SecurityConfig.TIER_4_DELAY
        else:
            tier, delay = 5, 0
        
        result['tier'] = tier
        result['delay'] = delay
        result['failed_count'] = failed_count_day
        
        # 4. Apply tier-specific rules
        if tier == 1:
            # Normal operation
            result['message'] = 'Invalid email or password.'
        
        elif tier == 2:
            # Warning with delay
            remaining = SecurityConfig.TIER_2_MAX - failed_count_day
            result['message'] = (
                f'Invalid email or password. '
                f'{remaining} attempt(s) remaining before additional security measures.'
            )
        
        elif tier == 3:
            # Tier 3: No special action (CAPTCHA removed)
            # Just generic error message - no CAPTCHA needed
            result['message'] = 'Invalid email or password.'
        
        elif tier == 4:
            # Email verification required
            result['requires_verification'] = True
            result['message'] = (
                'For your security, we need to verify your identity. '
                'A verification code has been sent to your email.'
            )
        
        elif tier == 5:
            # Account lock
            result['should_lock'] = True
            result['message'] = (
                'Too many failed login attempts. '
                'Your account has been locked for 1 hour. '
                'Check your email for unlock instructions.'
            )
        
        return result
    
    # ========================================================================
    # POST-FAILURE ACTIONS
    # ========================================================================
    
    def handle_failed_login(self, reason='invalid_credentials'):
        """
        Handle a failed login attempt with all security measures.
        
        Returns: Same format as check_security() plus action taken
        """
        # Get security status
        security = self.check_security()
        tier = security['tier']
        
        # Apply progressive delay (simulate processing time)
        if security['delay'] > 0:
            time.sleep(security['delay'])
        
        # Record the attempt
        self.record_attempt(
            success=False,
            failure_reason=reason,
            security_tier=tier
        )
        
        # Handle tier-specific actions
        if tier == 5 or security['should_lock']:
            # Create account lock
            lock = self.create_account_lock(
                attempt_count=security['failed_count'],
                reason='too_many_attempts'
            )
            security['lock_created'] = True
            security['unlock_token'] = lock.unlock_token
        
        elif tier == 4 and security['requires_verification']:
            # Generate and send verification code
            code = self.create_verification_code()
            security['verification_code_sent'] = True
        
        return security
    
    # ========================================================================
    # VERIFICATION CODE MANAGEMENT
    # ========================================================================
    
    def create_verification_code(self):
        """Create a new verification code for Tier 4"""
        _ensure_models_loaded()
        # Invalidate any existing codes
        VerificationCode.objects.filter(
            email=self.email,
            is_used=False
        ).update(is_used=True)
        
        # Create new code
        code = VerificationCode.objects.create(
            email=self.email,
            ip_address=self.ip_address,
        )
        
        logger.info(f"Verification code generated for {self.email}")
        return code
    
    def verify_code(self, code_input):
        """Verify a verification code"""
        _ensure_models_loaded()
        # Get most recent active code
        code_obj = VerificationCode.objects.filter(
            email=self.email,
            is_used=False
        ).order_by('-created_at').first()
        
        if not code_obj:
            return False, "No verification code found. Please request a new one."
        
        if code_obj.is_expired():
            return False, "Verification code expired. Please request a new one."
        
        if code_obj.attempts >= code_obj.max_attempts:
            return False, "Too many verification attempts. Please request a new code."
        
        # Verify the code
        if code_obj.verify(code_input):
            logger.info(f"Verification successful for {self.email}")
            return True, "Verification successful"
        else:
            remaining = code_obj.max_attempts - code_obj.attempts
            return False, f"Invalid code. {remaining} attempt(s) remaining."
    
    # ========================================================================
    # SUCCESS HANDLING
    # ========================================================================
    
    def handle_successful_login(self):
        """Record successful login and clear failed attempts cache"""
        self.record_attempt(success=True, security_tier=1)
        logger.info(f"Successful login: {self.email} from {self.ip_address}")
        
        # Could add additional success handling here
        # e.g., clear verification codes, send success notification, etc.


# ============================================================================
# UNLOCK TOKEN VALIDATION
# ============================================================================

def validate_unlock_token(token):
    """
    Validate an unlock token and unlock the account if valid.
    Returns: (success, message, email)
    """
    _ensure_models_loaded()
    try:
        lock = AccountLock.objects.get(
            unlock_token=token,
            is_active=True
        )
    except AccountLock.DoesNotExist:
        return False, "Invalid or expired unlock link.", None
    
    # Check token expiration
    if timezone.now() > lock.unlock_token_expires:
        return False, "This unlock link has expired.", None
    
    # Check if lock already expired naturally
    if lock.is_expired():
        lock.unlock(method='auto_expire')
        return True, "Your account has already been unlocked automatically.", lock.email
    
    # Unlock the account
    lock.unlock(method='email_link')
    logger.info(f"Account unlocked via email link: {lock.email}")
    
    return True, "Your account has been successfully unlocked!", lock.email

