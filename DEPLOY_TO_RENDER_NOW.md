# Deploy to Render - Step by Step (Your Code is on GitHub!)

## ✅ GitHub Push Successful!

Your code is now on GitHub: `https://github.com/hesamsaeedi55/myshop-backend`

**What was pushed:**
- ✅ 1114 files
- ✅ 31.82 MB
- ✅ All your cleaned-up code
- ✅ build.sh, render.yaml, .gitignore
- ✅ Branch: IOS

---

## 🚀 Now Deploy to Render (FREE)

### Step 1: Sign Up for Render

1. **Go to:** https://render.com
2. **Click:** "Get Started for Free"
3. **Sign up with GitHub** (easiest - one click!)
4. **Authorize** Render to access your GitHub

### Step 2: Create PostgreSQL Database (FREE)

1. **Click:** "New +" → "PostgreSQL"
2. **Name:** `myshop-db`
3. **Database:** `myshop_db`
4. **User:** `myshop_user`
5. **Region:** Choose closest to you
6. **Plan:** **Free**
7. **Click:** "Create Database"
8. **Wait 2-3 minutes** for database to be ready
9. **Copy:** Internal Database URL (you'll need this!)

### Step 3: Deploy Web Service

**Option A: Using Blueprint (Easiest - Recommended!)**

1. **Click:** "New +" → "Blueprint"
2. **Connect GitHub** → Select: `hesamsaeedi55/myshop-backend`
3. **Select Branch:** `IOS` (your branch name)
4. **Render will detect** `render.yaml` automatically
5. **Click:** "Apply"
6. **Done!** Render will create everything automatically

**Option B: Manual Setup**

1. **Click:** "New +" → "Web Service"
2. **Connect GitHub** → Select: `hesamsaeedi55/myshop-backend`
3. **Select Branch:** `IOS`
4. **Configure:**
   - **Name:** `myshop` (or any name)
   - **Environment:** `Python 3`
   - **Region:** Choose closest
   - **Branch:** `IOS` (important!)
   - **Root Directory:** (leave empty)
   - **Build Command:** `./build.sh`
   - **Start Command:** `gunicorn myshop.wsgi:application`
   - **Plan:** **Free**

5. **Environment Variables:**
   - `DEBUG`: `False`
   - `SECRET_KEY`: `3p#-j!(@a*8kj!s87$s4+xl#%tir-7hkay19njg##x$+t=-s^u`
   - `ALLOWED_HOSTS`: `myshop.onrender.com` (or your app name)
   - `DATABASE_URL`: (paste from Step 2)

6. **Click:** "Create Web Service"

### Step 4: Wait for Deployment

- Render will:
  1. Install dependencies (5-10 minutes)
  2. Run migrations
  3. Collect static files
  4. Start your app

**Watch the logs** in Render dashboard to see progress!

### Step 5: Create Superuser

1. **Go to:** Your Web Service → "Shell" tab
2. **Run:**
```bash
python manage.py createsuperuser
```
3. **Enter:** Email, username, password

### Step 6: Test Your App! 🎉

**Your app will be live at:**
- `https://myshop.onrender.com` (or your app name)

**Test endpoints:**
- Admin: `https://myshop.onrender.com/admin/`
- API: `https://myshop.onrender.com/shop/api/customer/cart/`

---

## 🎯 Quick Checklist

- [x] Code pushed to GitHub ✅
- [ ] Sign up for Render
- [ ] Create PostgreSQL database
- [ ] Deploy web service (use Blueprint!)
- [ ] Wait for deployment
- [ ] Create superuser
- [ ] Test your app!

---

## 🐛 Troubleshooting

### Build Fails?
- Check logs in Render dashboard
- Verify `requirements.txt` is correct
- Check `build.sh` is executable

### Database Connection Error?
- Wait 2-3 minutes after creating database
- Verify `DATABASE_URL` is set correctly
- Check database status is "Available"

### App Crashes?
- Check logs in Render dashboard
- Verify `SECRET_KEY` is set
- Verify `ALLOWED_HOSTS` includes your domain

---

## ✅ You're Almost There!

**Next step:** Go to Render.com and deploy!

**Your code is ready on GitHub - now just deploy it!** 🚀


