from django.core.management.base import BaseCommand
from shop.models import Product, ProductVariant

class Command(BaseCommand):
    help = 'Show and manage product variants'

    def add_arguments(self, parser):
        parser.add_argument('--product-id', type=int, help='Product ID to show variants for')
        parser.add_argument('--list-all', action='store_true', help='List all products with variants')

    def handle(self, *args, **options):
        if options['list_all']:
            self.list_all_products()
        elif options['product_id']:
            self.show_product_variants(options['product_id'])
        else:
            self.show_product_variants(267)  # Default to our t-shirt

    def list_all_products(self):
        """List all products that have variants"""
        self.stdout.write(self.style.SUCCESS('=== Products with Variants ==='))
        
        products_with_variants = Product.objects.filter(variants__isnull=False).distinct()
        
        for product in products_with_variants:
            variants_count = product.variants.count()
            self.stdout.write(f'Product ID: {product.id} - {product.name} ({variants_count} variants)')
            
            # Show variants for this product
            variants = product.variants.all()
            for variant in variants:
                color = variant.attributes.get('color', 'نامشخص')
                size = variant.attributes.get('size', 'نامشخص')
                self.stdout.write(f'  - {variant.sku}: {color} ({size}) - {variant.stock_quantity} in stock')

    def show_product_variants(self, product_id):
        """Show variants for a specific product"""
        try:
            product = Product.objects.get(id=product_id)
            variants = ProductVariant.objects.filter(product=product)
            
            self.stdout.write(self.style.SUCCESS(f'=== Variants for Product: {product.name} ==='))
            self.stdout.write(f'Product ID: {product.id}')
            self.stdout.write(f'Total variants: {variants.count()}')
            self.stdout.write('')
            
            if variants.exists():
                self.stdout.write(self.style.WARNING('Variants:'))
                for variant in variants:
                    color = variant.attributes.get('color', 'نامشخص')
                    size = variant.attributes.get('size', 'نامشخص')
                    status = 'فعال' if variant.is_active else 'غیرفعال'
                    stock_status = f'{variant.stock_quantity} موجود' if variant.stock_quantity > 0 else 'ناموجود'
                    
                    self.stdout.write(f'  SKU: {variant.sku}')
                    self.stdout.write(f'    Color: {color}')
                    self.stdout.write(f'    Size: {size}')
                    self.stdout.write(f'    Price: {variant.price_toman} تومان')
                    self.stdout.write(f'    Stock: {stock_status}')
                    self.stdout.write(f'    Status: {status}')
                    self.stdout.write(f'    Created: {variant.created_at}')
                    self.stdout.write('')
            else:
                self.stdout.write(self.style.ERROR('No variants found for this product.'))
                
        except Product.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Product with ID {product_id} not found.'))

