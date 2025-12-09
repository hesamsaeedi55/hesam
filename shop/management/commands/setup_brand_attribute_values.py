#!/usr/bin/env python3
import os
import django
from django.core.management.base import BaseCommand
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import Category, CategoryAttribute, AttributeValue

class Command(BaseCommand):
    help = 'Set up brand attribute values for categories'

    def handle(self, *args, **options):
        # Get the ساعت مردانه category
        category = Category.objects.get(id=1027)
        
        # Find the brand CategoryAttribute
        brand_category_attr = CategoryAttribute.objects.filter(
            category=category, 
            key='brand'
        ).first()
        
        if not brand_category_attr:
            self.stdout.write(self.style.ERROR('❌ No brand CategoryAttribute found'))
            return
        
        # Predefined brand values (in Persian)
        brand_values = [
            'رولکس', 'امگا', 'کارتیه', 'لونژین', 'همیلتون', 
            'اُریس', 'تودور', 'تگ هویر', 'فردریک کنستانت', 'سیکو', 
            'پتک فیلیپ', 'وشرون کنستانتین', 'سرتینا', 'تیسو', 
            'اورینت', 'سواچ'
        ]
        
        # Create or update AttributeValues
        created_count = 0
        for brand in brand_values:
            # Try to get existing value or create a new one
            _, created = AttributeValue.objects.get_or_create(
                attribute=brand_category_attr,
                value=brand
            )
            
            if created:
                created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created {created_count} brand values'))
        
        # Update category's categorization key
        category.categorization_attribute_key = 'brand'
        category.save()
        
        self.stdout.write(self.style.SUCCESS('✅ Updated categorization key to "brand"'))
