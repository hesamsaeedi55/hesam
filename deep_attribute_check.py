#!/usr/bin/env python3
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import Product, ProductAttributeValue, Attribute, CategoryAttribute
from django.db import connection

def deep_attribute_check():
    """Do a deep check of all possible ways brand attribute could be stored"""
    
    try:
        # Get product ID 207
        product = Product.objects.get(id=207)
        print(f"Product: {product.name} (ID: {product.id})")
        print(f"Category: {product.category.name} (ID: {product.category.id})")
        
        print(f"\n" + "="*60)
        print("METHOD 1: Check ProductAttributeValue directly")
        print("="*60)
        
        # Check ProductAttributeValue table directly
        attr_values = ProductAttributeValue.objects.filter(product=product)
        print(f"ProductAttributeValue records: {attr_values.count()}")
        
        for attr_value in attr_values:
            print(f"  - ProductAttributeValue: {attr_value.attribute.key} = {attr_value.get_display_value()}")
        
        print(f"\n" + "="*60)
        print("METHOD 2: Check all possible attribute relationships")
        print("="*60)
        
        # Check if product has any attributes through different relationships
        print(f"Product.attribute_values.all(): {product.attribute_values.count()}")
        print(f"Product.attribute_values.filter(): {product.attribute_values.filter().count()}")
        
        # Check if there are any attributes at all in the system
        all_attrs = Attribute.objects.all()
        print(f"Total Attribute objects: {all_attrs.count()}")
        
        for attr in all_attrs:
            print(f"  - Attribute: key='{attr.key}', name='{attr.name}'")
            
            # Check if this product has this attribute
            try:
                product_attr = ProductAttributeValue.objects.get(product=product, attribute=attr)
                print(f"    ✓ Product HAS this attribute: {product_attr.get_display_value()}")
            except ProductAttributeValue.DoesNotExist:
                print(f"    ✗ Product does NOT have this attribute")
        
        print(f"\n" + "="*60)
        print("METHOD 3: Raw SQL check")
        print("="*60)
        
        # Check with raw SQL to see if there are any records
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM shop_productattributevalue 
                WHERE product_id = %s
            """, [product.id])
            count = cursor.fetchone()[0]
            print(f"Raw SQL count: {count}")
            
            if count > 0:
                cursor.execute("""
                    SELECT pav.id, a.key, a.name, pav.custom_value, nav.value
                    FROM shop_productattributevalue pav
                    JOIN shop_attribute a ON pav.attribute_id = a.id
                    LEFT JOIN shop_newattributevalue nav ON pav.attribute_value_id = nav.id
                    WHERE pav.product_id = %s
                """, [product.id])
                
                rows = cursor.fetchall()
                for row in rows:
                    print(f"  - Raw SQL: {row}")
        
        print(f"\n" + "="*60)
        print("METHOD 4: Check if there are other attribute models")
        print("="*60)
        
        # Check if there are other attribute-related models
        from django.apps import apps
        app_models = apps.get_app_config('shop').get_models()
        
        attribute_models = [model for model in app_models if 'attribute' in model.__name__.lower()]
        print(f"Attribute-related models: {[model.__name__ for model in attribute_models]}")
        
        # Check each attribute model for data related to this product
        for model in attribute_models:
            if hasattr(model, 'product') or 'product' in [field.name for field in model._meta.fields]:
                try:
                    # Try to find records related to this product
                    if hasattr(model, 'product'):
                        count = model.objects.filter(product=product).count()
                        print(f"  - {model.__name__}: {count} records")
                    else:
                        # Check if any field contains product_id
                        count = model.objects.count()
                        print(f"  - {model.__name__}: {count} total records")
                except Exception as e:
                    print(f"  - {model.__name__}: Error checking - {e}")
        
        print(f"\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"If you're sure the product has a brand attribute, but I'm not finding it,")
        print(f"then it might be stored in a different way than I'm checking.")
        print(f"Please tell me exactly where you see this brand attribute stored.")
        
    except Product.DoesNotExist:
        print("Product ID 207 not found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    deep_attribute_check()
