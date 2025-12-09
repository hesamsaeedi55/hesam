#!/usr/bin/env python
"""
Test email sending directly (not async) to see actual errors
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/hesamoddinsaeedi/Desktop/best/backup copy 64/myshop2/myshop')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import traceback

print("=" * 70)
print("DIRECT EMAIL TEST (Shows Real Errors)")
print("=" * 70)
print()
print(f"✅ Email Backend: {settings.EMAIL_BACKEND}")
print(f"✅ SMTP Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
print(f"✅ TLS: {settings.EMAIL_USE_TLS}")
print(f"✅ From: {settings.EMAIL_HOST_USER}")
print()

recipient = input("Enter recipient email: ").strip()

if not recipient:
    print("❌ No email provided")
    sys.exit(1)

print()
print(f"📧 Sending test email to: {recipient}")
print("⏳ Connecting to Gmail SMTP...")
print()

try:
    # Create email
    subject = '🧪 Direct Email Test from MyShop'
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: #4CAF50; color: white; padding: 20px; text-align: center; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Email System Works!</h1>
            </div>
            <div style="padding: 20px;">
                <p>If you received this email, your security system can send:</p>
                <ul>
                    <li>✅ Verification codes (Tier 4)</li>
                    <li>✅ Account lock/unlock emails (Tier 5)</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = "If you received this, email system works!"
    
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient]
    )
    msg.attach_alternative(html_content, "text/html")
    
    # Send email (NOT in background - will show errors!)
    print("📤 Sending...")
    result = msg.send(fail_silently=False)  # Will raise exception on error
    
    if result == 1:
        print()
        print("=" * 70)
        print("✅ SUCCESS! Email sent!")
        print("=" * 70)
        print()
        print(f"📬 Check inbox: {recipient}")
        print()
        print("If you got this test email, your security emails will work!")
    else:
        print()
        print("❌ FAILED! send() returned 0")
        
except Exception as e:
    print()
    print("=" * 70)
    print("❌ ERROR SENDING EMAIL")
    print("=" * 70)
    print()
    print(f"Error: {str(e)}")
    print()
    print("Full traceback:")
    print("-" * 70)
    traceback.print_exc()
    print()
    print("COMMON FIXES:")
    print("1. Gmail App Password is wrong → Generate new one")
    print("2. 2FA not enabled on Gmail → Enable it first")
    print("3. 'Less secure apps' → Use App Password instead")
    print("4. Wrong Gmail address → Check EMAIL_HOST_USER")
    print()
    print("Generate App Password at:")
    print("https://myaccount.google.com/apppasswords")

print()
print("=" * 70)

