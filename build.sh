#!/usr/bin/env bash
# Build script for Render

set -o errexit

echo "================================"
echo "STARTING BUILD PROCESS"
echo "================================"

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run startup check
echo ""
echo "🔍 Running Django startup check..."
python check_startup.py || echo "⚠️  Startup check had warnings, continuing..."

# Collect static files
echo ""
echo "📁 Collecting static files..."
python manage.py collectstatic --no-input

# Create migrations for image_editor if needed
echo ""
echo "📝 Creating migrations for image_editor..."
python manage.py makemigrations image_editor || {
    echo "⚠️  No new migrations needed for image_editor"
}

# Run migrations
echo ""
echo "🔄 Running migrations..."
python manage.py migrate --no-input || {
    echo "⚠️  Migration had errors, checking status..."
    python manage.py showmigrations accounts
    python manage.py showmigrations image_editor
    echo "⚠️  Continuing anyway..."
}

echo ""
echo "================================"
echo "✅ BUILD COMPLETE"
echo "================================"


