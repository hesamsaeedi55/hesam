#!/bin/bash
# Cleanup script for Render deployment

echo "🧹 Cleaning up project for deployment..."

# Remove virtual environments
echo "Removing virtual environments..."
rm -rf venv/ newenv/ myenv/ venv_py311/

# Remove Python cache
echo "Removing __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete

# Remove generated files
echo "Removing generated files..."
rm -rf staticfiles/
rm -f server.log
rm -f db.sqlite3.backup
rm -f cookies.txt

# Remove node_modules (not needed for Django)
echo "Removing node_modules..."
rm -rf node_modules/
rm -f package-lock.json

# Remove test files (keep test_rate_limiting.py as it's useful)
echo "Cleaning test files..."
# Keep test_rate_limiting.py, remove others
rm -f test_*.py
rm -f quick_test.sh

# Remove temporary/debug files
echo "Removing temporary files..."
rm -f debug_*.py
rm -f check_*.py
rm -f diagnose.py
rm -f deploy_fixes.py
rm -f quick_fix.py
rm -f data.json
rm -f db_schema.txt

# Remove Swift files (iOS app files, not needed for backend)
echo "Removing iOS files..."
rm -f *.swift
rm -f OrganizedCategoryViewModel.swift

echo "✅ Cleanup complete!"
echo "📦 Project is now ready for deployment!"


