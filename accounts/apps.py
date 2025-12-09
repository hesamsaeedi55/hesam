from django.apps import AppConfig
import os


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Customer Management'
    
    def ready(self):
        """Run migrations automatically on startup (for Render free tier)"""
        # Only run in production (Render), not during tests or management commands
        if os.environ.get('RENDER') or os.environ.get('DATABASE_URL'):
            # Skip if running migrations, tests, or other management commands
            import sys
            if len(sys.argv) > 1 and any(cmd in sys.argv[1] for cmd in ['migrate', 'test', 'makemigrations', 'shell', 'dbshell']):
                return
            
            # Use threading to run migrations after Django is fully ready
            import threading
            def run_migrations():
                import time
                time.sleep(2)  # Wait 2 seconds for Django to fully initialize
                
                try:
                    from django.core.management import call_command
                    from django.db import connection
                    from django.db.utils import OperationalError
                    
                    # Retry database connection (up to 3 times)
                    for attempt in range(3):
                        try:
                            with connection.cursor() as cursor:
                                cursor.execute("SELECT 1")
                            break
                        except OperationalError as e:
                            if attempt == 2:
                                print(f"⚠️  [AccountsConfig] Database not ready after 3 attempts: {e}")
                                return
                            time.sleep(1)
                    
                    # Check if token_version column exists
                    try:
                        with connection.cursor() as cursor:
                            if connection.vendor == 'sqlite':
                                cursor.execute("PRAGMA table_info(accounts_customer)")
                                columns = [row[1] for row in cursor.fetchall()]
                                if 'token_version' in columns:
                                    print("✅ [AccountsConfig] token_version column already exists")
                                    return
                            elif connection.vendor == 'postgresql':
                                cursor.execute("""
                                    SELECT column_name 
                                    FROM information_schema.columns 
                                    WHERE table_name='accounts_customer' 
                                    AND column_name='token_version'
                                """)
                                if cursor.fetchone():
                                    print("✅ [AccountsConfig] token_version column already exists")
                                    return
                    except Exception as e:
                        print(f"⚠️  [AccountsConfig] Could not check column: {e}")
                    
                    # Run migrations
                    print("🔄 [AccountsConfig] Running migrations on startup...")
                    call_command('migrate', verbosity=2, interactive=False)
                    print("✅ [AccountsConfig] Migrations complete")
                except Exception as e:
                    # Log but don't crash
                    import traceback
                    print(f"⚠️  [AccountsConfig] Migration error: {str(e)}")
                    print(f"⚠️  [AccountsConfig] Traceback: {traceback.format_exc()}")
            
            # Run in background thread
            thread = threading.Thread(target=run_migrations, daemon=True)
            thread.start()
