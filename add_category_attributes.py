#!/usr/bin/env python3
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import Category, CategoryAttribute, AttributeValue

def add_category_attributes():
    try:
        # Get the ساعت مردانه category
        category = Category.objects.get(name='ساعت مردانه')
        print(f"✅ Category: {category.name}")
        
        # Define the attributes we want to add
        attributes_to_add = [
            {
                'key': 'برند',
                'type': 'select',
                'required': True,
                'values': ['Rolex', 'Omega', 'Cartier', 'Patek Philippe', 'Audemars Piguet', 'Tag Heuer', 'Breitling', 'IWC', 'Panerai', 'Hublot']
            },
            {
                'key': 'سری',
                'type': 'select',
                'required': True,
                'values': ['Submariner', 'Daytona', 'GMT-Master', 'Seamaster', 'Speedmaster', 'Constellation', 'Santos', 'Nautilus', 'Royal Oak', 'Chronograph']
            },
            {
                'key': 'مدل',
                'type': 'select',
                'required': True,
                'values': ['Professional', 'Classic', 'Sport', 'Luxury', 'Heritage', 'Modern', 'Vintage', 'Limited Edition', 'Special Edition', 'Anniversary']
            },
            {
                'key': 'جنسیت',
                'type': 'select',
                'required': True,
                'values': ['مردانه', 'زنانه', 'یونیسکس']
            },
            {
                'key': 'جنس بدنه',
                'type': 'select',
                'required': True,
                'values': ['استیل', 'طلای 18 عیار', 'طلای 14 عیار', 'تیتانیوم']
            },
            {
                'key': 'جنس شیشه',
                'type': 'select',
                'required': True,
                'values': ['سافایر', 'مینرال', 'پلکسی']
            },
            {
                'key': 'مقاوم در برابر آب',
                'type': 'select',
                'required': True,
                'values': ['30 متر', '50 متر', '100 متر', '200 متر', '300 متر', '600 متر']
            }
        ]
        
        added_count = 0
        
        for attr_data in attributes_to_add:
            # Check if attribute already exists
            existing_attr = CategoryAttribute.objects.filter(
                category=category,
                key=attr_data['key']
            ).first()
            
            if existing_attr:
                print(f"✅ Attribute '{attr_data['key']}' already exists")
                continue
            
            # Create the category attribute
            cat_attr = CategoryAttribute.objects.create(
                category=category,
                key=attr_data['key'],
                type=attr_data['type'],
                required=attr_data['required']
            )
            
            # Create attribute values
            for value in attr_data['values']:
                AttributeValue.objects.create(
                    attribute=cat_attr,
                    value=value
                )
            
            print(f"✅ Added attribute '{attr_data['key']}' with {len(attr_data['values'])} values")
            added_count += 1
        
        print(f"\n🎉 Added {added_count} new category attributes!")
        
        # Show all category attributes
        print(f"\n📋 All category attributes:")
        for attr in category.category_attributes.all():
            values = [v.value for v in attr.values.all()]
            print(f"   - {attr.key}: {attr.type} ({len(values)} values)")
        
    except Category.DoesNotExist:
        print("❌ Category 'ساعت مردانه' not found")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    add_category_attributes() 