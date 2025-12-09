#!/usr/bin/env python3
import os
import django
from django.core.management.base import BaseCommand
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import (
    Category, CategoryAttribute, Attribute, 
    NewAttributeValue, ProductAttributeValue, 
    Product, ProductAttribute
)

class Command(BaseCommand):
    help = 'Diagnose and fix brand attributes for categories'

    def handle(self, *args, **options):
        # Get the category
        category = Category.objects.get(id=1027)  # ساعت مردانه
        self.stdout.write(f"Analyzing category: {category.name}")

        # Find the brand CategoryAttribute
        brand_category_attrs = CategoryAttribute.objects.filter(
            category=category, 
            key='برند'
        )
        
        if not brand_category_attrs.exists():
            self.stdout.write(self.style.ERROR('❌ No brand CategoryAttribute found'))
            return

        brand_category_attr = brand_category_attrs.first()
        self.stdout.write(f"Found CategoryAttribute: {brand_category_attr}")

        # Find or create the Attribute
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
            self.stdout.write(self.style.SUCCESS('✅ Created brand Attribute'))

        # Get products in this category
        products = Product.objects.filter(category=category, is_active=True)
        self.stdout.write(f"Total products: {products.count()}")

        # Retrieve existing NewAttributeValues for this attribute
        existing_values = NewAttributeValue.objects.filter(attribute=brand_attribute)
        self.stdout.write(f"Existing predefined values: {existing_values.count()}")

        # If no predefined values, create them from ProductAttribute
        if not existing_values.exists():
            # Get unique brand values from ProductAttribute
            brand_values = set(ProductAttribute.objects.filter(
                product__in=products, 
                key='برند'
            ).values_list('value', flat=True))

            # Create NewAttributeValues
            for brand in brand_values:
                NewAttributeValue.objects.create(
                    attribute=brand_attribute,
                    value=brand
                )
            
            self.stdout.write(self.style.SUCCESS(f'✅ Created {len(brand_values)} brand values'))

        # Ensure ProductAttributeValue entries exist
        created_count = 0
        for product in products:
            # Check if ProductAttributeValue exists
            existing_pav = ProductAttributeValue.objects.filter(
                product=product,
                attribute=brand_attribute
            ).first()

            if not existing_pav:
                # Find the brand from ProductAttribute
                product_brand = ProductAttribute.objects.filter(
                    product=product, 
                    key='برند'
                ).first()

                if product_brand:
                    # Find the corresponding NewAttributeValue
                    brand_value = NewAttributeValue.objects.filter(
                        attribute=brand_attribute,
                        value=product_brand.value
                    ).first()

                    if brand_value:
                        # Create ProductAttributeValue
                        ProductAttributeValue.objects.create(
                            product=product,
                            attribute=brand_attribute,
                            attribute_value=brand_value
                        )
                        created_count += 1

        self.stdout.write(self.style.SUCCESS(f'✅ Created {created_count} ProductAttributeValue entries'))

        # Update category's categorization key
        category.categorization_attribute_key = 'برند'
        category.save()
        self.stdout.write(self.style.SUCCESS('✅ Updated categorization key to "برند"'))
