#!/usr/bin/env python3
"""
Management command to test variant images functionality
Usage: python manage.py test_variant_images [product_id]
"""

from django.core.management.base import BaseCommand
from shop.models import Product, ProductVariant, ProductVariantImage


class Command(BaseCommand):
    help = 'Test variant images functionality'

    def add_arguments(self, parser):
        parser.add_argument('product_id', type=int, nargs='?', help='Product ID to test with')

    def handle(self, *args, **options):
        product_id = options.get('product_id')
        
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
                self.stdout.write(f"Testing with product: {product.name} (ID: {product.id})")
            except Product.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Product with ID {product_id} not found.'))
                return
        else:
            # Find a product with variants
            product = Product.objects.filter(variants__isnull=False).first()
            if not product:
                self.stdout.write(self.style.ERROR('No products with variants found.'))
                return
            self.stdout.write(f"Testing with product: {product.name} (ID: {product.id})")

        # Get variants for this product
        variants = ProductVariant.objects.filter(product=product)
        
        if not variants.exists():
            self.stdout.write(self.style.ERROR(f'No variants found for product {product.name}'))
            return

        self.stdout.write(f"\nFound {variants.count()} variants:")
        
        for variant in variants:
            self.stdout.write(f"\n📦 Variant: {variant.sku}")
            self.stdout.write(f"   Attributes: {variant.attributes}")
            self.stdout.write(f"   Price: {variant.price_toman:,} Toman")
            self.stdout.write(f"   Stock: {variant.stock_quantity}")
            
            # Check variant images
            images = variant.images.all()
            self.stdout.write(f"   Images: {images.count()}")
            
            if images.exists():
                for i, img in enumerate(images, 1):
                    self.stdout.write(f"     {i}. {img.image.name} (Primary: {img.is_primary}, Order: {img.order})")
            else:
                self.stdout.write(f"     No images found for this variant")
                
            # Show admin URLs
            admin_url = f"http://127.0.0.1:8000/admin/shop/productvariant/{variant.id}/change/"
            self.stdout.write(f"   Admin URL: {admin_url}")

        # Show overall admin URLs
        self.stdout.write(f"\n🔗 Admin URLs:")
        self.stdout.write(f"   Product: http://127.0.0.1:8000/admin/shop/product/{product.id}/change/")
        self.stdout.write(f"   All Variants: http://127.0.0.1:8000/admin/shop/productvariant/")
        self.stdout.write(f"   All Variant Images: http://127.0.0.1:8000/admin/shop/productvariantimage/")
        
        self.stdout.write(self.style.SUCCESS('\n✅ Variant images test completed!'))
