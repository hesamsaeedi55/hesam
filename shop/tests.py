from django.test import TestCase
from django.core.management import call_command
from shop.models import Category, CategoryAttribute, AttributeValue

# Create your tests here.

class CategoryAttributeInheritanceTest(TestCase):
    def setUp(self):
        # Create a parent category
        self.parent_category = Category.objects.create(name='ساعت')
        
        # Create a child category
        self.child_category = Category.objects.create(
            name='ساعت مردانه', 
            parent=self.parent_category
        )
        
        # Create some attributes for the parent category
        self.parent_attr1 = CategoryAttribute.objects.create(
            category=self.parent_category,
            key='brand',
            type='select',
            label_fa='برند'
        )
        
        # Add some values to the parent attribute
        AttributeValue.objects.create(
            attribute=self.parent_attr1,
            value='رولکس',
            display_order=1
        )
        AttributeValue.objects.create(
            attribute=self.parent_attr1,
            value='کاسیو',
            display_order=2
        )
        
        # Create another parent attribute
        self.parent_attr2 = CategoryAttribute.objects.create(
            category=self.parent_category,
            key='movement_type',
            type='select',
            label_fa='نوع موومنت'
        )
        
        # Add values to the second attribute
        AttributeValue.objects.create(
            attribute=self.parent_attr2,
            value='اتوماتیک',
            display_order=1
        )
        AttributeValue.objects.create(
            attribute=self.parent_attr2,
            value='کوارتز',
            display_order=2
        )

    def test_attribute_inheritance(self):
        """
        Test that attributes are automatically inherited from parent to child category
        """
        # Attributes should already be inherited via signals
        self.assertEqual(
            CategoryAttribute.objects.filter(category=self.child_category).count(), 
            2, 
            "Two attributes should be automatically inherited from parent"
        )

        # Running the command should be idempotent and not change counts
        call_command('inherit_category_attributes')
        
        # Check that attributes have been inherited
        inherited_attrs = CategoryAttribute.objects.filter(category=self.child_category)
        self.assertEqual(
            inherited_attrs.count(), 
            2, 
            "Two attributes should be inherited from parent"
        )
        
        # Check specific attribute details
        brand_attr = inherited_attrs.get(key='brand')
        self.assertEqual(brand_attr.type, 'select')
        self.assertEqual(brand_attr.label_fa, 'برند')
        
        # Check inherited attribute values
        brand_values = AttributeValue.objects.filter(attribute=brand_attr)
        self.assertEqual(brand_values.count(), 2)
        self.assertSetEqual(
            set(brand_values.values_list('value', flat=True)), 
            {'رولکس', 'کاسیو'}
        )
        
        # Check the other inherited attribute
        movement_attr = inherited_attrs.get(key='movement_type')
        movement_values = AttributeValue.objects.filter(attribute=movement_attr)
        self.assertEqual(movement_values.count(), 2)
        self.assertSetEqual(
            set(movement_values.values_list('value', flat=True)), 
            {'اتوماتیک', 'کوارتز'}
        )

    def test_no_duplicate_inheritance(self):
        """
        Test that running the command multiple times doesn't create duplicate attributes
        """
        # Attributes are auto-inherited; capture initial count
        initial_count = CategoryAttribute.objects.filter(category=self.child_category).count()
        
        # Second inheritance
        call_command('inherit_category_attributes')
        subsequent_count = CategoryAttribute.objects.filter(category=self.child_category).count()
        
        # Counts should be the same
        self.assertEqual(
            initial_count, 
            subsequent_count, 
            "Repeated inheritance should not create duplicate attributes"
        )

    def test_specific_category_inheritance(self):
        """
        Test inheritance for a specific category
        """
        # Create another child category
        another_child = Category.objects.create(
            name='ساعت زنانه', 
            parent=self.parent_category
        )
        
        # Inherit attributes for a specific category
        call_command('inherit_category_attributes', '--category', str(another_child.id))
        
        # Check attributes for the specific category
        inherited_attrs = CategoryAttribute.objects.filter(category=another_child)
        self.assertEqual(
            inherited_attrs.count(), 
            2, 
            "Two attributes should be inherited for the specific category"
        )
