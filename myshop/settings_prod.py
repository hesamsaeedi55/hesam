from .settings import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Update this with your domain name
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com']

# Use a more secure secret key
SECRET_KEY = 'your-secure-secret-key-here'  # Generate a new one for production

# Database configuration for production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db_name',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Session Configuration for production (inherit from main settings but ensure secure cookies)
SESSION_COOKIE_SECURE = True  # Use HTTPS for session cookies in production
CSRF_COOKIE_SECURE = True  # Use HTTPS for CSRF cookies in production

# Static and media files
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_ROOT = BASE_DIR / 'media'

# Update site URL for production
SITE_URL = 'https://your-domain.com'

# Email configuration for production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-specific-password'
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
SERVER_EMAIL = EMAIL_HOST_USER 