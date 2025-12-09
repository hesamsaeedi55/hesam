#!/usr/bin/env python3
import os
import django
import random

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import Category, Product, ProductAttribute

def update_movement_type():
    try:
        # Get the ساعت مردانه category
        category = Category.objects.get(name='ساعت مردانه')
        print(f"✅ Found category: {category.name}")
        
        # Get all products in this category
        products = category.product_set.all()
        print(f"📊 Total products: {products.count()}")
        
        # Randomly select 20 products
        selected_products = random.sample(list(products), min(20, products.count()))
        print(f"🎯 Selected {len(selected_products)} products for movement type update")
        
        updated_count = 0
        
        for product in selected_products:
            try:
                # Find the existing movement type attribute
                movement_attr = ProductAttribute.objects.filter(
                    product=product,
                    key='نوع حرکت'
                ).first()
                
                if movement_attr:
                    # Update existing attribute
                    old_value = movement_attr.value
                    movement_attr.value = 'اتوماتیک'
                    movement_attr.save()
                    print(f"✅ Updated {product.name}: {old_value} → اتوماتیک")
                else:
                    # Create new attribute if it doesn't exist
                    ProductAttribute.objects.create(
                        product=product,
                        key='نوع حرکت',
                        value='اتوماتیک'
                    )
                    print(f"✅ Created movement type for {product.name}: اتوماتیک")
                
                updated_count += 1
                
            except Exception as e:
                print(f"❌ Error updating {product.name}: {e}")
                continue
        
        print(f"\n🎉 Successfully updated movement type for {updated_count} products!")
        
        # Show summary
        print(f"\n📋 Updated products:")
        for i, product in enumerate(selected_products[:10], 1):
            movement_attr = ProductAttribute.objects.filter(
                product=product,
                key='نوع حرکت'
            ).first()
            movement_type = movement_attr.value if movement_attr else "Not set"
            print(f"{i}. {product.name} - Movement: {movement_type}")
        
        if len(selected_products) > 10:
            print(f"... and {len(selected_products) - 10} more products")
        
    except Category.DoesNotExist:
        print("❌ Category 'ساعت مردانه' not found")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    update_movement_type() 