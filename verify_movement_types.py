#!/usr/bin/env python3
import os
import django
from collections import Counter

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import Category, Product, ProductAttribute

def verify_movement_types():
    try:
        # Get the ساعت مردانه category
        category = Category.objects.get(name='ساعت مردانه')
        print(f"✅ Category: {category.name}")
        
        # Get all products in this category
        products = category.product_set.all()
        print(f"📊 Total products: {products.count()}")
        
        # Get movement type attributes for all products
        movement_attrs = ProductAttribute.objects.filter(
            product__category=category,
            key='نوع حرکت'
        )
        
        print(f"📊 Products with movement type attribute: {movement_attrs.count()}")
        
        # Count movement types
        movement_types = [attr.value for attr in movement_attrs]
        movement_counts = Counter(movement_types)
        
        print(f"\n📋 Movement Type Distribution:")
        for movement_type, count in movement_counts.most_common():
            percentage = (count / len(movement_types)) * 100
            print(f"   {movement_type}: {count} products ({percentage:.1f}%)")
        
        # Show some examples of each type
        print(f"\n📋 Examples by movement type:")
        for movement_type in movement_counts.keys():
            examples = ProductAttribute.objects.filter(
                product__category=category,
                key='نوع حرکت',
                value=movement_type
            )[:5]  # Show first 5 examples
            
            print(f"\n   {movement_type}:")
            for attr in examples:
                print(f"     - {attr.product.name}")
        
        # Find products without movement type
        products_without_movement = []
        for product in products:
            if not ProductAttribute.objects.filter(product=product, key='نوع حرکت').exists():
                products_without_movement.append(product)
        
        if products_without_movement:
            print(f"\n⚠️ Products without movement type ({len(products_without_movement)}):")
            for product in products_without_movement[:5]:
                print(f"   - {product.name}")
            if len(products_without_movement) > 5:
                print(f"   ... and {len(products_without_movement) - 5} more")
        
    except Category.DoesNotExist:
        print("❌ Category 'ساعت مردانه' not found")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    verify_movement_types() 