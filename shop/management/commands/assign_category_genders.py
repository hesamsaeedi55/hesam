from django.core.management.base import BaseCommand
from django.db import transaction
from shop.models import Category, CategoryGender
import re


class Command(BaseCommand):
    help = 'Assign genders to categories based on their names and patterns'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force assignment even if category already has a gender',
        )
        parser.add_argument(
            '--category-id',
            type=int,
            help='Assign gender to specific category ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        category_id = options['category_id']

        # Get all available genders
        genders = CategoryGender.objects.filter(is_active=True)
        gender_map = {gender.name: gender for gender in genders}

        if not gender_map:
            self.stdout.write(
                self.style.ERROR('No active genders found in CategoryGender table')
            )
            return

        self.stdout.write(f"Available genders: {list(gender_map.keys())}")

        # Define patterns for gender detection
        gender_patterns = {
            'men': [
                r'مردانه',
                r'مرد',
                r'پسرانه',
                r'پسر',
                r'آقایان',
                r'آقا',
            ],
            'women': [
                r'زنانه',
                r'زن',
                r'دخترانه',
                r'دختر',
                r'خانم‌ها',
                r'خانم',
            ],
            'unisex': [
                r'یونیسکس',
                r'یونی',
                r'عمومی',
                r'مشترک',
            ],
            'general': [
                r'عمومی',
                r'کلی',
                r'همه',
            ]
        }

        # Get categories to process
        if category_id:
            categories = Category.objects.filter(id=category_id, is_visible=True)
        else:
            if force:
                categories = Category.objects.filter(is_visible=True)
            else:
                categories = Category.objects.filter(gender__isnull=True, is_visible=True)

        if not categories.exists():
            self.stdout.write(
                self.style.WARNING('No categories found to process')
            )
            return

        self.stdout.write(f"Processing {categories.count()} categories...")

        assigned_count = 0
        skipped_count = 0
        errors = []

        for category in categories:
            try:
                # Skip if already has gender and not forcing
                if category.gender and not force:
                    skipped_count += 1
                    continue

                # Try to detect gender from category name
                detected_gender = None
                category_name = category.name.lower()

                for gender_name, patterns in gender_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, category_name, re.IGNORECASE):
                            detected_gender = gender_name
                            break
                    if detected_gender:
                        break

                # If no gender detected, try to infer from parent category
                if not detected_gender and category.parent and category.parent.gender:
                    detected_gender = category.parent.gender.name
                    self.stdout.write(
                        f"  Inheriting gender '{detected_gender}' from parent '{category.parent.name}' for '{category.name}'"
                    )

                # If still no gender detected, assign to 'general'
                if not detected_gender:
                    detected_gender = 'general'
                    self.stdout.write(
                        f"  No gender pattern detected for '{category.name}', assigning to 'general'"
                    )

                # Get the gender object
                gender_obj = gender_map.get(detected_gender)
                if not gender_obj:
                    errors.append(f"Gender '{detected_gender}' not found for category '{category.name}'")
                    continue

                if dry_run:
                    current_gender = category.gender.name if category.gender else 'None'
                    self.stdout.write(
                        f"  Would assign '{detected_gender}' to '{category.name}' (currently: {current_gender})"
                    )
                else:
                    with transaction.atomic():
                        category.gender = gender_obj
                        category.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Assigned '{detected_gender}' to '{category.name}'"
                            )
                        )

                assigned_count += 1

            except Exception as e:
                error_msg = f"Error processing category '{category.name}': {str(e)}"
                errors.append(error_msg)
                self.stdout.write(self.style.ERROR(f"  {error_msg}"))

        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write("SUMMARY:")
        self.stdout.write(f"  Categories processed: {categories.count()}")
        self.stdout.write(f"  Gender assignments: {assigned_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        
        if errors:
            self.stdout.write(f"  Errors: {len(errors)}")
            for error in errors:
                self.stdout.write(self.style.ERROR(f"    {error}"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nThis was a dry run. No changes were made.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nSuccessfully assigned genders to {assigned_count} categories!")
            ) 