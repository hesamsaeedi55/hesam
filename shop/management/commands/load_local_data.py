"""
Management command to load local database backup into production database.
This is used when migrating from local SQLite to Render PostgreSQL.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
import os
from pathlib import Path


class Command(BaseCommand):
    help = 'Load local database backup (from SQLite to PostgreSQL migration)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='local_database_backup.json',
            help='Path to the backup JSON file',
        )

    def handle(self, *args, **options):
        backup_file = options['file']
        
        # Try multiple possible locations
        possible_paths = [
            backup_file,  # Current directory
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), backup_file),  # Project root
            os.path.join(Path(__file__).resolve().parent.parent.parent.parent, backup_file),  # Project root (alternative)
        ]
        
        found_file = None
        for path in possible_paths:
            if os.path.exists(path):
                found_file = path
                break
        
        if not found_file:
            self.stdout.write(
                self.style.WARNING(
                    f'Backup file not found. Tried: {", ".join(possible_paths)}\n'
                    'Skipping data load. Database will be empty but migrations will run.'
                )
            )
            return
        
        try:
            self.stdout.write(f'Loading data from {found_file}...')
            call_command('loaddata', found_file, verbosity=1)
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Successfully loaded data from {found_file}!'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'❌ Error loading data: {str(e)}\n'
                    'This might be normal if the database already has data or if there are conflicts.'
                )
            )
