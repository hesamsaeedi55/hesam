from django.core.management.base import BaseCommand
from django.core.files import File
from django.db import transaction
from pathlib import Path
from decimal import Decimal
import itertools
import random

from shop.models import Product, ProductImage, Category


class Command(BaseCommand):
    help = "Import clothing images from Desktop and create products with multiple images for category 1042."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            dest="directory",
            default=None,
            help="Directory containing clothing images. Defaults to a 'clothes' folder on Desktop.",
        )
        parser.add_argument(
            "--category-id",
            dest="category_id",
            type=int,
            default=1042,
            help="Target category ID.",
        )
        parser.add_argument(
            "--images-per-product",
            dest="images_per_product",
            type=int,
            default=3,
            help="How many images to attach to each product.",
        )
        parser.add_argument(
            "--max-products",
            dest="max_products",
            type=int,
            default=50,
            help="Maximum number of products to create.",
        )

    def handle(self, *args, **options):
        directory = options.get("directory")
        category_id = options.get("category_id")
        images_per_product = max(1, options.get("images_per_product") or 3)
        max_products = options.get("max_products") or 50

        if directory:
            base_dir = Path(directory).expanduser()
        else:
            # Try common Desktop folder names
            candidates = [
                Path("~/Desktop/clothes").expanduser(),
                Path("~/Desktop/Clothes").expanduser(),
                Path("~/Desktop/clothing").expanduser(),
            ]
            base_dir = next((p for p in candidates if p.exists()), None)

        if not base_dir or not base_dir.exists():
            self.stderr.write(self.style.ERROR("No valid images directory found. Use --dir to specify it."))
            return

        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Category with id {category_id} does not exist."))
            return

        # Collect image paths (recurse)
        allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".JPG", ".PNG", ".JPEG", ".WEBP"}
        image_files = [
            p for p in base_dir.rglob("*") if p.is_file() and p.suffix in allowed_exts
        ]

        if not image_files:
            self.stderr.write(self.style.ERROR(f"No images found under {base_dir}."))
            return

        self.stdout.write(self.style.WARNING(f"Found {len(image_files)} images under {base_dir}."))

        # We'll cycle through images so duplicates are fine
        image_cycle = itertools.cycle(image_files)

        created_count = 0
        product_index = 1

        while created_count < max_products:
            with transaction.atomic():
                name = f"Clothes Item {product_index:03d}"
                # Generate a plausible price in Toman
                price_toman = Decimal(str(random.randint(150000, 5000000)))

                product = Product.objects.create(
                    name=name,
                    description="Auto-imported clothing item",
                    price_toman=price_toman,
                    category=category,
                    stock_quantity=random.randint(1, 20),
                    is_active=True,
                )

                # Attach multiple images (allowing duplicates)
                for order_idx in range(images_per_product):
                    img_path = next(image_cycle)
                    try:
                        with img_path.open("rb") as f:
                            django_file = File(f, name=img_path.name)
                            # Create without de-duping by order: vary order to bypass unique(order) constraint
                            ProductImage.objects.create(
                                product=product,
                                image=django_file,
                                is_primary=(order_idx == 0),
                                order=order_idx,
                            )
                    except Exception as e:
                        self.stderr.write(self.style.WARNING(f"Failed to attach image {img_path}: {e}"))

                self.stdout.write(self.style.SUCCESS(f"Created product '{product.name}' with {images_per_product} images."))

                created_count += 1
                product_index += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Created {created_count} products in category {category_id}."))


