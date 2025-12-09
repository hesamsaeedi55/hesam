import os
import shutil
import random
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from shop.models import Category, Product, ProductImage, CategoryAttribute, AttributeValue, ProductAttribute
from decimal import Decimal
import uuid

class Command(BaseCommand):
    help = 'Add 40 watch products to the ساعت مردانه category using test images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--images-path',
            type=str,
            default='~/Desktop/imagesfortest',
            help='Path to the test images folder'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting to add 40 watches to ساعت مردانه category...'))
        
        # Get the images path
        images_path = os.path.expanduser(options['images_path'])
        if not os.path.exists(images_path):
            self.stdout.write(self.style.ERROR(f'❌ Images path does not exist: {images_path}'))
            return
        
        # Get all image files (excluding AVIF files that cause compression issues)
        image_files = []
        for file in os.listdir(images_path):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                image_files.append(os.path.join(images_path, file))
        
        if not image_files:
            self.stdout.write(self.style.ERROR(f'❌ No image files found in: {images_path}'))
            return
        
        self.stdout.write(f'📸 Found {len(image_files)} image files (excluding AVIF)')
        
        # Get or create the ساعت مردانه category
        mens_watches_category, created = Category.objects.get_or_create(
            name='ساعت مردانه',
            defaults={
                'label': 'ساعت مردانه',
                'category_type': 'direct',
                'is_visible': True,
                'display_section': 'men'
            }
        )
        
        if created:
            self.stdout.write(f'✅ Created new category: {mens_watches_category.name}')
        else:
            self.stdout.write(f'✅ Using existing category: {mens_watches_category.name}')
        
        # Watch brand names
        brands = ['Rolex', 'Omega', 'Cartier', 'Patek Philippe', 'Audemars Piguet', 'Tag Heuer', 'Breitling', 'IWC', 'Panerai', 'Hublot']
        
        # Watch series/collections
        series = ['Submariner', 'Daytona', 'GMT-Master', 'Seamaster', 'Speedmaster', 'Constellation', 'Santos', 'Nautilus', 'Royal Oak', 'Chronograph']
        
        # Watch models
        models = ['Professional', 'Classic', 'Sport', 'Luxury', 'Heritage', 'Modern', 'Vintage', 'Limited Edition', 'Special Edition', 'Anniversary']
        
        # Watch descriptions
        descriptions = [
            'ساعت مچی مردانه با طراحی کلاسیک و کیفیت برتر',
            'ساعت لوکس با حرکات دقیق و بدنه مقاوم',
            'ساعت ورزشی مناسب برای فعالیت‌های روزانه',
            'ساعت رسمی با طراحی مدرن و ظریف',
            'ساعت کالکشن با جزئیات هنری منحصر به فرد',
            'ساعت حرفه‌ای با قابلیت‌های پیشرفته',
            'ساعت هریتیج با طراحی سنتی و اصیل',
            'ساعت مدرن با تکنولوژی روز دنیا',
            'ساعت وینتیج با حس نوستالژیک',
            'ساعت ادیشن محدود با طراحی خاص'
        ]
        
        # Price ranges (in Toman)
        price_ranges = [
            (5000000, 10000000),    # 5-10 million Toman
            (10000000, 20000000),   # 10-20 million Toman
            (20000000, 50000000),   # 20-50 million Toman
            (50000000, 100000000),  # 50-100 million Toman
            (100000000, 200000000), # 100-200 million Toman
        ]
        
        # Create products
        products_created = 0
        for i in range(40):
            try:
                # Generate product data
                brand = random.choice(brands)
                series_name = random.choice(series)
                model_name = random.choice(models)
                product_name = f"{brand} {series_name} {model_name}"
                
                # Generate description
                description = random.choice(descriptions)
                
                # Generate price
                price_range = random.choice(price_ranges)
                price_toman = random.randint(price_range[0], price_range[1])
                price_usd = round(price_toman / 50000, 2)  # Approximate USD conversion
                
                # Generate SKU
                sku = f"WATCH-{brand[:3].upper()}-{random.randint(1000, 9999)}"
                
                # Generate model number
                model_number = f"{brand[:2]}{random.randint(100, 999)}"
                
                # Create product
                product = Product.objects.create(
                    name=product_name,
                    description=description,
                    price_toman=price_toman,
                    price_usd=price_usd,
                    category=mens_watches_category,
                    model=model_number,
                    sku=sku,
                    stock_quantity=random.randint(1, 10),
                    is_active=True,
                    is_new_arrival=random.choice([True, False])
                )
                
                # Add product images (1-3 images per product)
                num_images = random.randint(1, min(3, len(image_files)))
                # Use different images for each product to avoid duplicates
                start_index = (i * num_images) % len(image_files)
                selected_images = []
                for k in range(num_images):
                    image_index = (start_index + k) % len(image_files)
                    selected_images.append(image_files[image_index])
                
                for j, image_path in enumerate(selected_images):
                    try:
                        # Skip AVIF files as they cause compression issues
                        if image_path.lower().endswith('.avif'):
                            continue
                            
                        # Copy image to media directory
                        filename = f"watch_{product.id}_{j}_{uuid.uuid4().hex[:8]}{os.path.splitext(image_path)[1]}"
                        media_path = os.path.join(settings.MEDIA_ROOT, 'product_images', filename)
                        
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(media_path), exist_ok=True)
                        
                        # Copy file
                        shutil.copy2(image_path, media_path)
                        
                        # Create ProductImage record with proper order
                        product_image = ProductImage.objects.create(
                            product=product,
                            image=f'product_images/{filename}',
                            is_primary=(j == 0),  # First image is primary
                            order=j  # Set proper order to avoid unique constraint
                        )
                        
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'⚠️ Could not add image {image_path}: {e}'))
                
                # Add some basic attributes
                attributes_data = [
                    ('برند', brand),
                    ('سری', series_name),
                    ('مدل', model_name),
                    ('جنسیت', 'مردانه'),
                    ('نوع حرکت', random.choice(['اتوماتیک', 'کوارتز'])),
                    ('جنس بدنه', random.choice(['استیل', 'طلای 18 عیار', 'تیتانیوم'])),
                    ('جنس شیشه', random.choice(['سافایر', 'مینرال'])),
                    ('مقاوم در برابر آب', random.choice(['50 متر', '100 متر', '200 متر', '300 متر'])),
                ]
                
                for attr_key, attr_value in attributes_data:
                    ProductAttribute.objects.create(
                        product=product,
                        key=attr_key,
                        value=attr_value
                    )
                
                products_created += 1
                self.stdout.write(f'✅ Created product {products_created}/40: {product_name}')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error creating product {i+1}: {e}'))
                continue
        
        self.stdout.write(self.style.SUCCESS(f'🎉 Successfully created {products_created} watch products!'))
        self.stdout.write(f'📊 Category: {mens_watches_category.name}')
        self.stdout.write(f'📊 Total products in category: {mens_watches_category.product_set.count()}')
        self.stdout.write(f'📊 Images used: {len(image_files)}') 