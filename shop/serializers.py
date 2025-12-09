from rest_framework import serializers
from django.db import models
from .models import Product, ProductAttributeValue, ProductAttribute, Category, Wishlist, SpecialOffer, SpecialOfferProduct, ProductVariant

class LegacyProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ['key', 'value']

class ProductAttributeValueSerializer(serializers.ModelSerializer):
    attribute = serializers.CharField(source='attribute.key')
    value = serializers.SerializerMethodField()
    persian_label = serializers.SerializerMethodField()

    class Meta:
        model = ProductAttributeValue
        fields = ['attribute', 'value', 'persian_label']

    def get_value(self, obj):
        # Prefer attribute_value (FK to NewAttributeValue), else custom_value
        if obj.attribute_value:
            return obj.attribute_value.value
        return obj.custom_value

    def get_persian_label(self, obj):
        # Return persian_label if available, otherwise return the value
        if obj.attribute_value and obj.attribute_value.persian_label:
            return obj.attribute_value.persian_label
        return self.get_value(obj)

class ProductImageSerializer(serializers.Serializer):
    url = serializers.CharField()
    is_primary = serializers.BooleanField()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class ProductSerializer(serializers.ModelSerializer):
    price_toman = serializers.FloatField()
    price_usd = serializers.FloatField(allow_null=True)
    stock_quantity = serializers.IntegerField()
    created_at = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    attributes = serializers.SerializerMethodField()
    category = CategorySerializer(read_only=True)
    
    # Reduced price fields
    reduced_price_toman = serializers.DecimalField(max_digits=12, decimal_places=0, allow_null=True, read_only=True)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True, read_only=True)
    
    # Special offers fields
    original_price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    discount_percentage_offer = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    
    # Variants field
    variants_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price_toman', 'price_usd', 'model', 'sku',
            'stock_quantity', 'created_at', 'images', 'attributes', 'category', 'is_new_arrival', 'is_active',
            'is_in_special_offers', 'reduced_price_toman', 'discount_percentage', 
            'original_price', 'discounted_price', 'discount_percentage_offer', 'has_discount',
            'variants_count'
        ]

    def get_created_at(self, obj):
        # Return as seconds since 1970 for Swift Date compatibility
        return obj.created_at.timestamp()
    
    def get_original_price(self, obj):
        # Return the original price (same as price_toman for clarity)
        return float(obj.price_toman) if obj.price_toman else None
    
    def get_discounted_price(self, obj):
        """Get the discounted price - prioritize product's own reduced price, then special offers"""
        # First check if product has its own reduced price
        if obj.reduced_price_toman:
            return float(obj.reduced_price_toman)
        
        # Check if this product is in any active special offers
        from django.utils import timezone
        now = timezone.now()
        
        special_offer_product = obj.specialofferproduct_set.filter(
            offer__enabled=True,
            offer__is_active=True,
            offer__valid_from__lte=now,
            is_active=True
        ).filter(
            models.Q(offer__valid_until__isnull=True) | models.Q(offer__valid_until__gte=now)
        ).first()
        
        if special_offer_product and special_offer_product.discount_percentage > 0:
            original_price = special_offer_product.original_price or obj.price_toman
            if original_price:
                from decimal import Decimal
                discount_decimal = Decimal(str(special_offer_product.discount_percentage)) / Decimal('100')
                discounted_price = original_price * (Decimal('1') - discount_decimal)
                return float(discounted_price)
        
        return float(obj.price_toman) if obj.price_toman else None
    
    def get_discount_percentage_offer(self, obj):
        """Get the discount percentage from special offers (separate from product's own discount)"""
        from django.utils import timezone
        now = timezone.now()
        
        special_offer_product = obj.specialofferproduct_set.filter(
            offer__enabled=True,
            offer__is_active=True,
            offer__valid_from__lte=now,
            is_active=True
        ).filter(
            models.Q(offer__valid_until__isnull=True) | models.Q(offer__valid_until__gte=now)
        ).first()
        
        return float(special_offer_product.discount_percentage) if special_offer_product else 0
    
    def get_has_discount(self, obj):
        """Check if product has an active discount (either own discount or special offer)"""
        # Check product's own discount first
        if obj.discount_percentage and obj.discount_percentage > 0:
            return True
        # Then check special offers
        return self.get_discount_percentage_offer(obj) > 0

    def get_variants_count(self, obj):
        """Get the count of active variants for this product"""
        return obj.variants.filter(is_active=True).count()

    def get_images(self, obj):
        request = self.context.get('request', None)
        images = []
        for image in obj.images.all():
            url = image.image.url
            if request and not url.startswith(('http://', 'https://')):
                url = request.build_absolute_uri(url)
            images.append({'url': url, 'is_primary': image.is_primary})
        
        # If no direct product images, try to get from variants
        if not images:
            variants = ProductVariant.objects.filter(product=obj, is_active=True).order_by('sku')
            default_variant = variants.filter(is_default=True).first()
            if not default_variant:
                default_variant = variants.first()
            
            if default_variant:
                first_variant_image = default_variant.images.first()
                if first_variant_image and first_variant_image.image:
                    url = first_variant_image.image.url
                    if request and not url.startswith(('http://', 'https://')):
                        url = request.build_absolute_uri(url)
                    images.append({'url': url, 'is_primary': True})
        
        return images

    def get_attributes(self, obj):
        # Get allowed keys for this product's category
        allowed_keys = set()
        if obj.category:
            allowed_keys = set(obj.category.category_attributes.values_list('key', flat=True))
        attributes = []
        
        # Collect from new system (attribute_values)
        for av in obj.attribute_values.all():
            key = av.attribute.key
            value = av.get_display_value()
            if value is not None and value != '':
                attributes.append({'key': key, 'value': value, 'source': 'new'})
        
        # Collect from legacy system (legacy_attribute_set)
        for legacy in obj.legacy_attribute_set.all():
            key = legacy.key
            value = legacy.value
            if value is not None and value != '':
                attributes.append({'key': key, 'value': value, 'source': 'legacy'})
        
        # Remove duplicates with improved logic for brand conflicts
        seen = set()
        unique_attributes = []
        
        # Handle brand attributes specially to resolve conflicts
        brand_attrs = [attr for attr in attributes if attr['key'] == 'brand']
        brand_persian_attrs = [attr for attr in attributes if attr['key'] == 'برند']
        other_attrs = [attr for attr in attributes if attr['key'] not in ['brand', 'برند']]
        
        # For brand attributes, prioritize English 'brand' over Persian 'برند'
        if brand_attrs:
            # Take the first non-empty English brand attribute
            for attr in brand_attrs:
                if attr['value'] and attr['value'].strip():
                    unique_attributes.append({'key': 'brand', 'value': attr['value']})
                    seen.add('brand')
                    break
        
        # If no English brand found, use Persian brand
        if 'brand' not in seen and brand_persian_attrs:
            for attr in brand_persian_attrs:
                if attr['value'] and attr['value'].strip():
                    unique_attributes.append({'key': 'brand', 'value': attr['value']})
                    seen.add('brand')
                    break
        
        # Process other attributes
        for attr in other_attrs:
            if attr['key'] not in seen:
                seen.add(attr['key'])
                unique_attributes.append({'key': attr['key'], 'value': attr['value']})
        
        # Only include attributes defined for the product's category
        if allowed_keys:
            unique_attributes = [attr for attr in unique_attributes if attr['key'] in allowed_keys]
        
        return unique_attributes


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    
    class Meta:
        model = Wishlist
        fields = ['id', 'product', 'customer_name', 'customer_email', 'created_at']
        read_only_fields = ['customer']


class WishlistCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating wishlist items"""
    product_id = serializers.IntegerField()
    
    class Meta:
        model = Wishlist
        fields = ['product_id']
    
    def validate_product_id(self, value):
        """Validate that the product exists and is active"""
        try:
            product = Product.objects.get(id=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or inactive")
        return value
    
    def create(self, validated_data):
        """Create wishlist item"""
        product_id = validated_data['product_id']
        customer = self.context['request'].user
        
        # Create or get existing wishlist item
        wishlist_item, created = Wishlist.objects.get_or_create(
            customer=customer,
            product_id=product_id
        )
        
        # Store whether it was created or already existed
        wishlist_item._was_created = created
        
        return wishlist_item
    
    def to_representation(self, instance):
        """Return a complete response with all relevant data"""
        from django.utils import timezone
        
        # Get the product details
        product = instance.product
        
        # Get primary image URL
        primary_image = product.images.filter(is_primary=True).first()
        image_url = primary_image.image.url if primary_image else None
        
        # Build absolute URL if needed
        request = self.context.get('request')
        if image_url and request and not image_url.startswith(('http://', 'https://')):
            image_url = request.build_absolute_uri(image_url)
        
        # Check if this was newly created or already existed
        was_created = getattr(instance, '_was_created', True)
        
        if was_created:
            message = 'محصول با موفقیت به لیست علاقه‌مندی اضافه شد'
            status_code = 201
        else:
            message = 'محصول قبلاً در لیست علاقه‌مندی شما موجود است'
            status_code = 200
        
        return {
            'success': True,
            'message': message,
            'action': 'added' if was_created else 'already_exists',
            'wishlist_item': {
                'id': instance.id,
                'product_id': product.id,
                'product_name': product.name,
                'product_price_toman': float(product.price_toman) if product.price_toman else None,
                'product_price_usd': float(product.price_usd) if product.price_usd else None,
                'product_category': product.category.name if product.category else None,
                'image_url': image_url,
                'created_at': instance.created_at.isoformat(),
                'customer_id': instance.customer.id,
                'customer_name': instance.customer.get_full_name() if hasattr(instance.customer, 'get_full_name') else instance.customer.username
            },
            'timestamp': timezone.now().isoformat(),
            'status_code': status_code
        }


class WishlistSimpleSerializer(serializers.ModelSerializer):
    """Simple serializer for wishlist without nested product data"""
    product_id = serializers.IntegerField(source='product.id')
    product_name = serializers.CharField(source='product.name')
    product_price = serializers.CharField(source='product.get_formatted_toman_price')
    
    class Meta:
        model = Wishlist
        fields = ['id', 'product_id', 'product_name', 'product_price', 'created_at'] 


class SpecialOfferProductSerializer(serializers.ModelSerializer):
    """Serializer for products in special offers"""
    product = serializers.SerializerMethodField()
    discount_display = serializers.CharField(source='get_discount_display', read_only=True)
    
    class Meta:
        model = SpecialOfferProduct
        fields = [
            'id', 'product', 'discount_percentage', 'discount_amount', 
            'original_price', 'discounted_price', 'discount_display', 'display_order'
        ]
    
    def get_product(self, instance):
        """Get product with special offer discount context"""
        product_data = ProductSerializer(instance.product, context=self.context).data
        
        # Override discount fields with this special offer's values
        original_price = instance.original_price if instance.original_price else instance.product.price_toman
        
        # Calculate discounted price
        discounted_price = original_price
        if instance.discount_percentage > 0 and original_price:
            from decimal import Decimal
            discount_decimal = Decimal(str(instance.discount_percentage)) / Decimal('100')
            discounted_price = original_price * (Decimal('1') - discount_decimal)
        
        # Update product data with special offer values
        product_data['original_price'] = float(original_price) if original_price else None
        product_data['discounted_price'] = float(discounted_price) if discounted_price else None
        product_data['discount_percentage'] = instance.discount_percentage
        product_data['has_discount'] = instance.discount_percentage > 0
        
        return product_data
    
    def to_representation(self, instance):
        """Custom representation to handle decimal fields and calculate discounted price"""
        data = super().to_representation(instance)
        
        # Get the original price (use product price if not set)
        original_price = instance.original_price if instance.original_price else instance.product.price_toman
        
        # Calculate discounted price if not already calculated
        discounted_price = instance.discounted_price
        if not discounted_price and instance.discount_percentage > 0 and original_price:
            from decimal import Decimal
            discount_decimal = Decimal(str(instance.discount_percentage)) / Decimal('100')
            discounted_price = original_price * (Decimal('1') - discount_decimal)
        elif not discounted_price:
            discounted_price = original_price
        
        # Convert Decimal fields to float for JSON serialization
        data['original_price'] = float(original_price) if original_price else None
        data['discounted_price'] = float(discounted_price) if discounted_price else None
        if data.get('discount_amount') is not None:
            data['discount_amount'] = float(instance.discount_amount) if instance.discount_amount else None
            
        return data


class SpecialOfferSerializer(serializers.ModelSerializer):
    """Serializer for special offers"""
    products = SpecialOfferProductSerializer(many=True, read_only=True)
    remaining_time = serializers.SerializerMethodField()
    is_currently_valid = serializers.SerializerMethodField()
    banner_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = SpecialOffer
        fields = [
            'id', 'title', 'description', 'offer_type', 'display_style',
            'banner_image_url', 'banner_action_type', 'banner_action_target', 'banner_external_url',
            'valid_from', 'valid_until', 'enabled', 'is_active', 'display_order',
            'products', 'remaining_time', 'is_currently_valid'
        ]
    
    def get_remaining_time(self, obj):
        """Get remaining time in seconds"""
        return obj.get_remaining_time()
    
    def get_is_currently_valid(self, obj):
        """Check if offer is currently valid"""
        return obj.is_currently_valid()
    
    def get_banner_image_url(self, obj):
        """Get full URL for banner image"""
        if obj.banner_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.banner_image.url)
            return obj.banner_image.url
        return None 