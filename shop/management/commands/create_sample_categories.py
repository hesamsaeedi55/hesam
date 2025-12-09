from django.core.management.base import BaseCommand
from shop.models import CategoryGender, CategoryGroup, CategorySubgroup, Category


class Command(BaseCommand):
    help = 'Create sample categories using the new improved category system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating sample categories...'))
        
        # Step 1: Create all genders
        genders = {
            'men': {'display_name': 'مردانه', 'order': 1},
            'women': {'display_name': 'زنانه', 'order': 2},
            'unisex': {'display_name': 'یونیسکس', 'order': 3},
            'general': {'display_name': 'عمومی', 'order': 4},
        }
        
        gender_objects = {}
        for gender_key, gender_data in genders.items():
            gender_obj, created = CategoryGender.objects.get_or_create(
                name=gender_key,
                defaults={
                    'display_name': gender_data['display_name'],
                    'display_order': gender_data['order'],
                    'is_active': True
                }
            )
            gender_objects[gender_key] = gender_obj
            if created:
                self.stdout.write(f'Created gender: {gender_obj.display_name}')
        
        # Step 2: Create category groups
        groups_data = [
            {
                'name': 'ساعت',
                'label': 'ساعت',
                'description': 'انواع ساعت‌های مچی و دیواری',
                'icon': 'watch',
                'order': 1,
                'supports_gender': True
            },
            {
                'name': 'پوشاک',
                'label': 'پوشاک',
                'description': 'لباس‌های مردانه و زنانه',
                'icon': 'clothing',
                'order': 2,
                'supports_gender': True
            },
            {
                'name': 'کتاب',
                'label': 'کتاب',
                'description': 'کتاب‌های مختلف',
                'icon': 'book',
                'order': 3,
                'supports_gender': False
            }
        ]
        
        group_objects = {}
        for group_data in groups_data:
            group_obj, created = CategoryGroup.objects.get_or_create(
                name=group_data['name'],
                defaults={
                    'label': group_data['label'],
                    'description': group_data['description'],
                    'icon': group_data['icon'],
                    'display_order': group_data['order'],
                    'supports_gender': group_data['supports_gender'],
                    'is_active': True
                }
            )
            group_objects[group_data['name']] = group_obj
            if created:
                self.stdout.write(f'Created group: {group_obj.name}')
        
        # Step 3: Create subgroups
        subgroups_data = [
            # Watches subgroups
            {'name': 'ساعت مچی', 'group': 'ساعت', 'label': 'ساعت مچی', 'order': 1},
            {'name': 'ساعت دیواری', 'group': 'ساعت', 'label': 'ساعت دیواری', 'order': 2},
            
            # Clothing subgroups
            {'name': 'تی‌شرت', 'group': 'پوشاک', 'label': 'تی‌شرت', 'order': 1},
            {'name': 'شلوار', 'group': 'پوشاک', 'label': 'شلوار', 'order': 2},
            {'name': 'کت', 'group': 'پوشاک', 'label': 'کت', 'order': 3},
            
            # Book subgroups
            {'name': 'رمان', 'group': 'کتاب', 'label': 'رمان', 'order': 1},
            {'name': 'کتاب‌های علمی', 'group': 'کتاب', 'label': 'کتاب‌های علمی', 'order': 2},
        ]
        
        subgroup_objects = {}
        for subgroup_data in subgroups_data:
            group_obj = group_objects[subgroup_data['group']]
            subgroup_obj, created = CategorySubgroup.objects.get_or_create(
                name=subgroup_data['name'],
                group=group_obj,
                defaults={
                    'label': subgroup_data['label'],
                    'display_order': subgroup_data['order'],
                    'is_active': True
                }
            )
            subgroup_objects[f"{subgroup_data['group']}_{subgroup_data['name']}"] = subgroup_obj
            if created:
                self.stdout.write(f'Created subgroup: {subgroup_obj.name} in {group_obj.name}')
        
        # Step 4: Create categories
        categories_data = [
            # Watches categories
            {
                'name': 'ساعت مردانه',
                'label': 'ساعت مردانه',
                'group': 'ساعت',
                'subgroup': 'ساعت مچی',
                'gender': 'men',
                'section': 'men'
            },
            {
                'name': 'ساعت زنانه',
                'label': 'ساعت زنانه',
                'group': 'ساعت',
                'subgroup': 'ساعت مچی',
                'gender': 'women',
                'section': 'women'
            },
            {
                'name': 'ساعت یونیسکس',
                'label': 'ساعت یونیسکس',
                'group': 'ساعت',
                'subgroup': 'ساعت مچی',
                'gender': 'unisex',
                'section': 'unisex'
            },
            {
                'name': 'ساعت دیواری',
                'label': 'ساعت دیواری',
                'group': 'ساعت',
                'subgroup': 'ساعت دیواری',
                'gender': 'general',
                'section': 'general'
            },
            
            # Clothing categories
            {
                'name': 'تی‌شرت مردانه',
                'label': 'تی‌شرت مردانه',
                'group': 'پوشاک',
                'subgroup': 'تی‌شرت',
                'gender': 'men',
                'section': 'men'
            },
            {
                'name': 'تی‌شرت زنانه',
                'label': 'تی‌شرت زنانه',
                'group': 'پوشاک',
                'subgroup': 'تی‌شرت',
                'gender': 'women',
                'section': 'women'
            },
            {
                'name': 'شلوار مردانه',
                'label': 'شلوار مردانه',
                'group': 'پوشاک',
                'subgroup': 'شلوار',
                'gender': 'men',
                'section': 'men'
            },
            {
                'name': 'شلوار زنانه',
                'label': 'شلوار زنانه',
                'group': 'پوشاک',
                'subgroup': 'شلوار',
                'gender': 'women',
                'section': 'women'
            },
            {
                'name': 'کت مردانه',
                'label': 'کت مردانه',
                'group': 'پوشاک',
                'subgroup': 'کت',
                'gender': 'men',
                'section': 'men'
            },
            {
                'name': 'کت زنانه',
                'label': 'کت زنانه',
                'group': 'پوشاک',
                'subgroup': 'کت',
                'gender': 'women',
                'section': 'women'
            },
            
            # Book categories (no gender)
            {
                'name': 'رمان',
                'label': 'رمان',
                'group': 'کتاب',
                'subgroup': 'رمان',
                'gender': 'general',
                'section': 'general'
            },
            {
                'name': 'کتاب‌های علمی',
                'label': 'کتاب‌های علمی',
                'group': 'کتاب',
                'subgroup': 'کتاب‌های علمی',
                'gender': 'general',
                'section': 'general'
            },
        ]
        
        for category_data in categories_data:
            group_obj = group_objects[category_data['group']]
            subgroup_obj = subgroup_objects[f"{category_data['group']}_{category_data['subgroup']}"]
            gender_obj = gender_objects[category_data['gender']]
            
            category_obj, created = Category.objects.get_or_create(
                name=category_data['name'],
                defaults={
                    'label': category_data['label'],
                    'category_type': 'direct',
                    'is_visible': True,
                    'display_section': category_data['section'],
                    'group': group_obj,
                    'subgroup': subgroup_obj,
                    'gender': gender_obj
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created category: {category_obj.name}')
                )
        
        # Step 5: Show the complete structure
        self.stdout.write('\n' + '='*60)
        self.stdout.write('COMPLETE CATEGORY STRUCTURE:')
        self.stdout.write('='*60)
        
        for group in CategoryGroup.objects.filter(is_active=True).order_by('display_order'):
            self.stdout.write(f'\n📁 {group.name} ({group.get_display_name()})')
            if group.description:
                self.stdout.write(f'   Description: {group.description}')
            self.stdout.write(f'   Supports gender: {"Yes" if group.supports_gender else "No"}')
            
            for subgroup in group.subgroups.filter(is_active=True).order_by('display_order'):
                self.stdout.write(f'  └── 📂 {subgroup.name} ({subgroup.get_display_name()})')
                
                for category in subgroup.categories.filter(is_visible=True).order_by('name'):
                    gender_display = f" [{category.gender.display_name}]" if category.gender else ""
                    self.stdout.write(f'      └── 🏷️  {category.name}{gender_display}')
                    self.stdout.write(f'          Clean name: {category.get_clean_name()}')
                    self.stdout.write(f'          Section: {category.display_section}')
                    self.stdout.write(f'          Product count: {category.get_product_count()}')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write('API ENDPOINTS TO TEST:')
        self.stdout.write('='*60)
        self.stdout.write('1. New improved categories: http://127.0.0.1:8000/shop/api/improved-categories/')
        
        for group in CategoryGroup.objects.filter(is_active=True).order_by('display_order'):
            self.stdout.write(f'2. {group.name} products: http://127.0.0.1:8000/shop/api/groups/{group.id}/products/')
        
        self.stdout.write('3. Django Admin: http://127.0.0.1:8000/admin/')
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ Sample categories created successfully!')
        )
        self.stdout.write('You can now test the new API endpoints and see the improved structure.') 