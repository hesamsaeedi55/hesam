# How to Use Personal Access Token - Step by Step

## 🔐 Problem: No Place to Enter Token

When you run `git push`, it might not prompt for credentials if they're cached.

---

## ✅ Solution 1: Put Token in URL (Easiest!)

### Step 1: Get Your Token
1. Go to: https://github.com/settings/tokens
2. Create token (if you haven't)
3. Copy the token

### Step 2: Use Token in URL

```bash
cd "/Users/hesamoddinsaeedi/Desktop/best/backup copy 64/myshop2/myshop"

# Remove old remote
git remote remove origin

# Add remote WITH token in URL
git remote add origin https://YOUR_TOKEN@github.com/hesamsaeedi55/myshop-backend.git

# Push (won't ask for password)
git push -u origin IOS
```

**Replace `YOUR_TOKEN` with your actual token!**

---

## ✅ Solution 2: Clear Cached Credentials

```bash
# Clear macOS keychain
git credential-osxkeychain erase
host=github.com
protocol=https
# Press Enter twice

# Then try push again
git push -u origin IOS
# Now it will prompt for username/password
```

---

## ✅ Solution 3: Use SSH (Best Long-term)

### Step 1: Check if you have SSH key
```bash
ls -la ~/.ssh/id_rsa.pub
```

### Step 2: If you have SSH key, use SSH URL:
```bash
git remote remove origin
git remote add origin git@github.com:hesamsaeedi55/myshop-backend.git
git push -u origin IOS
```

### Step 3: If you don't have SSH key, create one:
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Press Enter for all prompts

# Copy public key
cat ~/.ssh/id_ed25519.pub

# Add to GitHub:
# 1. Go to: https://github.com/settings/keys
# 2. Click "New SSH key"
# 3. Paste the key
# 4. Save

# Then use SSH URL (see Step 2)
```

---

## 🎯 Recommended: Solution 1 (Token in URL)

**Easiest and fastest:**

```bash
cd "/Users/hesamoddinsaeedi/Desktop/best/backup copy 64/myshop2/myshop"
git remote remove origin
git remote add origin https://YOUR_TOKEN@github.com/hesamsaeedi55/myshop-backend.git
git push -u origin IOS
```

**Just replace `YOUR_TOKEN` with your actual Personal Access Token!**

---

## ⚠️ Security Note

**After pushing, remove token from URL:**
```bash
git remote set-url origin https://github.com/hesamsaeedi55/myshop-backend.git
```

This prevents token from being saved in git config.

---

## ✅ Quick Steps

1. **Get token:** https://github.com/settings/tokens
2. **Use in URL:** `https://TOKEN@github.com/hesamsaeedi55/myshop-backend.git`
3. **Push:** `git push -u origin IOS`
4. **Remove token from URL** (for security)

**That's it!** 🚀


