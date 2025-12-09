# Global Rate Limiting Implementation

## ✅ What Was Implemented

A **global rate limiting middleware** that automatically protects ALL API endpoints in your application.

## 🎯 Coverage

### Protected Endpoints

**All endpoints are now protected**, with different limits based on importance:

#### Critical (Very Restrictive)
- **Login** (`/accounts/token/`): 5 requests/minute
- **Registration** (`/accounts/register/`): 3 requests/hour
- **Password Reset** (`/accounts/password-reset/`): 3 requests/hour
- **Email Verification** (`/accounts/verify-email/`): 10 requests/minute
- **Token Refresh** (`/accounts/token/refresh/`): 20 requests/minute
- **Supplier Login**: 5 requests/minute
- **Supplier Registration**: 2 requests/hour

#### High Priority
- **Checkout**: 30 requests/minute (also has view-level protection)
- **Cart**: 50 requests/minute (also has view-level protection)
- **Order Cancellation**: 10 requests/hour
- **Order Return**: 5 requests/hour
- **Order Queries**: 30 requests/minute
- **Address Management**: 10 requests/hour
- **Profile Updates**: 20 requests/hour

#### Medium Priority
- **Wishlist**: 30 requests/minute
- **Advanced Search**: 50 requests/minute
- **Product Search**: 100 requests/minute

#### General API
- **All other API endpoints**: 100 requests/minute

### Excluded (No Rate Limiting)
- Admin panel (`/admin/`)
- Static files (`/static/`)
- Media files (`/media/`)
- Favicon

## 🔒 How It Works

1. **Middleware intercepts all requests** before they reach your views
2. **Checks URL pattern** to determine appropriate rate limit
3. **Tracks requests by IP address** using Django cache
4. **Blocks requests** that exceed limits (returns HTTP 429)
5. **Logs security warnings** for rate limit violations

## 📊 Rate Limit Details

### Rate Limiting Rules
- **IP-based**: Tracks requests per IP address
- **Path-specific**: Different limits for different endpoints
- **Time-windowed**: Resets after the time window expires
- **Cache-backed**: Uses Django cache (fast, no database queries)

### Example Limits
```
Login: 5 requests per 60 seconds
Registration: 3 requests per 3600 seconds (1 hour)
Cart: 50 requests per 60 seconds
General API: 100 requests per 60 seconds
```

## 🛡️ Security Benefits

1. **Prevents Brute Force Attacks**: Login endpoints protected
2. **Prevents Spam Registration**: Registration limited to 3/hour
3. **Prevents Email Bombing**: Password reset limited
4. **Prevents Scraping**: Search endpoints rate limited
5. **Prevents DDoS**: All endpoints have maximum request limits
6. **Prevents Abuse**: Order/cart manipulation limited

## 🔄 Dual Protection

Some endpoints have **two layers** of rate limiting:

1. **Middleware** (IP-based, global)
2. **View-level** (Device ID + IP, specific)

This provides **defense in depth**:
- Middleware catches IP-based attacks
- View-level catches device-specific abuse
- Both work together for maximum security

## 📝 Configuration

Rate limits are configured in `shop/middleware.py`:

```python
RATE_LIMIT_RULES = [
    (r'^/accounts/token/$', 5, 60, 'Login'),
    (r'^/accounts/register/', 3, 3600, 'Registration'),
    # ... more rules
]
```

To adjust limits, edit the `RATE_LIMIT_RULES` list.

## 🧪 Testing

Test rate limiting by making rapid requests:

```bash
# Test login rate limit (5/minute)
for i in {1..10}; do
  curl -X POST "http://127.0.0.1:8000/accounts/token/" \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}'
  echo "Request $i"
done
# Should see 429 after 5 requests
```

## ⚠️ Important Notes

1. **Cache Required**: Uses Django cache - ensure cache is configured
2. **IP-based Only**: Middleware uses IP, view-level uses device ID
3. **Admin Excluded**: Admin panel not rate limited (has own auth)
4. **Static Files Excluded**: Static/media files not rate limited

## 🚀 Next Steps

The middleware is **active immediately**. All endpoints are now protected!

To verify:
1. Start Django server
2. Make rapid requests to any endpoint
3. Should see 429 after limit is reached

## 📈 Monitoring

Rate limit violations are logged to the `security` logger:
```python
logger.warning(f"Rate limit exceeded: {description} - IP: {ip}, Path: {path}")
```

Check logs for security warnings to identify potential attacks.

