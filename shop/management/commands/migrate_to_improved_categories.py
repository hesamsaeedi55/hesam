from django.core.management.base import BaseCommand
from django.db import transaction
from shop.models import Category, CategoryGroup, CategorySubgroup, CategoryGender
import re


class Command(BaseCommand):
    help = 'Migrate from old category structure to new improved structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Create gender options
        genders = [
            {'name': 'men', 'display_name': 'مردانه', 'display_order': 1},
            {'name': 'women', 'display_name': 'زنانه', 'display_order': 2},
            {'name': 'unisex', 'display_name': 'یونیسکس', 'display_order': 3},
            {'name': 'general', 'display_name': 'عمومی', 'display_order': 4},
        ]
        
        with transaction.atomic():
            # Create gender options
            for gender_data in genders:
                gender, created = CategoryGender.objects.get_or_create(
                    name=gender_data['name'],
                    defaults=gender_data
                )
                if created:
                    self.stdout.write(f"Created gender: {gender.display_name}")
                else:
                    self.stdout.write(f"Gender already exists: {gender.display_name}")
            
            # Analyze existing categories to create groups
            existing_categories = Category.objects.filter(parent=None, is_visible=True)
            
            # Extract group names from existing categories
            group_names = set()
            for category in existing_categories:
                clean_name = self.extract_clean_name(category.name)
                if clean_name:
                    group_names.add(clean_name)
            
            self.stdout.write(f"Found {len(group_names)} potential groups: {list(group_names)}")
            
            # Create groups
            groups = {}
            for i, group_name in enumerate(sorted(group_names)):
                if not dry_run:
                    group, created = CategoryGroup.objects.get_or_create(
                        name=group_name,
                        defaults={
                            'label': group_name,
                            'display_order': i + 1,
                            'supports_gender': self.determine_gender_support(group_name)
                        }
                    )
                else:
                    group = {'name': group_name, 'label': group_name}
                    created = True
                
                groups[group_name] = group
                
                if created:
                    self.stdout.write(f"Created group: {group_name}")
                else:
                    self.stdout.write(f"Group already exists: {group_name}")
            
            # Process each main category
            for category in existing_categories:
                clean_name = self.extract_clean_name(category.name)
                if not clean_name:
                    continue
                
                group = groups[clean_name]
                
                # Determine if this is a container category
                is_container = category.get_effective_category_type() == 'container'
                
                if is_container:
                    # Handle container categories (like ساعت, عطر)
                    self.process_container_category(category, group, dry_run)
                else:
                    # Handle direct categories (like کتاب)
                    self.process_direct_category(category, group, dry_run)
            
            if not dry_run:
                self.stdout.write(self.style.SUCCESS('Migration completed successfully!'))
            else:
                self.stdout.write(self.style.SUCCESS('Dry run completed. Review the output above.'))
    
    def extract_clean_name(self, category_name):
        """Extract clean category name without gender suffix"""
        # Remove gender suffixes
        clean_name = re.sub(r'\s+(مردانه|زنانه|یونیسکس)$', '', category_name)
        return clean_name.strip()
    
    def determine_gender_support(self, group_name):
        """Determine if a group supports gender variants"""
        # Groups that typically support gender
        gender_supporting_groups = {
            'ساعت', 'عطر', 'لباس', 'کفش', 'پوشاک', 'اکسسوری', 'زیبایی'
        }
        return group_name in gender_supporting_groups
    
    def process_container_category(self, category, group, dry_run):
        """Process container categories that have subcategories"""
        self.stdout.write(f"Processing container category: {category.name}")
        
        # Get subcategories
        subcategories = category.subcategories.filter(is_visible=True)
        
        for subcategory in subcategories:
            # Extract subgroup name and gender
            subgroup_name = self.extract_clean_name(subcategory.name)
            gender_name = self.extract_gender_from_name(subcategory.name)
            
            if not dry_run:
                # Create or get subgroup
                subgroup, created = CategorySubgroup.objects.get_or_create(
                    group=group,
                    name=subgroup_name,
                    defaults={'label': subgroup_name}
                )
                
                if created:
                    self.stdout.write(f"  Created subgroup: {subgroup_name}")
                
                # Get gender object
                gender = None
                if gender_name:
                    gender = CategoryGender.objects.filter(display_name=gender_name).first()
                
                # Update subcategory with new fields
                subcategory.group = group
                subcategory.subgroup = subgroup
                subcategory.gender = gender
                subcategory.save()
                
                self.stdout.write(f"  Updated subcategory: {subcategory.name}")
            else:
                self.stdout.write(f"  Would create subgroup: {subgroup_name}")
                self.stdout.write(f"  Would update subcategory: {subcategory.name} with gender: {gender_name}")
    
    def process_direct_category(self, category, group, dry_run):
        """Process direct categories that have products directly"""
        self.stdout.write(f"Processing direct category: {category.name}")
        
        # For direct categories, create a general subgroup
        if not dry_run:
            subgroup, created = CategorySubgroup.objects.get_or_create(
                group=group,
                name='عمومی',
                defaults={'label': 'عمومی'}
            )
            
            if created:
                self.stdout.write(f"  Created general subgroup for direct category")
            
            # Update category
            category.group = group
            category.subgroup = subgroup
            category.gender = CategoryGender.objects.filter(name='general').first()
            category.save()
            
            self.stdout.write(f"  Updated direct category: {category.name}")
        else:
            self.stdout.write(f"  Would create general subgroup for direct category")
            self.stdout.write(f"  Would update direct category: {category.name}")
    
    def extract_gender_from_name(self, category_name):
        """Extract gender from category name"""
        if 'مردانه' in category_name:
            return 'مردانه'
        elif 'زنانه' in category_name:
            return 'زنانه'
        elif 'یونیسکس' in category_name:
            return 'یونیسکس'
        return None 