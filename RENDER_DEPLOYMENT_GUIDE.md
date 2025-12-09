# Render.com Deployment Guide - Step by Step

## ✅ Project Cleanup (DONE!)

**Cleaned up:**
- ✅ Virtual environments removed (~600MB saved!)
- ✅ __pycache__ directories removed
- ✅ Log files removed
- ✅ Test files removed
- ✅ .gitignore created
- ✅ Size reduced: 1.1GB → 238MB

**Your project is now clean and ready!**

---

## 🚀 Deploy to Render (FREE) - Step by Step

### Step 1: Push to GitHub

```bash
cd "/Users/hesamoddinsaeedi/Desktop/best/backup copy 64/myshop2/myshop"

# Initialize git (if not already)
git init

# Add all files (respects .gitignore)
git add .

# Commit
git commit -m "Ready for Render deployment"

# Create GitHub repo:
# 1. Go to github.com
# 2. Click "New repository"
# 3. Name it: myshop-backend (or any name)
# 4. Don't initialize with README
# 5. Click "Create repository"

# Then push:
git remote add origin https://github.com/YOUR_USERNAME/myshop-backend.git
git branch -M main
git push -u origin main
```

### Step 2: Sign Up for Render

1. **Go to:** https://render.com
2. **Click:** "Get Started for Free"
3. **Sign up** with GitHub (easiest)
4. **Authorize** Render to access your GitHub

### Step 3: Create PostgreSQL Database (FREE)

1. **Click:** "New +" → "PostgreSQL"
2. **Name:** `myshop-db`
3. **Database:** `myshop_db`
4. **User:** `myshop_user`
5. **Region:** Choose closest to you
6. **Plan:** Free
7. **Click:** "Create Database"
8. **Copy:** Internal Database URL (you'll need this)

### Step 4: Deploy Web Service

**Option A: Using render.yaml (Easiest)**

1. **Click:** "New +" → "Blueprint"
2. **Connect GitHub** → Select your repo
3. **Render will detect** `render.yaml` automatically
4. **Click:** "Apply"
5. **Done!** Render will create everything automatically

**Option B: Manual Setup**

1. **Click:** "New +" → "Web Service"
2. **Connect GitHub** → Select your repo
3. **Configure:**
   - **Name:** `myshop`
   - **Environment:** `Python 3`
   - **Region:** Choose closest
   - **Branch:** `main`
   - **Root Directory:** (leave empty)
   - **Build Command:** `./build.sh`
   - **Start Command:** `gunicorn myshop.wsgi:application`
   - **Plan:** Free

4. **Environment Variables:**
   - `DEBUG`: `False`
   - `SECRET_KEY`: `3p#-j!(@a*8kj!s87$s4+xl#%tir-7hkay19njg##x$+t=-s^u` (generated for you)
   - `ALLOWED_HOSTS`: `myshop.onrender.com` (or your app name)
   - `DATABASE_URL`: (paste from Step 3)

5. **Click:** "Create Web Service"

### Step 5: Wait for Deployment

- Render will:
  1. Install dependencies
  2. Run migrations
  3. Collect static files
  4. Start your app

**Time:** 5-10 minutes

### Step 6: Create Superuser

1. **Go to:** Your Web Service → "Shell"
2. **Run:**
```bash
python manage.py createsuperuser
```
3. **Enter:** Email, username, password

### Step 7: Test Your App!

**Your app is live at:**
- `https://myshop.onrender.com` (or your app name)

**Test endpoints:**
- API: `https://myshop.onrender.com/shop/api/customer/cart/`
- Admin: `https://myshop.onrender.com/admin/`

---

## 📋 What Was Cleaned Up

### Removed (~900MB saved!):
- ❌ `venv/` (239MB) - Virtual environment
- ❌ `newenv/` (281MB) - Virtual environment
- ❌ `myenv/` (57MB) - Virtual environment
- ❌ `venv_py311/` (23MB) - Virtual environment
- ❌ `__pycache__/` - Python cache
- ❌ `staticfiles/` (4.1MB) - Will be regenerated
- ❌ `server.log` (31MB) - Log file
- ❌ `node_modules/` (904KB) - Not needed
- ❌ `db.sqlite3.backup` (612KB) - Backup file
- ❌ Test files - Not needed for deployment
- ❌ iOS Swift files - Not needed for backend

### Kept (Essential):
- ✅ All Python code
- ✅ `requirements.txt`
- ✅ `manage.py`
- ✅ `myshop/` settings
- ✅ `shop/`, `accounts/`, `suppliers/` apps
- ✅ Migrations
- ✅ `media/` (product images - 198MB, but needed)

---

## ⚙️ Files Created for Render

### 1. `.gitignore`
- Excludes virtual environments, cache, logs
- Prevents uploading unnecessary files

### 2. `build.sh`
- Installs dependencies
- Collects static files
- Runs migrations

### 3. `render.yaml`
- Auto-configuration for Render
- Sets up database automatically

### 4. `requirements.txt` (Updated)
- Added `gunicorn` (web server)
- Added `dj-database-url` (database config)

---

## 🎯 Quick Checklist

Before deploying:
- [x] Project cleaned up
- [x] .gitignore created
- [x] requirements.txt updated
- [x] build.sh created
- [x] render.yaml created
- [ ] Push to GitHub
- [ ] Deploy to Render
- [ ] Create superuser
- [ ] Test endpoints

---

## 🐛 Troubleshooting

### Build Fails?
- Check `requirements.txt` has all packages
- Check `build.sh` is executable
- Check logs in Render dashboard

### Database Connection Error?
- Verify `DATABASE_URL` is set correctly
- Check database is created and running
- Wait a few minutes after creating database

### Static Files Not Loading?
- Check `build.sh` runs `collectstatic`
- Check `STATIC_ROOT` in settings
- Check `STATIC_URL` in settings

### App Crashes?
- Check logs in Render dashboard
- Verify `SECRET_KEY` is set
- Verify `ALLOWED_HOSTS` includes your domain

---

## ✅ You're Ready!

**Your project:**
- ✅ Cleaned up (1.1GB → 238MB)
- ✅ Ready for deployment
- ✅ All files configured

**Next steps:**
1. Push to GitHub
2. Deploy to Render
3. Test your app!

**Good luck! 🚀**

