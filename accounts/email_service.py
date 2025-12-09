"""
Email Service for Security Notifications
Sends warning emails, verification codes, and unlock links.
"""
import logging
import threading
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

logger = logging.getLogger('security')


# ============================================================================
# NON-BLOCKING EMAIL SENDER
# ============================================================================

def send_email_async(msg):
    """
    Send email in background thread to prevent blocking the request.
    If email fails, it doesn't crash the login.
    """
    def _send():
        try:
            msg.send(fail_silently=True)
            logger.info(f"Email sent successfully to {msg.to}")
        except Exception as e:
            logger.error(f"Failed to send email to {msg.to}: {str(e)}")
    
    # Start background thread - returns immediately
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
    logger.info(f"Email queued for {msg.to}")


# ============================================================================
# EMAIL TEMPLATES (HTML)
# ============================================================================

def get_warning_email_html(email, failed_count, remaining_count, ip_address):
    """HTML template for warning email (Tier 3)"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #ff9800; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #ddd; }}
            .alert {{ background: #fff3cd; border-left: 4px solid #ff9800; padding: 15px; margin: 20px 0; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            .details {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ Security Alert</h1>
            </div>
            <div class="content">
                <h2>Multiple Failed Login Attempts Detected</h2>
                <p>Hello,</p>
                <p>We detected <strong>{failed_count} failed login attempts</strong> on your account.</p>
                
                <div class="alert">
                    <strong>⚠️ Warning:</strong> You have <strong>{remaining_count} more attempt(s)</strong> before your account is temporarily locked for security.
                </div>
                
                <div class="details">
                    <p><strong>Details:</strong></p>
                    <ul>
                        <li><strong>Time:</strong> {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
                        <li><strong>IP Address:</strong> {ip_address}</li>
                        <li><strong>Email:</strong> {email}</li>
                    </ul>
                </div>
                
                <h3>What should you do?</h3>
                <p><strong>If this was you:</strong></p>
                <ul>
                    <li>Make sure you're using the correct password</li>
                    <li>Consider resetting your password if you've forgotten it</li>
                </ul>
                
                <p><strong>If this wasn't you:</strong></p>
                <ul>
                    <li>⚠️ Someone may be trying to access your account</li>
                    <li>Reset your password immediately</li>
                    <li>Enable two-factor authentication if available</li>
                </ul>
                
                <p style="text-align: center;">
                    <a href="{settings.SITE_URL}/accounts/password-reset/" class="button">Reset Password Now</a>
                </p>
            </div>
            <div class="footer">
                <p>This is an automated security notification.</p>
                <p>If you have concerns, please contact our support team.</p>
            </div>
        </div>
    </body>
    </html>
    """


def get_verification_code_email_html(email, code, expires_minutes, ip_address):
    """HTML template for verification code email (Tier 4)"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #dc3545; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #ddd; }}
            .code-box {{ background: white; border: 2px dashed #dc3545; padding: 30px; text-align: center; margin: 25px 0; border-radius: 5px; }}
            .code {{ font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #dc3545; font-family: 'Courier New', monospace; }}
            .alert {{ background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            .details {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔒 Verification Required</h1>
            </div>
            <div class="content">
                <h2>Account Verification Code</h2>
                <p>Hello,</p>
                <p>Due to multiple failed login attempts, we need to verify your identity.</p>
                
                <div class="code-box">
                    <p style="margin: 0; font-size: 14px; color: #666;">Your Verification Code:</p>
                    <div class="code">{code}</div>
                    <p style="margin: 10px 0 0 0; font-size: 12px; color: #999;">Valid for {expires_minutes} minutes</p>
                </div>
                
                <div class="alert">
                    <strong>🔐 Security Note:</strong> Enter this code to continue your login. Do not share this code with anyone.
                </div>
                
                <div class="details">
                    <p><strong>Request Details:</strong></p>
                    <ul>
                        <li><strong>Time:</strong> {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
                        <li><strong>IP Address:</strong> {ip_address}</li>
                        <li><strong>Email:</strong> {email}</li>
                    </ul>
                </div>
                
                <h3>Didn't request this code?</h3>
                <p>If you didn't attempt to log in, someone may be trying to access your account. We recommend:</p>
                <ul>
                    <li>Change your password immediately</li>
                    <li>Review your account security settings</li>
                    <li>Contact support if you see suspicious activity</li>
                </ul>
            </div>
            <div class="footer">
                <p>This code will expire in {expires_minutes} minutes.</p>
                <p>This is an automated security notification.</p>
            </div>
        </div>
    </body>
    </html>
    """


def get_account_locked_email_html(email, unlock_url, expires_hours, attempt_count, ip_addresses):
    """HTML template for account lock email (Tier 5)"""
    ip_list = ', '.join(ip_addresses[:5])  # Show first 5 IPs
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #dc3545; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #ddd; }}
            .alert-danger {{ background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
            .button:hover {{ background: #218838; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            .details {{ background: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .warning-box {{ background: #fff3cd; border: 2px solid #ffc107; padding: 20px; border-radius: 5px; margin: 20px 0; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Account Temporarily Locked</h1>
            </div>
            <div class="content">
                <h2>Your Account Has Been Locked</h2>
                <p>Hello,</p>
                <p>Due to <strong>{attempt_count} failed login attempts</strong>, we've temporarily locked your account to protect it from unauthorized access.</p>
                
                <div class="alert-danger">
                    <strong>🔒 Security Lock Active:</strong> Your account is locked for <strong>{expires_hours} hour(s)</strong> for your protection.
                </div>
                
                <div class="details">
                    <p><strong>Lock Details:</strong></p>
                    <ul>
                        <li><strong>Locked At:</strong> {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</li>
                        <li><strong>Failed Attempts:</strong> {attempt_count}</li>
                        <li><strong>IP Address(es):</strong> {ip_list}</li>
                        <li><strong>Auto-Unlock In:</strong> {expires_hours} hour(s)</li>
                    </ul>
                </div>
                
                <h3>How to Unlock Your Account</h3>
                
                <div class="warning-box">
                    <h4 style="margin-top: 0;">Option 1: Unlock Immediately (Recommended)</h4>
                    <p>Click the button below to unlock your account right now:</p>
                    <a href="{unlock_url}" class="button">🔓 Unlock My Account Now</a>
                    <p style="font-size: 12px; color: #666; margin-bottom: 0;">This link is valid for 24 hours</p>
                </div>
                
                <p><strong>Option 2: Wait for Automatic Unlock</strong></p>
                <p>Your account will automatically unlock in {expires_hours} hour(s). No action required.</p>
                
                <h3>Was This You?</h3>
                <p><strong>If you were trying to log in:</strong></p>
                <ul>
                    <li>Use the unlock link above to regain access immediately</li>
                    <li>Make sure you're using the correct password</li>
                    <li>Consider resetting your password if you've forgotten it</li>
                </ul>
                
                <p><strong>If this wasn't you:</strong></p>
                <ul>
                    <li>⚠️ <strong>Someone attempted to access your account</strong></li>
                    <li>Reset your password immediately after unlocking</li>
                    <li>Review your security settings</li>
                    <li>Contact support if you notice any unauthorized activity</li>
                </ul>
                
                <p style="text-align: center; margin-top: 30px;">
                    <a href="{settings.SITE_URL}/accounts/password-reset/" style="color: #007bff; text-decoration: none;">
                        → Reset Password After Unlocking
                    </a>
                </p>
            </div>
            <div class="footer">
                <p><strong>Need Help?</strong> Contact our support team</p>
                <p>This is an automated security notification to protect your account.</p>
                <p style="color: #999; font-size: 11px;">If you didn't request this, please contact support immediately.</p>
            </div>
        </div>
    </body>
    </html>
    """


def get_unlock_success_email_html(email, unlocked_at):
    """HTML template for successful unlock confirmation"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #28a745; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #ddd; }}
            .success-box {{ background: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0; }}
            .button {{ display: inline-block; padding: 12px 30px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Account Unlocked</h1>
            </div>
            <div class="content">
                <h2>Your Account Is Now Accessible</h2>
                <p>Hello,</p>
                
                <div class="success-box">
                    <strong>✅ Success:</strong> Your account has been successfully unlocked!
                </div>
                
                <p>You can now log in to your account normally.</p>
                
                <p><strong>Unlocked At:</strong> {unlocked_at}</p>
                
                <p style="text-align: center;">
                    <a href="{settings.SITE_URL}/accounts/login/" class="button">Log In Now</a>
                </p>
                
                <h3>Security Recommendation</h3>
                <p>For your security, we recommend:</p>
                <ul>
                    <li>Using a strong, unique password</li>
                    <li>Enabling two-factor authentication</li>
                    <li>Being cautious of phishing attempts</li>
                </ul>
            </div>
            <div class="footer">
                <p>If you didn't unlock this account, contact support immediately.</p>
            </div>
        </div>
    </body>
    </html>
    """


# ============================================================================
# EMAIL SENDING FUNCTIONS
# ============================================================================

class SecurityEmailService:
    """Service for sending security-related emails"""
    
    @staticmethod
    def send_warning_email(email, failed_count, remaining_count, ip_address):
        """Send warning email (Tier 3)"""
        try:
            subject = '⚠️ Security Alert: Multiple Failed Login Attempts'
            
            html_content = get_warning_email_html(
                email, failed_count, remaining_count, ip_address
            )
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email]
            )
            msg.attach_alternative(html_content, "text/html")
            send_email_async(msg)  # Non-blocking!
            
            logger.info(f"Warning email queued for {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send warning email to {email}: {str(e)}")
            return False
    
    @staticmethod
    def send_verification_code_email(email, code, expires_minutes, ip_address):
        """Send verification code email (Tier 4)"""
        try:
            subject = '🔒 Your Verification Code'
            
            html_content = get_verification_code_email_html(
                email, code, expires_minutes, ip_address
            )
            text_content = f"""
Your Verification Code: {code}

This code will expire in {expires_minutes} minutes.

Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
IP Address: {ip_address}

If you didn't request this, please secure your account immediately.
            """.strip()
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email]
            )
            msg.attach_alternative(html_content, "text/html")
            send_email_async(msg)  # Non-blocking!
            
            logger.info(f"Verification code queued for {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send verification code to {email}: {str(e)}")
            return False
    
    @staticmethod
    def send_account_locked_email(lock_obj):
        """Send account locked email (Tier 5)"""
        try:
            email = lock_obj.email
            subject = '🔐 Account Temporarily Locked - Action Required'
            
            # Build unlock URL
            unlock_url = f"{settings.SITE_URL}/accounts/unlock/{lock_obj.unlock_token}/"
            
            expires_hours = (lock_obj.expires_at - timezone.now()).total_seconds() / 3600
            expires_hours = max(1, round(expires_hours))
            
            html_content = get_account_locked_email_html(
                email=email,
                unlock_url=unlock_url,
                expires_hours=expires_hours,
                attempt_count=lock_obj.attempt_count,
                ip_addresses=lock_obj.ip_addresses
            )
            
            text_content = f"""
ACCOUNT TEMPORARILY LOCKED

Your account has been locked due to {lock_obj.attempt_count} failed login attempts.

Unlock immediately: {unlock_url}

Or wait {expires_hours} hour(s) for automatic unlock.

Locked at: {lock_obj.locked_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
IPs: {', '.join(lock_obj.ip_addresses[:3])}

If this wasn't you, reset your password immediately.
            """.strip()
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email]
            )
            msg.attach_alternative(html_content, "text/html")
            send_email_async(msg)  # Non-blocking!
            
            # Update lock record
            lock_obj.email_sent = True
            lock_obj.email_sent_at = timezone.now()
            lock_obj.save()
            
            logger.info(f"Account locked email queued for {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send lock email to {lock_obj.email}: {str(e)}")
            return False
    
    @staticmethod
    def send_unlock_success_email(email):
        """Send confirmation email after successful unlock"""
        try:
            subject = '✅ Your Account Has Been Unlocked'
            
            unlocked_at = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
            html_content = get_unlock_success_email_html(email, unlocked_at)
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email]
            )
            msg.attach_alternative(html_content, "text/html")
            send_email_async(msg)  # Non-blocking!

            logger.info(f"Unlock success email queued for {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send unlock success email to {email}: {str(e)}")
            return False

