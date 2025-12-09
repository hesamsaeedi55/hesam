from django.core.management.base import BaseCommand
from django.utils import timezone
from shop.models import Product, SpecialOfferProduct


class Command(BaseCommand):
    help = 'Update is_in_special_offers status for all products based on current active offers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        self.stdout.write(f"Checking all products for special offer status at {now}")
        
        total_products = 0
        updated_products = 0
        
        for product in Product.objects.all():
            total_products += 1
            
            # Check if product has any active special offers
            has_active_offers = SpecialOfferProduct.objects.filter(
                product=product,
                offer__enabled=True,
                offer__is_active=True,
                offer__valid_from__lte=now,
                offer__valid_until__gte=now
            ).exists()
            
            # Check if update is needed
            if product.is_in_special_offers != has_active_offers:
                if dry_run:
                    self.stdout.write(
                        f"[DRY RUN] Would update {product.name} (ID: {product.id}): "
                        f"{product.is_in_special_offers} -> {has_active_offers}"
                    )
                else:
                    old_status = product.is_in_special_offers
                    product.is_in_special_offers = has_active_offers
                    product.save(update_fields=['is_in_special_offers'])
                    self.stdout.write(
                        f"Updated {product.name} (ID: {product.id}): {old_status} -> {has_active_offers}"
                    )
                
                updated_products += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would update {updated_products} out of {total_products} products"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated {updated_products} out of {total_products} products"
                )
            )
