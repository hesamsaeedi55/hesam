#!/usr/bin/env python
"""
Test email sending capability
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/hesamoddinsaeedi/Desktop/best/backup copy 64/myshop2/myshop')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("=" * 70)
print("EMAIL CONFIGURATION TEST")
print("=" * 70)
print()
print(f"Email Backend: {settings.EMAIL_BACKEND}")
print(f"Email Host: {settings.EMAIL_HOST}")
print(f"Email Port: {settings.EMAIL_PORT}")
print(f"Email TLS: {settings.EMAIL_USE_TLS}")
print(f"Email User: {settings.EMAIL_HOST_USER}")
print(f"Email Password: {'*' * len(settings.EMAIL_HOST_PASSWORD)}")
print()

# Ask for recipient
recipient = input("Enter email address to send TEST email to: ").strip()

if not recipient:
    print("❌ No email provided")
    sys.exit(1)

print()
print(f"📧 Sending test email to: {recipient}")
print("⏳ Please wait...")
print()

try:
    # Send test email
    result = send_mail(
        subject='🧪 Test Email from MyShop Security System',
        message='This is a test email to verify email sending works.\n\nIf you received this, the email system is working correctly! ✅',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )
    
    if result == 1:
        print("✅ SUCCESS! Test email sent!")
        print(f"✅ Check inbox: {recipient}")
        print()
        print("If you received the email, your security system emails will work:")
        print("  - Tier 4: Verification codes ✅")
        print("  - Tier 5: Account lock/unlock emails ✅")
    else:
        print("❌ FAILED! send_mail returned 0")
        
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    print()
    print("Common issues:")
    print("  1. Gmail app password incorrect")
    print("  2. 'Less secure app access' disabled")
    print("  3. 2FA not enabled on Gmail account")
    print("  4. Wrong SMTP settings")

print()
print("=" * 70)

