#!/usr/bin/env python3
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myshop.settings')
django.setup()

from shop.models import Attribute, NewAttributeValue, ProductAttribute, ProductAttributeValue

def replace_brands_with_persian():
    print("🔄 Starting brand replacement process...")
    
    persian_brands = [
        'رولکس', 'اومگا', 'پاتک فیلیپ', 'اودمار پیگه', 'کارتیه',
        'برایتلینگ', 'تگ هویر', 'IWC', 'جگر لکولتر', 'واشرون کنستانتین',
        'لانگه اند زونه', 'بلانپین', 'اوریس', 'لونژین', 'تیسو',
        'سیکو', 'سیتیزن', 'کاسیو', 'اپل', 'سامسونگ', 'گارمین',
        'کنستانتین چایکین', 'ریچارد میل', 'هابلوت', 'پنرای'
    ]

    brand_mapping = {
        'Rolex': 'رولکس',
        'Omega': 'اومگا', 
        'Cartier': 'کارتیه',
        'Patek Philippe': 'پاتک فیلیپ',
        'Audemars Piguet': 'اودمار پیگه',
        'Tag Heuer': 'تگ هویر',
        'Breitling': 'برایتلینگ',
        'IWC': 'IWC',
        'Panerai': 'پنرای',
        'Hublot': 'هابلوت'
    }
    
    try:
        # Find brand attribute by either English or Persian key
        brand_attribute = None
        for candidate_key in ('brand', 'برند'):
            try:
                brand_attribute = Attribute.objects.get(key=candidate_key)
                break
            except Attribute.DoesNotExist:
                continue
        if not brand_attribute:
            print("❌ Brand attribute not found with key 'brand' or 'برند'. Create it first.")
            return

        print(f"✅ Using brand attribute with key: {brand_attribute.key}")
        
        # Delete all existing predefined brand values
        deleted_count = NewAttributeValue.objects.filter(attribute=brand_attribute).delete()[0]
        print(f"🗑️ Deleted {deleted_count} existing brand values")
        
        # Create new Persian brand values
        created_brands = []
        for display_order, brand in enumerate(persian_brands):
            created_brands.append(NewAttributeValue.objects.create(
                attribute=brand_attribute,
                value=brand,
                display_order=display_order
            ))
        print(f"✅ Created {len(created_brands)} Persian brand values")
        
        # Update legacy ProductAttribute records (key/value string pairs) for both keys
        legacy_updated = 0
        for english_brand, persian_brand in brand_mapping.items():
            legacy_updated += ProductAttribute.objects.filter(
                key__in=['brand', 'برند'],
                value=english_brand
            ).update(value=persian_brand)
        print(f"🔄 Updated {legacy_updated} legacy product brand attributes")
        
        # Update new ProductAttributeValue records (FK to NewAttributeValue)
        new_updated = 0
        for english_brand, persian_brand in brand_mapping.items():
            persian_brand_value = NewAttributeValue.objects.filter(
                attribute=brand_attribute,
                value=persian_brand
            ).first()
            if persian_brand_value:
                new_updated += ProductAttributeValue.objects.filter(
                    attribute=brand_attribute,
                    attribute_value__value=english_brand
                ).update(attribute_value=persian_brand_value)
        print(f"🔄 Updated {new_updated} new product brand attributes")
        
        # Update custom text values
        custom_updated = 0
        for english_brand, persian_brand in brand_mapping.items():
            custom_updated += ProductAttributeValue.objects.filter(
                attribute=brand_attribute,
                custom_value=english_brand
            ).update(custom_value=persian_brand)
        print(f"🔄 Updated {custom_updated} custom brand values")
        
        print("\n🎉 Brand replacement completed.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    replace_brands_with_persian()
