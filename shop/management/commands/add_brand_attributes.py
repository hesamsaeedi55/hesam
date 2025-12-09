#!/usr/bin/env python3
import os
import django
from django.core.management.base import BaseCommand
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import Category, Product, CategoryAttribute, ProductAttribute, AttributeValue

class Command(BaseCommand):
    help = 'Add brand attributes to products in the ساعت مردانه category'

    def handle(self, *args, **options):
        # Get the ساعت مردانه category
        try:
            category = Category.objects.get(name='ساعت مردانه')
        except Category.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Category "ساعت مردانه" not found'))
            return

        # Ensure brand CategoryAttribute exists
        brand_category_attr, created = CategoryAttribute.objects.get_or_create(
            category=category,
            key='برند',
            defaults={
                'type': 'select',
                'required': True,
                'label_fa': 'برند'
            }
        )

        # Predefined brand values
        brand_values = [
            'Rolex', 'Omega', 'Cartier', 'Patek Philippe', 
            'Audemars Piguet', 'Tag Heuer', 'Breitling', 
            'IWC', 'Panerai', 'Hublot'
        ]

        # Create AttributeValues for the brand
        for brand in brand_values:
            AttributeValue.objects.get_or_create(
                attribute=brand_category_attr,
                value=brand
            )

        # Get products in this category
        products = Product.objects.filter(category=category, is_active=True)

        # Add brand attributes to products
        added_count = 0
        for product in products:
            # Randomly assign a brand if not already set
            existing_brand = ProductAttribute.objects.filter(
                product=product, 
                key='برند'
            ).first()

            if not existing_brand:
                # Choose a random brand
                brand = brand_values[added_count % len(brand_values)]
                
                # Create ProductAttribute
                ProductAttribute.objects.create(
                    product=product,
                    key='برند',
                    value=brand
                )
                added_count += 1

        # Update category's categorization key
        category.categorization_attribute_key = 'برند'
        category.save()

        self.stdout.write(self.style.SUCCESS(f'✅ Added brand attributes to {added_count} products'))
        self.stdout.write(self.style.SUCCESS(f'✅ Set categorization key to "برند"'))
