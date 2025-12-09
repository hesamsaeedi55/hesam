#!/usr/bin/env python3
import os
import django
from django.core.management.base import BaseCommand
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import Attribute, Category, CategoryAttribute

class Command(BaseCommand):
    help = 'Set up brand attribute for categories'

    def handle(self, *args, **options):
        # Create or get the brand attribute
        brand_attribute, created = Attribute.objects.get_or_create(
            key='برند',
            defaults={
                'name': 'برند',
                'type': 'select',
                'is_filterable': True,
                'description': 'برند محصول'
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Created brand attribute'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ Brand attribute already exists'))

        # Get all categories
        categories = Category.objects.all()

        # Add brand attribute to categories that don't have it
        added_count = 0
        for category in categories:
            # Check if brand attribute already exists for this category
            existing_attr = CategoryAttribute.objects.filter(
                category=category, 
                key='برند'
            ).exists()

            if not existing_attr:
                # Create CategoryAttribute for this category
                CategoryAttribute.objects.create(
                    category=category,
                    key='برند',
                    type='select',
                    required=False,
                    label_fa='برند'
                )
                added_count += 1

        self.stdout.write(self.style.SUCCESS(f'✅ Added brand attribute to {added_count} categories'))

        # Optionally, update categorization key for categories
        categories.update(categorization_attribute_key='برند')
        self.stdout.write(self.style.SUCCESS(f'✅ Updated categorization key to "برند" for all categories'))
