#!/usr/bin/env python3
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import Category, Product, ProductImage

def verify_watches():
    try:
        # Get the ساعت مردانه category
        category = Category.objects.get(name='ساعت مردانه')
        print(f"✅ Category found: {category.name}")
        
        # Count products
        products = category.product_set.all()
        print(f"📊 Total products: {products.count()}")
        
        # Show sample products
        print("\n📋 Sample products:")
        for i, product in enumerate(products[:10]):
            print(f"{i+1}. {product.name}")
            print(f"   Price: ${product.price_usd} / {product.price_toman:,} تومان")
            print(f"   SKU: {product.sku}")
            print(f"   Stock: {product.stock_quantity}")
            print(f"   Images: {product.images.count()}")
            print()
        
        # Count total images
        total_images = ProductImage.objects.filter(product__category=category).count()
        print(f"📸 Total product images: {total_images}")
        
        # Show price statistics
        prices = [p.price_toman for p in products]
        if prices:
            print(f"💰 Price range: {min(prices):,} - {max(prices):,} تومان")
            print(f"💰 Average price: {sum(prices)/len(prices):,.0f} تومان")
        
    except Category.DoesNotExist:
        print("❌ Category 'ساعت مردانه' not found")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    verify_watches() 