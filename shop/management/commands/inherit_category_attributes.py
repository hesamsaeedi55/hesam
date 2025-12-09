from django.core.management.base import BaseCommand
from django.db import transaction
from shop.models import Category, CategoryAttribute, AttributeValue

class Command(BaseCommand):
    help = 'Inherit attributes from parent categories to their child categories'

    def add_arguments(self, parser):
        parser.add_argument('--category', type=int, help='Specific category ID to inherit attributes for')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        specific_category_id = options.get('category')

        # Determine which categories to process
        if specific_category_id:
            categories = Category.objects.filter(id=specific_category_id)
        else:
            categories = Category.objects.filter(parent__isnull=False)

        total_inherited = 0
        total_skipped = 0

        for category in categories:
            # Skip if no parent
            if not category.parent:
                continue

            # Get parent's attributes
            parent_attributes = CategoryAttribute.objects.filter(category=category.parent)

            for parent_attr in parent_attributes:
                # Check if this attribute already exists in the child category
                existing_attr = CategoryAttribute.objects.filter(
                    category=category, 
                    key=parent_attr.key
                ).first()

                if existing_attr:
                    total_skipped += 1
                    self.stdout.write(self.style.WARNING(
                        f"Skipping {parent_attr.key} for {category.name} - already exists"
                    ))
                    continue

                # If not dry run, create the attribute
                if not dry_run:
                    new_attr = CategoryAttribute.objects.create(
                        category=category,
                        key=parent_attr.key,
                        type=parent_attr.type,
                        required=parent_attr.required,
                        display_order=parent_attr.display_order,
                        label_fa=parent_attr.label_fa
                    )

                    # Also copy attribute values
                    parent_values = AttributeValue.objects.filter(attribute=parent_attr)
                    for parent_value in parent_values:
                        AttributeValue.objects.create(
                            attribute=new_attr,
                            value=parent_value.value,
                            display_order=parent_value.display_order
                        )

                total_inherited += 1
                self.stdout.write(self.style.SUCCESS(
                    f"Inherited {parent_attr.key} to {category.name}"
                ))

        # Final summary
        self.stdout.write(self.style.SUCCESS(
            f"Attribute Inheritance Summary: "
            f"{total_inherited} attributes inherited, "
            f"{total_skipped} attributes skipped"
        ))
