#!/usr/bin/env bash
# Script to create and run migrations for image_editor app
# Can be run on Render shell or locally

set -o errexit

echo "================================"
echo "IMAGE EDITOR MIGRATIONS"
echo "================================"

cd "$(dirname "$0")"

# Create migrations
echo ""
echo "📝 Creating migrations for image_editor..."
python manage.py makemigrations image_editor

# Run migrations
echo ""
echo "🔄 Running migrations..."
python manage.py migrate image_editor --no-input

echo ""
echo "✅ Migrations complete!"
echo ""
echo "To verify, run: python manage.py showmigrations image_editor"

