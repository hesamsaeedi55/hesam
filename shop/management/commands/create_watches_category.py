from django.core.management.base import BaseCommand
from shop.models import CategoryGender, CategoryGroup, CategorySubgroup, Category


class Command(BaseCommand):
    help = 'Create a men\'s watches category using the new improved category system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating men\'s watches category...'))
        
        # Step 1: Create or get gender
        men_gender, created = CategoryGender.objects.get_or_create(
            name='men',
            defaults={
                'display_name': 'مردانه',
                'display_order': 1,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'Created gender: {men_gender.display_name}')
        else:
            self.stdout.write(f'Using existing gender: {men_gender.display_name}')
        
        # Step 2: Create or get the watches group
        watches_group, created = CategoryGroup.objects.get_or_create(
            name='ساعت',
            defaults={
                'label': 'ساعت',
                'description': 'انواع ساعت‌های مچی و دیواری',
                'icon': 'watch',
                'display_order': 1,
                'supports_gender': True,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'Created group: {watches_group.name}')
        else:
            self.stdout.write(f'Using existing group: {watches_group.name}')
        
        # Step 3: Create or get the watches subgroup
        watches_subgroup, created = CategorySubgroup.objects.get_or_create(
            name='ساعت مچی',
            group=watches_group,
            defaults={
                'label': 'ساعت مچی',
                'display_order': 1,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'Created subgroup: {watches_subgroup.name}')
        else:
            self.stdout.write(f'Using existing subgroup: {watches_subgroup.name}')
        
        # Step 4: Create the men's watches category
        mens_watches_category, created = Category.objects.get_or_create(
            name='ساعت مردانه',
            defaults={
                'label': 'ساعت مردانه',
                'category_type': 'direct',
                'is_visible': True,
                'display_section': 'men',
                'group': watches_group,
                'subgroup': watches_subgroup,
                'gender': men_gender
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created men\'s watches category: {mens_watches_category.name}')
            )
            self.stdout.write(f'  - Group: {mens_watches_category.group.name}')
            self.stdout.write(f'  - Subgroup: {mens_watches_category.subgroup.name}')
            self.stdout.write(f'  - Gender: {mens_watches_category.gender.display_name}')
            self.stdout.write(f'  - Clean name: {mens_watches_category.get_clean_name()}')
        else:
            self.stdout.write(f'Using existing category: {mens_watches_category.name}')
        
        # Step 5: Show the complete structure
        self.stdout.write('\n' + '='*50)
        self.stdout.write('COMPLETE CATEGORY STRUCTURE:')
        self.stdout.write('='*50)
        
        for group in CategoryGroup.objects.filter(is_active=True).order_by('display_order'):
            self.stdout.write(f'\n📁 {group.name} ({group.get_display_name()})')
            if group.description:
                self.stdout.write(f'   Description: {group.description}')
            
            for subgroup in group.subgroups.filter(is_active=True).order_by('display_order'):
                self.stdout.write(f'  └── 📂 {subgroup.name} ({subgroup.get_display_name()})')
                
                for category in subgroup.categories.filter(is_visible=True).order_by('name'):
                    gender_display = f" [{category.gender.display_name}]" if category.gender else ""
                    self.stdout.write(f'      └── 🏷️  {category.name}{gender_display}')
                    self.stdout.write(f'          Clean name: {category.get_clean_name()}')
                    self.stdout.write(f'          Product count: {category.get_product_count()}')
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write('API ENDPOINTS TO TEST:')
        self.stdout.write('='*50)
        self.stdout.write('1. New improved categories: http://127.0.0.1:8000/shop/api/improved-categories/')
        self.stdout.write(f'2. Group products: http://127.0.0.1:8000/shop/api/groups/{watches_group.id}/products/')
        self.stdout.write('3. Django Admin: http://127.0.0.1:8000/admin/')
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ Men\'s watches category created successfully!')
        ) 