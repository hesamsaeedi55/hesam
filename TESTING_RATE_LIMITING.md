# Testing Rate Limiting - Step by Step Guide

## Quick Test (Postman/curl)

### Test 1: Invalid Device ID Format
**Should return 400 Bad Request**

```bash
curl -X GET "http://127.0.0.1:8000/shop/api/customer/cart/" \
  -H "X-Device-ID: invalid-not-uuid" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "detail": "Invalid device ID format"
}
```

---

### Test 2: Valid Device ID Format
**Should return 200 OK**

```bash
curl -X GET "http://127.0.0.1:8000/shop/api/customer/cart/" \
  -H "X-Device-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "cart": {
    "id": 1,
    "items": [],
    ...
  }
}
```

---

### Test 3: Rate Limiting (Device ID)
**Make 55 requests rapidly - should block after 50**

```bash
# Run this 55 times quickly (or use a loop)
for i in {1..55}; do
  curl -X GET "http://127.0.0.1:8000/shop/api/customer/cart/" \
    -H "X-Device-ID: 550e8400-e29b-41d4-a716-446655440000" \
    -H "Content-Type: application/json"
  echo "Request $i"
  sleep 0.1
done
```

**Expected:**
- First 50 requests: `200 OK`
- Requests 51-55: `429 Too Many Requests` with message:
```json
{
  "detail": "Too many requests, please try again later."
}
```

---

### Test 4: Rate Limiting (IP Address)
**Make 55 requests with different device IDs (same IP)**

```bash
for i in {1..55}; do
  # Generate random UUID for each request
  UUID=$(uuidgen)
  curl -X GET "http://127.0.0.1:8000/shop/api/customer/cart/" \
    -H "X-Device-ID: $UUID" \
    -H "Content-Type: application/json"
  echo "Request $i with UUID: $UUID"
  sleep 0.1
done
```

**Expected:**
- After ~50 requests from same IP: `429 Too Many Requests`

---

### Test 5: Wait for Reset
**After 60 seconds, rate limit should reset**

1. Make 50 requests (hit the limit)
2. Wait 60 seconds
3. Make 1 more request - should work again

```bash
# Hit the limit
for i in {1..50}; do
  curl -X GET "http://127.0.0.1:8000/shop/api/customer/cart/" \
    -H "X-Device-ID: 550e8400-e29b-41d4-a716-446655440000"
done

# Wait 60 seconds
echo "Waiting 60 seconds for rate limit to reset..."
sleep 60

# Should work again
curl -X GET "http://127.0.0.1:8000/shop/api/customer/cart/" \
  -H "X-Device-ID: 550e8400-e29b-41d4-a716-446655440000"
```

---

## Automated Test Script

Run the Python test script:

```bash
cd myshop2/myshop
python3 test_rate_limiting.py
```

**Requirements:**
- Django server running: `python manage.py runserver`
- `requests` library: `pip install requests`

---

## Postman Testing

### Setup:
1. Create a new request: `GET http://127.0.0.1:8000/shop/api/customer/cart/`
2. Add header: `X-Device-ID` with value: `550e8400-e29b-41d4-a716-446655440000`

### Test Invalid Device ID:
- Change `X-Device-ID` to: `invalid-not-uuid`
- Send request
- Should get `400 Bad Request`

### Test Rate Limiting:
1. Use Postman's "Runner" feature
2. Create a collection with the cart GET request
3. Run it 55 times
4. Check responses - should see `429` after 50 requests

---

## What to Look For:

✅ **Success Indicators:**
- Invalid device IDs return `400 Bad Request`
- Valid device IDs return `200 OK`
- Rate limit blocks requests after threshold
- Rate limit resets after 60 seconds
- Error messages are clear and consistent

❌ **Failure Indicators:**
- Invalid device IDs are accepted
- Rate limiting doesn't trigger
- Rate limit doesn't reset after 60 seconds
- Error messages are unclear

---

## Troubleshooting

**Rate limit not working?**
- Check Django cache is configured (should use Redis or Memcached in production)
- Check server logs for errors
- Verify `check_rate_limit()` is being called

**Cache issues?**
- Django uses in-memory cache by default (fine for testing)
- In production, use Redis: `CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache'}}`

