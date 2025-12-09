#!/usr/bin/env python3
"""
Script to add products to existing special offers
"""

import os
import sys
import django
from decimal import Decimal

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from django.utils import timezone
from shop.models import SpecialOffer, SpecialOfferProduct, Product

def add_products_to_offers():
    """Add products to existing special offers"""
    
    # Get active products
    products = Product.objects.filter(is_active=True)[:10]
    if not products.exists():
        print("No active products found!")
        return
    
    print(f"Found {products.count()} active products")
    
    # Get existing offers
    offers = SpecialOffer.objects.filter(enabled=True, is_active=True)
    if not offers.exists():
        print("No active offers found!")
        return
    
    print(f"Found {offers.count()} active offers")
    
    # Clear existing product associations
    SpecialOfferProduct.objects.all().delete()
    print("Cleared existing product associations")
    
    # Add products to each offer
    for i, offer in enumerate(offers):
        print(f"\nProcessing offer: {offer.title}")
        
        # Select products for this offer (different products for each offer)
        start_idx = i * 3
        end_idx = start_idx + 3
        offer_products = products[start_idx:end_idx]
        
        if not offer_products.exists():
            print(f"  No products available for offer {i+1}")
            continue
        
        for j, product in enumerate(offer_products):
            # Calculate discount based on offer type
            if offer.offer_type == "flash_sale":
                discount_percentage = 50
                discount_amount = 0
            elif offer.offer_type == "bundle":
                discount_percentage = 0  # No individual discount for bundle
                discount_amount = 0
            elif offer.offer_type == "discount":
                discount_percentage = 30
                discount_amount = 0
            else:
                discount_percentage = 20
                discount_amount = 0
            
            # Create the offer product
            offer_product = SpecialOfferProduct.objects.create(
                offer=offer,
                product=product,
                discount_percentage=discount_percentage,
                discount_amount=discount_amount,
                original_price=product.price_toman,
                display_order=j + 1,
                is_active=True
            )
            
            print(f"  Added product: {product.name} (Discount: {discount_percentage}%)")
    
    print(f"\nTotal offer products created: {SpecialOfferProduct.objects.count()}")
    
    # Verify the results
    print("\n=== Verification ===")
    for offer in offers:
        product_count = offer.products.count()
        print(f"Offer '{offer.title}': {product_count} products")
        
        for offer_product in offer.products.all():
            print(f"  - {offer_product.product.name}: {offer_product.discount_percentage}% off")

if __name__ == "__main__":
    print("=== Adding Products to Special Offers ===")
    add_products_to_offers()
    print("\n=== Complete ===")
