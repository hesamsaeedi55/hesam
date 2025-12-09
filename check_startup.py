#!/usr/bin/env python
"""
Startup check script to validate Django configuration before deployment.
This will catch import errors and missing migrations early.
"""
import sys
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

print("=" * 70)
print("DJANGO STARTUP CHECK")
print("=" * 70)

errors = []
warnings = []

# Check 1: Import security models
print("\n1. Checking security models...")
try:
    from accounts.models import LoginAttempt, AccountLock, VerificationCode, UserSession
    print("   ✅ Security models imported successfully")
except ImportError as e:
    errors.append(f"❌ Cannot import security models: {e}")
    print(f"   ❌ ERROR: {e}")

# Check 2: Import security service
print("\n2. Checking security service...")
try:
    from accounts.security_service import LoginSecurityService, validate_unlock_token
    print("   ✅ Security service imported successfully")
except ImportError as e:
    errors.append(f"❌ Cannot import security service: {e}")
    print(f"   ❌ ERROR: {e}")

# Check 3: Import email service
print("\n3. Checking email service...")
try:
    from accounts.email_service import SecurityEmailService
    print("   ✅ Email service imported successfully")
except ImportError as e:
    errors.append(f"❌ Cannot import email service: {e}")
    print(f"   ❌ ERROR: {e}")

# Check 4: Import serializers
print("\n4. Checking serializers...")
try:
    from accounts.serializers import EmailTokenObtainPairSerializer
    print("   ✅ Serializers imported successfully")
except ImportError as e:
    errors.append(f"❌ Cannot import serializers: {e}")
    print(f"   ❌ ERROR: {e}")

# Check 5: Check if migrations are needed
print("\n5. Checking migrations...")
try:
    from django.core.management import call_command
    from io import StringIO
    
    # Check for unapplied migrations
    out = StringIO()
    try:
        call_command('migrate', '--check', stdout=out, stderr=out)
        print("   ✅ All migrations applied")
    except SystemExit:
        warnings.append("⚠️  Unapplied migrations detected")
        print("   ⚠️  WARNING: Unapplied migrations detected")
        print("   Run: python manage.py migrate")
except Exception as e:
    warnings.append(f"⚠️  Could not check migrations: {e}")
    print(f"   ⚠️  WARNING: {e}")

# Check 6: Test database connection
print("\n6. Testing database connection...")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("   ✅ Database connection successful")
except Exception as e:
    errors.append(f"❌ Database connection failed: {e}")
    print(f"   ❌ ERROR: {e}")

# Check 7: Verify security tables exist
print("\n7. Checking security tables...")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema='public' 
            AND table_name IN ('accounts_loginattempt', 'accounts_accountlock', 'accounts_verificationcode', 'accounts_usersession')
        """)
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]
        expected_tables = ['accounts_loginattempt', 'accounts_accountlock', 'accounts_verificationcode', 'accounts_usersession']
        missing = [t for t in expected_tables if t not in table_names]
        
        if len(tables) == 4:
            print("   ✅ All security tables exist")
        else:
            warnings.append(f"⚠️  Missing tables: {missing}")
            print(f"   ⚠️  WARNING: Missing tables: {missing}")
            print("   Run: python manage.py migrate accounts")
except Exception as e:
    warnings.append(f"⚠️  Could not verify tables: {e}")
    print(f"   ⚠️  WARNING: {e}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if errors:
    print(f"\n❌ ERRORS FOUND ({len(errors)}):")
    for error in errors:
        print(f"  {error}")
    print("\n🚨 Django will NOT start successfully!")
    sys.exit(1)

if warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)}):")
    for warning in warnings:
        print(f"  {warning}")
    print("\n⚠️  Django may start but some features may not work")

if not errors and not warnings:
    print("\n✅ ALL CHECKS PASSED!")
    print("✅ Django is ready to start")

print("\n" + "=" * 70)
sys.exit(0 if not errors else 1)

