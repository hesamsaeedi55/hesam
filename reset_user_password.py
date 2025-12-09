#!/usr/bin/env python
"""
Reset a user's password to upgrade to new faster hash
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/hesamoddinsaeedi/Desktop/best/backup copy 64/myshop2/myshop')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

email = input("Enter email to reset: ")
new_password = input("Enter new password: ")

try:
    user = User.objects.get(email=email)
    user.set_password(new_password)
    user.save()
    print(f"✅ Password updated for {email}")
    print(f"✅ Now uses optimized 100k iteration hash (fast!)")
except User.DoesNotExist:
    print(f"❌ User {email} not found")

