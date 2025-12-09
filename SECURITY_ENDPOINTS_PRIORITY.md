# Security Endpoints Priority Guide

## 🔴 CRITICAL PRIORITY (Implement First)

These endpoints are most vulnerable to abuse and MUST have rate limiting:

### Authentication & Account Security
1. **Login** (`/accounts/token/` - EmailTokenObtainPairView)
   - **Risk**: Brute force attacks, credential stuffing
   - **Rate Limit**: 5 requests/minute per IP
   - **Why**: Prevents password guessing attacks

2. **Registration** (`/accounts/register/`)
   - **Risk**: Spam account creation, email bombing
   - **Rate Limit**: 3 requests/hour per IP
   - **Why**: Prevents automated account creation

3. **Password Reset** (`/accounts/password-reset/`)
   - **Risk**: Email spam, account enumeration
   - **Rate Limit**: 3 requests/hour per IP
   - **Why**: Prevents email bombing and user enumeration

4. **Email Verification** (`/accounts/verify-email/<token>/`)
   - **Risk**: Token brute forcing
   - **Rate Limit**: 10 requests/minute per IP
   - **Why**: Prevents token guessing

5. **Token Refresh** (`/accounts/token/refresh/`)
   - **Risk**: Token abuse, session hijacking attempts
   - **Rate Limit**: 20 requests/minute per IP
   - **Why**: Prevents token refresh abuse

### Supplier Authentication
6. **Supplier Login** (`/suppliers/auth/login/`)
   - **Rate Limit**: 5 requests/minute per IP
   
7. **Supplier Registration** (`/suppliers/auth/register/`)
   - **Rate Limit**: 2 requests/hour per IP (more restrictive - suppliers are business accounts)

8. **Supplier Password Reset** (`/suppliers/auth/password-reset/`)
   - **Rate Limit**: 3 requests/hour per IP

---

## 🟠 HIGH PRIORITY (Implement Second)

These endpoints modify user data or financial transactions:

### Order Management
9. **Checkout** (`/shop/api/customer/checkout/`)
   - ✅ **Already Protected**: 30 requests/minute
   - **Status**: DONE

10. **Order Cancellation** (`/shop/api/customer/orders/<id>/cancel/`)
    - **Risk**: Abuse, spam cancellations
    - **Rate Limit**: 10 requests/hour per user
    - **Why**: Prevents order manipulation

11. **Order Return** (`/shop/api/customer/orders/<id>/return/`)
    - **Rate Limit**: 5 requests/hour per user
    - **Why**: Prevents return abuse

### Cart Operations
12. **Cart** (`/shop/api/customer/cart/`)
    - ✅ **Already Protected**: 50 requests/minute
    - **Status**: DONE

### Address Management
13. **Add/Update Address** (`/accounts/customer/addresses/`)
    - **Rate Limit**: 10 requests/hour per user
    - **Why**: Prevents address spam

---

## 🟡 MEDIUM PRIORITY (Implement Third)

These endpoints are less critical but still benefit from rate limiting:

### User Data
14. **Profile Update** (`/accounts/profile/`)
    - **Rate Limit**: 20 requests/hour per user

15. **Wishlist Operations** (`/shop/api/wishlist/`)
    - **Rate Limit**: 30 requests/minute per user
    - **Why**: Prevents spam additions

### Search & Browsing
16. **Product Search** (`/shop/api/products/search/`)
    - **Rate Limit**: 100 requests/minute per IP
    - **Why**: Prevents scraping, reduces server load

17. **Advanced Search** (`/shop/api/products/advanced-search/`)
    - **Rate Limit**: 50 requests/minute per IP
    - **Why**: More complex queries, higher server load

### Order Queries
18. **Order List** (`/shop/api/customer/orders/`)
    - **Rate Limit**: 30 requests/minute per user

19. **Order Detail** (`/shop/api/customer/orders/<id>/`)
    - **Rate Limit**: 30 requests/minute per user

---

## 🟢 LOW PRIORITY (Optional)

These are read-only endpoints with minimal risk:

20. **Product Listing** (`/shop/api/products/`)
    - **Rate Limit**: 200 requests/minute per IP (very lenient)
    - **Why**: Mostly read-only, but prevents scraping

21. **Category Listing** (`/shop/api/category/`)
    - **Rate Limit**: 200 requests/minute per IP

22. **Product Detail** (`/shop/api/product/<id>/detail/`)
    - **Rate Limit**: 100 requests/minute per IP

---

## 📊 Summary

### Current Status
- ✅ **Protected**: Cart (50/min), Checkout (30/min)
- ❌ **Not Protected**: All authentication endpoints, order management, search

### Recommended Implementation Order

**Phase 1 (Critical - Do Now):**
1. Login endpoints (customer + supplier)
2. Registration endpoints
3. Password reset endpoints

**Phase 2 (High Priority - Do Soon):**
4. Order cancellation/return
5. Address management
6. Profile updates

**Phase 3 (Medium Priority - Do Later):**
7. Search endpoints
8. Wishlist operations
9. Order queries

**Phase 4 (Low Priority - Optional):**
10. Read-only product/category endpoints

---

## 🛠️ Implementation Strategy

### Option 1: Per-Endpoint (Current Approach)
- ✅ Precise control per endpoint
- ✅ Different limits for different endpoints
- ❌ More code to maintain
- ❌ Easy to miss endpoints

### Option 2: Middleware (Recommended for Global)
- ✅ Apply to all endpoints automatically
- ✅ Centralized configuration
- ✅ Harder to bypass
- ❌ Less granular control

### Option 3: Hybrid (Best)
- Use middleware for general rate limiting (100 requests/minute per IP)
- Add specific limits for critical endpoints (login, registration, etc.)
- Best of both worlds!

---

## 🎯 Recommendation

**Start with Phase 1 (Critical):**
1. Login (5/min)
2. Registration (3/hour)
3. Password Reset (3/hour)

These 3 endpoints are the most vulnerable and should be protected immediately.

Then move to Phase 2 for order management endpoints.

