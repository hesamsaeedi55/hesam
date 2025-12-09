# forms.py
from django import forms
from .models import Product, ProductImage, Category, Tag, CategoryAttribute, AttributeValue, ProductAttributeValue
from suppliers.models import Supplier
from decimal import Decimal, InvalidOperation

def normalize_persian_text(text):
    """
    Normalize Persian text by:
    1. Removing zero-width characters
    2. Replacing multiple whitespaces with a single space
    3. Stripping leading/trailing whitespaces
    4. Normalizing Arabic/Persian digits to standard digits
    """
    if not isinstance(text, str):
        return text

    # Remove zero-width characters (ZWNJ, ZWJ, etc.)
    text = text.replace('\u200c', '').replace('\u200d', '')
    
    # Normalize Arabic/Persian digits to standard digits
    digit_map = str.maketrans(
        '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
        '01234567890123456789'
    )
    text = text.translate(digit_map)
    
    # Replace multiple whitespaces with a single space and strip
    text = ' '.join(text.split())
    
    return text.strip()

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class ProductForm(forms.ModelForm):
    images = MultipleFileField(
        required=False,
        label="تصاویر محصول",
        widget=MultipleFileInput(attrs={'class': 'form-control'})
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        empty_label="انتخاب کنید",
        required=True,
        label="دسته‌بندی",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        empty_label="انتخاب کنید",
        required=False,
        label="تامین‌کننده",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        label="برچسب‌ها",
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control multi-select-tags',
            'data-placeholder': 'انتخاب برچسب‌ها',
        })
    )
    
    price_toman = forms.DecimalField(
        max_digits=12,
        decimal_places=0,
        required=True,
        label="قیمت (تومان)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'قیمت به تومان (الزامی)'})
    )
    
    price_usd = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        label="قیمت (دلار)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'قیمت به دلار (اختیاری)'})
    )
    
    reduced_price_toman = forms.DecimalField(
        max_digits=12,
        decimal_places=0,
        required=False,
        label="قیمت کاهش یافته (تومان)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'قیمت تخفیف خورده (اختیاری)'})
    )
    
    discount_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        label="درصد تخفیف",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'درصد تخفیف (اختیاری)', 'step': '0.01', 'min': '0', 'max': '100'})
    )
    
    # Keep these fields for backwards compatibility but hide them
    price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.HiddenInput(),
    )
    
    price_currency = forms.ChoiceField(
        choices=Product.CURRENCY_CHOICES,
        required=False,
        widget=forms.HiddenInput(),
    )
    
    # Entity fields
    model = forms.CharField(
        max_length=100,
        required=False,
        label="مدل",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    sku = forms.CharField(
        max_length=50,
        required=False,
        label="کد محصول",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    weight = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label="وزن (گرم)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    dimensions = forms.CharField(
        max_length=100,
        required=False,
        label="ابعاد (سانتیمتر)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    warranty = forms.CharField(
        max_length=100,
        required=False,
        label="گارانتی",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    stock_quantity = forms.IntegerField(
        required=True,
        label="تعداد موجودی",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        initial=0
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set initial tags queryset based on category
        if 'instance' in kwargs and kwargs['instance']:
            instance = kwargs['instance']
            if instance.category:
                self.fields['tags'].queryset = Tag.objects.filter(
                    categories=instance.category
                ).distinct()
        elif 'initial' in kwargs and 'category' in kwargs['initial']:
            category = kwargs['initial']['category']
            if category:
                self.fields['tags'].queryset = Tag.objects.filter(
                    categories=category
                ).distinct()
        elif 'data' in kwargs and 'category' in kwargs['data']:
            category_id = kwargs['data']['category']
            if category_id:
                self.fields['tags'].queryset = Tag.objects.filter(
                    categories__id=category_id
                ).distinct()
        
        # Dynamically add fields for category attributes
        category = None
        if 'instance' in kwargs and kwargs['instance'] and kwargs['instance'].category:
            category = kwargs['instance'].category
        elif 'initial' in kwargs and 'category' in kwargs['initial']:
            category = kwargs['initial']['category']
        elif 'data' in kwargs and 'category' in kwargs['data']:
            try:
                category = Category.objects.get(id=kwargs['data']['category'])
            except Exception:
                pass
        if category:
            # Get variant attributes from the form data to exclude them from main form
            variant_attr_keys = []
            if 'data' in kwargs and kwargs['data']:
                variant_attributes = kwargs['data'].get('variant_attributes', '')
                print(f"DEBUG ProductForm: variant_attributes from data: '{variant_attributes}'")
                print(f"DEBUG ProductForm: has_variants from data: '{kwargs['data'].get('has_variants', 'NOT_FOUND')}'")
                if variant_attributes:
                    try:
                        import json
                        variant_attr_keys = json.loads(variant_attributes)
                        print(f"DEBUG ProductForm: parsed variant_attr_keys: {variant_attr_keys}")
                        print(f"DEBUG ProductForm: variant_attr_keys type: {type(variant_attr_keys)}")
                        print(f"DEBUG ProductForm: variant_attr_keys length: {len(variant_attr_keys)}")
                    except Exception as e:
                        print(f"DEBUG ProductForm: error parsing variant_attributes: {e}")
                        pass
                else:
                    print(f"DEBUG ProductForm: variant_attributes is empty or None")
                    # Check if variants are enabled but variant_attributes is missing
                    has_variants = kwargs['data'].get('has_variants') == 'on'
                    if has_variants:
                        print(f"DEBUG ProductForm: WARNING - Variants enabled but variant_attributes is missing!")
                        print(f"DEBUG ProductForm: This will cause duplicate attributes in the main form!")
            else:
                print(f"DEBUG ProductForm: No data in kwargs or kwargs['data'] is None")
                print(f"DEBUG ProductForm: kwargs keys: {list(kwargs.keys())}")
                print(f"DEBUG ProductForm: kwargs['data'] type: {type(kwargs.get('data'))}")
            
            # Ensure category is saved before using in related filters
            if not category.pk:
                category.save()
            attributes = CategoryAttribute.objects.filter(category=category).order_by('display_order', 'key')
            print(f"DEBUG ProductForm: Found {len(attributes)} category attributes")
            print(f"DEBUG ProductForm: Variant attr keys to skip: {variant_attr_keys}")
            
            for attr in attributes:
                # Skip attributes that are used for variants
                if attr.key in variant_attr_keys:
                    print(f"DEBUG ProductForm: Skipping variant attribute: {attr.key}")
                    continue
                
                print(f"DEBUG ProductForm: Creating field for attribute: {attr.key}")
                    
                field_name = f'attr_{attr.key}'
                field_required = attr.required
                
                # Get existing value for this attribute if editing
                initial_value = None
                if 'instance' in kwargs and kwargs['instance']:
                    try:
                        from shop.models import ProductAttribute
                        existing_attr = ProductAttribute.objects.get(
                            product=kwargs['instance'], 
                            key=attr.key
                        )
                        initial_value = existing_attr.value
                        print(f"DEBUG ProductForm: Found existing value for {attr.key}: {initial_value}")
                    except ProductAttribute.DoesNotExist:
                        print(f"DEBUG ProductForm: No existing value for {attr.key}")
                        initial_value = None
                
                # Make size optional for t-shirt categories
                if attr.key.lower() in ['size', 'سایز'] and 'تی شرت' in category.name.lower():
                    field_required = False
                if attr.type == 'text':
                    self.fields[field_name] = forms.CharField(
                        required=field_required,
                        label=attr.key,
                        initial=initial_value,
                        widget=forms.TextInput(attrs={'class': 'form-control'})
                    )
                elif attr.type == 'number':
                    self.fields[field_name] = forms.DecimalField(
                        required=field_required,
                        label=attr.key,
                        initial=initial_value,
                        widget=forms.NumberInput(attrs={'class': 'form-control'})
                    )
                elif attr.type == 'select':
                    choices = [(v.value, v.value) for v in attr.values.order_by('display_order', 'value')]
                    self.fields[field_name] = forms.ChoiceField(
                        required=field_required,
                        label=attr.key,
                        initial=initial_value,
                        choices=choices,
                        widget=forms.Select(attrs={'class': 'form-control'})
                    )
                elif attr.type == 'multiselect':
                    choices = [(v.value, v.value) for v in attr.values.order_by('display_order', 'value')]
                    # For multiselect, split the initial value by comma
                    multiselect_initial = []
                    if initial_value:
                        multiselect_initial = [v.strip() for v in initial_value.split(',') if v.strip()]
                    self.fields[field_name] = forms.MultipleChoiceField(
                        required=field_required,
                        label=attr.key,
                        initial=multiselect_initial,
                        choices=choices,
                        widget=forms.SelectMultiple(attrs={'class': 'form-control'})
                    )
                elif attr.type == 'boolean':
                    # Convert string to boolean for initial value
                    bool_initial = False
                    if initial_value:
                        bool_initial = initial_value.lower() in ['true', '1', 'yes', 'on']
                    self.fields[field_name] = forms.BooleanField(
                        required=field_required,
                        label=attr.key,
                        initial=bool_initial
                    )

    def clean_price_toman(self):
        price_toman = self.cleaned_data['price_toman']
        if isinstance(price_toman, str):
            # Remove commas and convert to decimal
            price_toman = price_toman.replace(',', '')
            try:
                price_toman = Decimal(price_toman)
            except (ValueError, InvalidOperation):
                raise forms.ValidationError('لطفا یک عدد معتبر وارد کنید')
        
        if price_toman <= 0:
            raise forms.ValidationError('قیمت تومان باید بزرگتر از صفر باشد')
        return price_toman
        
    def clean_price_usd(self):
        price_usd = self.cleaned_data.get('price_usd')
        if price_usd is not None and price_usd != '' and str(price_usd).lower() != 'none':
            if isinstance(price_usd, str):
                # Remove commas and convert to decimal
                price_usd = price_usd.replace(',', '')
                try:
                    price_usd = Decimal(price_usd)
                except (ValueError, InvalidOperation):
                    raise forms.ValidationError('لطفا یک عدد معتبر وارد کنید')
            
            if price_usd <= 0:
                raise forms.ValidationError('قیمت دلار باید بزرگتر از صفر باشد')
        elif price_usd == '' or str(price_usd).lower() == 'none':
            return None
        return price_usd
    
    def clean_reduced_price_toman(self):
        reduced_price_toman = self.cleaned_data.get('reduced_price_toman')
        if reduced_price_toman is not None and reduced_price_toman != '':
            if isinstance(reduced_price_toman, str):
                # Remove commas and convert to decimal
                reduced_price_toman = reduced_price_toman.replace(',', '')
                try:
                    reduced_price_toman = Decimal(reduced_price_toman)
                except (ValueError, InvalidOperation):
                    raise forms.ValidationError('لطفا یک عدد معتبر وارد کنید')
            
            if reduced_price_toman <= 0:
                raise forms.ValidationError('قیمت کاهش یافته باید بزرگتر از صفر باشد')
        elif reduced_price_toman == '' or str(reduced_price_toman).lower() == 'none':
            return None
        return reduced_price_toman
    
    def clean_discount_percentage(self):
        discount_percentage = self.cleaned_data.get('discount_percentage')
        if discount_percentage is not None and discount_percentage != '':
            if isinstance(discount_percentage, str):
                try:
                    discount_percentage = Decimal(discount_percentage)
                except (ValueError, InvalidOperation):
                    raise forms.ValidationError('لطفا یک عدد معتبر وارد کنید')
            
            if discount_percentage < 0 or discount_percentage > 100:
                raise forms.ValidationError('درصد تخفیف باید بین 0 تا 100 باشد')
        elif discount_percentage == '' or str(discount_percentage).lower() == 'none':
            return None
        return discount_percentage
        
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        tags = cleaned_data.get('tags')
        
        # Validate that selected tags belong to the selected category
        if category and tags:
            valid_tags = Tag.objects.filter(categories=category)
            for tag in tags:
                if tag not in valid_tags:
                    self.add_error('tags', f'Tag "{tag}" is not valid for the selected category.')
        
        # Set the old price field for compatibility
        if 'price_toman' in cleaned_data and cleaned_data['price_toman']:
            cleaned_data['price'] = cleaned_data['price_toman']
            cleaned_data['price_currency'] = 'TOMAN'
        
        # Validate reduced price against original price
        price_toman = cleaned_data.get('price_toman')
        reduced_price_toman = cleaned_data.get('reduced_price_toman')
        discount_percentage = cleaned_data.get('discount_percentage')
        
        if price_toman and reduced_price_toman:
            if reduced_price_toman >= price_toman:
                self.add_error('reduced_price_toman', 'قیمت کاهش یافته باید کمتر از قیمت اصلی باشد')
        
        # Ensure discount percentage and reduced price are consistent
        if price_toman and discount_percentage and not reduced_price_toman:
            # Calculate reduced price from percentage
            cleaned_data['reduced_price_toman'] = price_toman * (Decimal('1') - discount_percentage / Decimal('100'))
        
        if price_toman and reduced_price_toman and not discount_percentage:
            # Calculate discount percentage from reduced price
            discount = ((price_toman - reduced_price_toman) / price_toman) * Decimal('100')
            cleaned_data['discount_percentage'] = discount
        
        # Remove all references to CategoryAttribute and AttributeValue
        
        return cleaned_data

    def clean_images(self):
        images = self.files.getlist('images')
        if len(images) > 10:
            raise forms.ValidationError('شما نمی‌توانید بیشتر از 10 تصویر آپلود کنید')
        
        # Validate each image
        for image in images:
            if not image.content_type.startswith('image/'):
                raise forms.ValidationError('فقط فایل‌های تصویری مجاز هستند')
            if image.size > 20 * 1024 * 1024:  # 20MB
                raise forms.ValidationError('حجم هر تصویر نباید بیشتر از 20 مگابایت باشد')
        
        return images

    def save(self, commit=True):
        # Respect commit flag: do not perform related queries/writes when commit=False
        product = super().save(commit=commit)

        # If we're not committing yet, defer attribute handling to the caller (view handles it post-save)
        if not commit:
            return product

        # Ensure product has a primary key before creating related attribute rows
        if not getattr(product, 'pk', None):
            product.save()

        # Use category_id for filtering to avoid passing any unsaved instances to related filters
        category_id = getattr(product, 'category_id', None)
        if not category_id:
            return product

        # Save dynamic attributes
        attributes = CategoryAttribute.objects.filter(category_id=category_id)
        for attr in attributes:
            field_name = f'attr_{attr.key}'
            value = self.cleaned_data.get(field_name)
            if value is not None:
                from shop.models import ProductAttribute
                pav, _ = ProductAttribute.objects.get_or_create(product=product, key=attr.key)
                if attr.type == 'multiselect':
                    # Normalize each value in the multiselect list
                    pav.value = ','.join(normalize_persian_text(v) for v in value)
                else:
                    # Normalize single value
                    pav.value = normalize_persian_text(value)
                pav.save()
        return product

    class Meta:
        model = Product
        fields = ['name', 'description', 'price_toman', 'price_usd', 'price', 'price_currency', 
                  'category', 'supplier', 'tags', 'is_active', 'model', 'sku', 'weight', 
                  'dimensions', 'warranty', 'stock_quantity', 'reduced_price_toman', 'discount_percentage']

# class ProductImageForm(forms.ModelForm):
#     image = forms.ImageField(widget=forms.ClearableFileInput(attrs={'multiple': True}))

#     class Meta:
#         model = ProductImage
#         fields = ['image']

class TagForm(forms.ModelForm):
    """
    Custom form for Tag model that handles Persian text in slug field
    """
    slug = forms.SlugField(
        max_length=100,
        required=False,
        help_text="Leave empty to auto-generate. For Persian text, a unique ID will be created."
    )
    
    class Meta:
        model = Tag
        fields = ['name', 'slug', 'categories']
        
    def clean_slug(self):
        """
        Allow slug to be empty; it will be auto-generated in the model save method
        """
        slug = self.cleaned_data.get('slug')
        if not slug:
            # We'll handle this in the model save method
            return ''
        return slug
