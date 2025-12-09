# 🚀 Deployment Guide - Supplier Invitation System

## **Files to Upload to PythonAnywhere**

### **Critical Files (Must Upload):**
1. `suppliers/models.py` ⭐ **MOST IMPORTANT**
2. `suppliers/admin.py` ⭐ **CRITICAL**
3. `suppliers/views.py` ⭐ **CRITICAL**
4. `suppliers/urls.py`
5. `suppliers/forms.py`
6. `suppliers/templates/suppliers/register.html`
7. `suppliers/templates/suppliers/base.html`
8. `suppliers/templates/suppliers/register_success.html`
9. `suppliers/management/commands/create_invitation.py`
10. `suppliers/migrations/0009_remove_old_invitation.py`
11. `myshop/urls.py`
12. `myshop/settings.py`

## **Step-by-Step Deployment**

### **Step 1: Access PythonAnywhere**
1. Go to [www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Log in to your account
3. Go to the **Files** tab

### **Step 2: Navigate to Your Project**
1. Navigate to your Django project directory
2. Usually: `/home/yourusername/yourprojectname/`

### **Step 3: Upload Files**
1. **Upload `suppliers/models.py`** - Replace the existing file
2. **Upload `suppliers/admin.py`** - Replace the existing file
3. **Upload `suppliers/views.py`** - Replace the existing file
4. **Upload `suppliers/forms.py`** - Replace the existing file
5. **Upload `suppliers/urls.py`** - Replace the existing file
6. **Upload `suppliers/migrations/0009_remove_old_invitation.py`** - Add this new file
7. **Upload `suppliers/management/commands/create_invitation.py`** - Add this new file
8. **Upload template files** - Replace the existing templates

### **Step 4: Run Migrations**
1. Go to the **Consoles** tab
2. Open a **Bash console**
3. Navigate to your project directory:
   ```bash
   cd /home/yourusername/yourprojectname/
   ```
4. Activate your virtual environment:
   ```bash
   workon yourprojectname
   ```
5. Run migrations:
   ```bash
   python manage.py migrate
   ```

### **Step 5: Test the System**
1. In the same console, test the new invitation system:
   ```bash
   python manage.py create_invitation test@example.com "Test Store" "Test User" --admin-email your-admin-email@example.com
   ```

### **Step 6: Restart Web App**
1. Go to the **Web** tab
2. Click **"Reload"** button for your web app
3. Wait for the reload to complete

### **Step 7: Test the Registration URL**
1. Copy the registration URL from the test invitation
2. Test it in your browser
3. Should show the registration form (not "Page not found")

## **Troubleshooting**

### **If you get "Page not found":**
1. Check that all files were uploaded correctly
2. Verify the migration ran successfully
3. Check the PythonAnywhere error logs
4. Restart the web app again

### **If emails don't send:**
1. Check your email settings in `settings.py`
2. Verify `DEFAULT_FROM_EMAIL` is set correctly
3. Check PythonAnywhere email logs

### **If migration fails:**
1. Check the migration file exists
2. Verify the model changes are correct
3. Try running `python manage.py makemigrations` first

## **Verification Commands**

### **Check if invitation system works:**
```bash
python manage.py shell -c "from suppliers.models import SupplierInvitation; print('System ready:', SupplierInvitation.objects.count(), 'invitations')"
```

### **Test URL generation:**
```bash
python manage.py shell -c "from django.urls import reverse; print('URL pattern works:', reverse('suppliers:register', kwargs={'token': 'test'}))"
```

### **Test view function:**
```bash
python manage.py shell -c "from suppliers.views import register_with_token; print('View function imported successfully')"
```

## **Important Notes**

- ✅ **Backup your database** before deploying
- ✅ **Test locally first** before uploading
- ✅ **Upload files one by one** to avoid errors
- ✅ **Check file permissions** after upload
- ✅ **Monitor error logs** after deployment

## **Success Indicators**

After successful deployment:
- ✅ Registration URLs work (no "Page not found")
- ✅ Admin panel shows new invitation fields
- ✅ Emails send automatically
- ✅ Invitations can be created via command line
- ✅ Suppliers can register successfully 