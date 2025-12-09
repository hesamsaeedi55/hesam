from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from shop.models import Product, ProductAttribute


class Command(BaseCommand):
    help = (
        "Normalize legacy ProductAttribute.key values for products in a category.\n"
        "Example: rename Persian 'برند' to 'brand' for category 1027.\n"
        "Only affects legacy ProductAttribute rows (not the flexible Attribute model)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--category-id",
            type=int,
            required=True,
            help="Target category ID (e.g., 1027)",
        )
        parser.add_argument(
            "--from-key",
            type=str,
            required=True,
            help="Legacy attribute key to rename (e.g., 'برند')",
        )
        parser.add_argument(
            "--to-key",
            type=str,
            required=True,
            help="New key value (e.g., 'brand')",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database",
        )

    def handle(self, *args, **options):
        category_id = options["category_id"]
        from_key = options["from_key"]
        to_key = options["to_key"]
        dry_run = options["dry_run"]

        # Find legacy ProductAttribute rows for products in this category with the from_key
        qs = ProductAttribute.objects.filter(
            product__category_id=category_id,
            key=from_key,
        )

        count = qs.count()
        self.stdout.write(self.style.NOTICE(
            f"Found {count} legacy ProductAttribute rows in category {category_id} with key='{from_key}'."
        ))

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to update."))
            return

        # Show a small sample
        sample = list(qs.select_related("product").values("product_id", "product__name", "key", "value")[:10])
        if sample:
            self.stdout.write("Sample:")
            for row in sample:
                self.stdout.write(f" - product {row['product_id']} | {row['product__name']} | {row['key']} = {row['value']}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no changes written."))
            return

        with transaction.atomic():
            updated = qs.update(key=to_key)

        self.stdout.write(self.style.SUCCESS(
            f"Updated {updated} rows: '{from_key}' -> '{to_key}' in category {category_id}."
        ))


