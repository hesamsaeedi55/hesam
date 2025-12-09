# Flexible Attribute System Usage Guide

## Overview
The flexible attribute system allows you to create reusable attributes and assign them to multiple product subcategories. This means you can define attributes like "سایز" (size), "رنگ" (color), "جنس" (material) once and then use them across different clothing categories.

## Attribute Inheritance

### What is Attribute Inheritance?
Attribute inheritance allows parent categories to automatically pass their attributes to child categories. This feature simplifies attribute management by ensuring that child categories have the same attributes as their parent.

### How Attribute Inheritance Works
- When a parent category has attributes defined, these attributes can be automatically copied to its child categories.
- Inheritance includes both the attribute definition and its predefined values.
- Attributes are inherited only once to prevent duplicates.

### Using Attribute Inheritance

#### Management Command
You can inherit attributes using the Django management command:

```bash
# Inherit attributes for all child categories
python manage.py inherit_category_attributes

# Inherit attributes for a specific category
python manage.py inherit_category_attributes --category 123

# Perform a dry run to see what would be inherited
python manage.py inherit_category_attributes --dry-run
```

#### Example Scenario
```
Parent Category: ساعت (Watches)
- Attributes: 
  1. برند (Brand) - with values: رولکس, کاسیو
  2. نوع موومنت (Movement Type) - with values: اتوماتیک, کوارتز

Child Categories: 
- ساعت مردانه (Men's Watches)
- ساعت زنانه (Women's Watches)

After inheritance, both child categories will have the same attributes and values as the parent.
```

### Inheritance Rules
- Attributes are only inherited if they don't already exist in the child category.
- The entire attribute definition (key, type, label) and its values are copied.
- You can run the inheritance command multiple times safely without creating duplicates.

### Customization
- After inheritance, you can still modify or add attributes to child categories independently.
- The inheritance process does not modify existing attributes in child categories.

## Programmatic Usage

```python
# Manually trigger inheritance for a specific category
from django.core.management import call_command

# Inherit all attributes
call_command('inherit_category_attributes')

# Inherit for a specific category
call_command('inherit_category_attributes', '--category', category_id)
```

## Best Practices
1. Define comprehensive attributes at the parent category level.
2. Use inheritance to maintain consistency across related categories.
3. Review and adjust inherited attributes as needed.

## Troubleshooting
- If attributes are not inheriting, check:
  1. The parent category has attributes
  2. The child category is correctly linked to the parent
  3. No existing attributes in the child category with the same key 