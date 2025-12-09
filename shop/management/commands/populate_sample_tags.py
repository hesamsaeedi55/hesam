from django.core.management.base import BaseCommand
from shop.models import Tag, Product, Category
from django.db import transaction


class Command(BaseCommand):
    help = 'Populate sample tags for testing tag-based similar products functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing tags before creating new ones',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing tags...')
            Tag.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Existing tags cleared'))

        # Sample tags for different product types
        sample_tags = {
            'watches': [
                'کلاسیک', 'ورزشی', 'لوکس', 'محدود', 'خاطره‌انگیز', 'مدرن', 'وینتیج',
                'Professional', 'Classic', 'Sport', 'Luxury', 'Heritage', 'Modern', 'Vintage',
                'Limited Edition', 'Special Edition', 'Anniversary', 'Swiss Made', 'Automatic'
            ],
            'books': [
                'راک', 'جاز', 'کلاسیک', 'پاپ', 'مترال', 'الکترونیک', 'فولک', 'بلوز',
                'Rock', 'Jazz', 'Classical', 'Pop', 'Metal', 'Electronic', 'Folk', 'Blues',
                'Persian', 'English', 'Fiction', 'Non-fiction', 'Biography', 'History'
            ],
            'clothing': [
                'کژوال', 'رسمی', 'ورزشی', 'کلاسیک', 'مدرن', 'وینتیج', 'لوکس',
                'Casual', 'Formal', 'Sport', 'Classic', 'Modern', 'Vintage', 'Luxury',
                'Cotton', 'Silk', 'Wool', 'Leather', 'Summer', 'Winter', 'Spring', 'Fall'
            ],
            'general': [
                'جدید', 'پرفروش', 'تخفیف', 'محدود', 'پیشنهاد ویژه', 'محبوب',
                'New', 'Best Seller', 'Sale', 'Limited', 'Special Offer', 'Popular',
                'Made in Iran', 'Handmade', 'Eco-friendly', 'Sustainable'
            ]
        }

        created_tags = []
        
        with transaction.atomic():
            for category_type, tags in sample_tags.items():
                self.stdout.write(f'Creating tags for {category_type}...')
                
                for tag_name in tags:
                    tag, created = Tag.objects.get_or_create(name=tag_name)
                    if created:
                        created_tags.append(tag)
                        self.stdout.write(f'  Created tag: {tag_name}')
                    else:
                        self.stdout.write(f'  Tag already exists: {tag_name}')

        # Assign some tags to existing products
        self.stdout.write('\nAssigning tags to existing products...')
        
        # Get some existing products
        products = Product.objects.filter(is_active=True)[:50]  # Limit to first 50
        
        if products.exists():
            # Get some tags to assign
            tags = Tag.objects.all()[:20]  # Use first 20 tags
            
            if tags.exists():
                for product in products:
                    # Randomly assign 1-3 tags to each product
                    import random
                    num_tags = random.randint(1, min(3, len(tags)))
                    selected_tags = random.sample(list(tags), num_tags)
                    
                    product.tags.add(*selected_tags)
                    self.stdout.write(f'  Assigned {num_tags} tags to {product.name}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Successfully created {len(created_tags)} new tags and assigned tags to products'
            )
        )
        
        # Show statistics
        total_tags = Tag.objects.count()
        products_with_tags = Product.objects.filter(tags__isnull=False).distinct().count()
        total_products = Product.objects.count()
        
        self.stdout.write(f'\n📊 Final Statistics:')
        self.stdout.write(f'  Total Tags: {total_tags}')
        self.stdout.write(f'  Products with Tags: {products_with_tags}')
        self.stdout.write(f'  Total Products: {total_products}')
        if total_products > 0:
            coverage = (products_with_tags / total_products) * 100
            self.stdout.write(f'  Tag Coverage: {coverage:.1f}%')


