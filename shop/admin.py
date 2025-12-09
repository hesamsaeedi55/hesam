# admin.py
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django import forms
from .models import (
    Category, Product, ProductAttribute, ProductImage, ProductVariantImage, Order, OrderItem, Tag, 
    Attribute, ProductAttributeValue, NewAttributeValue, CategoryAttribute, AttributeValue,
    DeletedProduct, Wishlist, CategoryGender, CategoryGroup, CategorySubgroup,
    SpecialOffer, SpecialOfferProduct, ProductVariant, Cart, CartItem
)
from .forms import ProductForm, TagForm
from suppliers.models import SupplierAdmin, User as SupplierUser
# Removed admin_site import to avoid circular import
from .models import persian_slugify
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.db import transaction

# Custom form to allow editing Category ID
class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'
        widgets = {
            'label': forms.TextInput(attrs={
                'placeholder': 'نام نمایشی (مثل: ساعت برای ساعت مردانه)',
                'help_text': 'نام تمیز برای نمایش در اپ'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make the id field editable
        if 'id' not in self.fields:
            self.fields['id'] = forms.IntegerField(
                initial=self.instance.pk if self.instance.pk else None,
                required=False,
                help_text="Change the ID carefully - this affects all related data"
            )
        
        # Add helpful descriptions for category types
        if 'category_type' in self.fields:
            self.fields['category_type'].help_text = """
            <strong>Category Types:</strong><br>
            • <strong>Auto-detect:</strong> Automatically determine based on content (recommended)<br>
            • <strong>Container:</strong> Has subcategories, no direct products (e.g., "ساعت" with "ساعت مردانه", "ساعت زنانه")<br>
            • <strong>Direct:</strong> Has products directly, no subcategories (e.g., "کتاب", "لوازم التحریر")
            """
            self.fields['category_type'].widget.attrs.update({
                'style': 'width: 100%;'
            })
        
        # Add helpful description for display section
        if 'display_section' in self.fields:
            self.fields['display_section'].help_text = """
            <strong>Display Sections:</strong><br>
            • <strong>Men:</strong> Show in men's section<br>
            • <strong>Women:</strong> Show in women's section<br>
            • <strong>Unisex:</strong> Show in unisex section<br>
            • <strong>General:</strong> Show in general section (default)
            """
        
        # Add choices for categorization attribute key
        if 'categorization_attribute_key' in self.fields and self.instance.pk:
            available_keys = self.instance.get_available_attribute_keys()
            choices = [('', '-- انتخاب کنید --')] + [(key, key) for key in available_keys]
            self.fields['categorization_attribute_key'].widget = forms.Select(choices=choices)
            self.fields['categorization_attribute_key'].help_text = f"""
            <strong>ویژگی دسته‌بندی:</strong><br>
            • ویژگی‌های موجود: {', '.join(available_keys) if available_keys else 'هیچ ویژگی‌ای تعریف نشده'}<br>
            • اگر خالی باشد، از اولین ویژگی موجود استفاده می‌شود<br>
            • این ویژگی برای API دسته‌بندی استفاده می‌شود: /api/category/{self.instance.id}/attribute/[KEY]/values/
            """

# New flexible attribute system admins
class AttributeValueInline(admin.TabularInline):
    model = NewAttributeValue
    extra = 1
    fields = ['value', 'persian_label', 'display_order', 'color_code']
    ordering = ['display_order', 'value']

class AttributeAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'type', 'is_filterable', 'display_order')
    list_filter = ('type', 'is_filterable')
    search_fields = ('name', 'key')
    ordering = ('display_order', 'name')
    inlines = [AttributeValueInline]

    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'key', 'type')
        }),
        ('تنظیمات', {
            'fields': ('description', 'is_filterable', 'display_order')
        }),
    )
    


class NewAttributeValueAdmin(admin.ModelAdmin):
    list_display = ('attribute', 'value', 'persian_label', 'display_order', 'color_code')
    list_filter = ('attribute__type', 'attribute')
    search_fields = ('value', 'persian_label', 'attribute__name')
    ordering = ['attribute__name', 'display_order']
    list_editable = ('display_order',)

# Inline for ProductImages in ProductAdmin
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'is_primary', 'order']
    max_num = 10  # محدودیت تعداد تصاویر
    validate_max = True  # اعمال محدودیت
    ordering = ['order']  # مرتب‌سازی بر اساس فیلد order

# Inline for ProductVariants in ProductAdmin
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ['sku', 'attributes', 'price_toman', 'stock_quantity', 'variant_images_preview', 'is_active', 'is_default', 'isDistinctive']
    readonly_fields = ['created_at', 'variant_images_preview']
    verbose_name = 'Product Variant'
    verbose_name_plural = 'Product Variants'
    can_delete = True
    show_change_link = True
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form = formset.form
        
        # Add help text for attributes field
        if 'attributes' in form.base_fields:
            form.base_fields['attributes'].help_text = 'JSON format: {"color": "قرمز", "size": "M"}'
            form.base_fields['attributes'].widget.attrs.update({
                'style': 'width: 100%; height: 60px;',
                'placeholder': '{"color": "قرمز", "size": "M"}'
            })
        
        return formset
    
    def variant_images_preview(self, obj):
        """Display preview of variant images"""
        if not obj or not obj.pk:
            return '-'
        return obj.variant_images_preview()
    variant_images_preview.short_description = 'Images'

# Inline for ProductVariantImages in ProductVariantAdmin
class ProductVariantImageInline(admin.TabularInline):
    model = ProductVariantImage
    extra = 1
    fields = ['image', 'is_primary', 'order']
    max_num = 10  # محدودیت تعداد تصاویر برای هر نوع محصول
    validate_max = True  # اعمال محدودیت
    ordering = ['order']  # مرتب‌سازی بر اساس فیلد order
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form = formset.form
        
        # اضافه کردن اعتبارسنجی برای فیلد order
        original_clean = form.clean
        
        def clean(self):
            cleaned_data = original_clean(self)
            if 'order' in cleaned_data:
                order = cleaned_data['order']
                if order > 10:
                    raise ValidationError(_('شماره ترتیب نمی‌تواند بیشتر از 10 باشد'))
            return cleaned_data
        
        form.clean = clean
        return formset

# Inline for ProductImages in ProductAdmin (separate class)
class ProductImageInlineAdmin(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'is_primary', 'order']
    max_num = 10  # محدودیت تعداد تصاویر
    validate_max = True  # اعمال محدودیت
    ordering = ['order']  # مرتب‌سازی بر اساس فیلد order
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        form = formset.form
        
        # اضافه کردن اعتبارسنجی برای فیلد order
        original_clean = form.clean
        
        def clean(self):
            cleaned_data = original_clean(self)
            if 'order' in cleaned_data:
                order = cleaned_data['order']
                if order > 10:
                    raise ValidationError(_('شماره ترتیب نمی‌تواند بیشتر از 10 باشد'))
            return cleaned_data
        
        form.clean = clean
        return formset

class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    change_form_template = 'admin/shop/category/change_form.html'
    list_display = (
        'id', 'name', 'label', 'parent', 'gender',
        'categorization_attribute_key',
        'get_product_count', 'get_attribute_count'
    )
    search_fields = ('name', 'label', 'id')
    list_filter = ('parent', 'category_type', 'gender')
    inlines = []  # Removed CategoryAttributeInline
    fields = ('id', 'name', 'label', 'parent', 'category_type', 'is_visible', 'display_section', 'gender', 'group', 'subgroup', 'categorization_attribute_key')

    
    def get_attribute_count(self, obj):
        if obj.is_subcategory():
            return obj.category_attributes.count()
        return '-'
    get_attribute_count.short_description = 'تعداد ویژگی‌ها'
    
    def get_product_count(self, obj):
        """Show total product count for this category"""
        count = obj.get_product_count()
        return count if count > 0 else '-'
    get_product_count.short_description = 'تعداد محصولات'
    

    
    def analyze_category_structure(self, request, queryset):
        """Admin action to analyze and display category structure"""
        from django.contrib import messages
        
        for category in queryset:
            has_subcategories = category.subcategories.exists()
            has_direct_products = category.product_set.filter(is_active=True).exists()
            effective_type = category.get_effective_category_type()
            
            message = f"""
            <strong>{category.name}</strong> (ID: {category.id})<br>
            • Has subcategories: {has_subcategories}<br>
            • Has direct products: {has_direct_products}<br>
            • Current type: {category.category_type}<br>
            • Effective type: {effective_type}<br>
            • Product count: {category.get_product_count()}
            """
            messages.info(request, mark_safe(message))
        
        self.message_user(request, f"Analyzed {queryset.count()} categories. Check the messages above for details.")
    analyze_category_structure.short_description = "Analyze category structure and detection logic"
    
    actions = ['analyze_category_structure']

    def quick_set_category_key(self, obj):
        """Inline selector to set categorization key from changelist."""
        available_keys = obj.get_available_attribute_keys()
        # Build a minimal inline form that posts to an admin action-like URL
        options = ''.join(
            f'<option value="{key}" {"selected" if obj.categorization_attribute_key == key else ""}>{key}</option>'
            for key in available_keys
        )
        # Add an empty option for fallback behavior
        empty_selected = '' if obj.categorization_attribute_key else 'selected'
        action_url = reverse('admin:shop_category_set_key', args=[obj.id])
        html = f'''
            <form method="get" action="{action_url}" style="display:flex;gap:6px;align-items:center;">
                <select name="key" style="min-width:140px">
                    <option value="" {empty_selected}>--</option>
                    {options}
                </select>
                <button type="submit" class="button" style="padding:2px 6px;">Save</button>
            </form>
        '''
        return mark_safe(html)
    quick_set_category_key.short_description = 'Set Key'

    def manage_tags_link(self, obj):
        """Link to manage tags for this category"""
        from django.utils.html import format_html
        from django.urls import reverse
        
        tag_count = obj.tags.count()
        if tag_count > 0:
            tag_text = f"🏷️ {tag_count} برچسب"
        else:
            tag_text = "🏷️ بدون برچسب"
        
        url = reverse('admin:manage_category_tags', args=[obj.id])
        return format_html(
            '<a href="{}" class="button" style="background-color: #17a2b8; color: white; padding: 5px 10px; border-radius: 4px; text-decoration: none;">{}</a>',
            url, tag_text
        )
    manage_tags_link.short_description = 'مدیریت برچسب‌ها'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/set-category-key/',
                admin.site.admin_view(self.set_category_key_view),
                name='shop_category_set_key',
            ),
        ]
        return custom_urls + urls

    def set_category_key_view(self, request, object_id):
        from django.shortcuts import get_object_or_404, redirect
        from django.contrib import messages
        category = get_object_or_404(Category, pk=object_id)
        # Support both GET (from inline form) and POST
        key = None
        if request.method == 'POST':
            key = request.POST.get('key') or None
        else:
            key = request.GET.get('key') or None

        if key is not None:
            # Validate selected key belongs to category's attributes (or empty)
            if key and not category.category_attributes.filter(key=key).exists():
                messages.error(request, _('Invalid key for this category'))
            else:
                category.categorization_attribute_key = key or None
                category.save(update_fields=['categorization_attribute_key'])
                messages.success(request, _('Categorization key updated.'))
        # Redirect back to changelist preserving filters
        return redirect('admin:shop_category_changelist')

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('manage-tags/<int:category_id>/', admin.site.admin_view(self.manage_category_tags), name='manage_category_tags'),
            path('add-tags/<int:category_id>/', admin.site.admin_view(self.add_tags_to_category), name='add_tags_to_category'),
            path('remove-tags/<int:category_id>/', admin.site.admin_view(self.remove_tags_from_category), name='remove_tags_from_category'),
            path('bulk-assign-tags/<int:category_id>/', admin.site.admin_view(self.bulk_assign_tags), name='bulk_assign_tags'),
            path('manage-attributes/<int:category_id>/', admin.site.admin_view(self.manage_category_attributes), name='manage_category_attributes'),
        ]
        return custom_urls + urls

    def manage_category_tags(self, request, category_id):
        """Main interface for managing tags within a category"""
        category = get_object_or_404(Category, id=category_id)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'add_tags':
                return self.add_tags_to_category(request, category_id)
            elif action == 'remove_tags':
                return self.remove_tags_from_category(request, category_id)
            elif action == 'bulk_assign':
                return self.bulk_assign_tags(request, category_id)
        
        # Get all available tags
        all_tags = Tag.objects.all().order_by('name')
        
        # Get tags currently assigned to this category
        assigned_tags = category.tags.all()
        
        context = {
            'category': category,
            'all_tags': all_tags,
            'assigned_tags': assigned_tags,
            'title': f'مدیریت برچسب‌ها برای {category.name}',
        }
        
        return render(request, 'admin/shop/category/manage_category_tags.html', context)

    def add_tags_to_category(self, request, category_id):
        """Add selected tags to the category"""
        category = get_object_or_404(Category, id=category_id)
        
        if request.method == 'POST':
            tag_ids = request.POST.getlist('tag_ids')
            tags = Tag.objects.filter(id__in=tag_ids)
            category.tags.add(*tags)
            
            messages.success(request, f'برچسب‌های انتخاب شده به {category.name} اضافه شدند.')
        
        return HttpResponseRedirect(reverse('admin:manage_category_tags', args=[category_id]))

    def remove_tags_from_category(self, request, category_id):
        """Remove selected tags from the category"""
        category = get_object_or_404(Category, id=category_id)
        
        if request.method == 'POST':
            tag_ids = request.POST.getlist('tag_ids')
            tags = Tag.objects.filter(id__in=tag_ids)
            category.tags.remove(*tags)
            
            messages.success(request, f'برچسب‌های انتخاب شده از {category.name} حذف شدند.')
        
        return HttpResponseRedirect(reverse('admin:manage_category_tags', args=[category_id]))

    def bulk_assign_tags(self, request, category_id):
        """Bulk assign tags to all products in this category"""
        category = get_object_or_404(Category, id=category_id)
        
        if request.method == 'POST':
            tag_ids = request.POST.getlist('tag_ids')
            tags = Tag.objects.filter(id__in=tag_ids)
            
            # Get all products in this category (including subcategories)
            products = category.get_all_products()
            
            # Assign tags to all products
            for product in products:
                product.tags.add(*tags)
            
            messages.success(request, f'برچسب‌ها به {products.count()} محصول در دسته‌بندی {category.name} اضافه شدند.')
        
        return HttpResponseRedirect(reverse('admin:manage_category_tags', args=[category_id]))

    def manage_category_attributes(self, request, category_id):
        """Redirect to the manage category attributes page"""
        from django.shortcuts import redirect
        from django.urls import reverse
        
        # Redirect to the existing manage_category_attributes view
        return redirect('shop:manage_category_attributes', category_id=category_id)

class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ('product', 'key', 'value')
    list_filter = ('key',)
    search_fields = ('product__name', 'key', 'value')

class TagAdmin(admin.ModelAdmin):
    form = TagForm
    list_display = ('name', 'slug', 'get_categories')
    search_fields = ('name', 'slug')
    filter_horizontal = ('categories',)
    list_filter = ('categories',)
    
    def save_model(self, request, obj, form, change):
        """
        Override save_model to handle slug generation for Persian text
        """
        if not obj.slug:
            # Use our custom persian_slugify function
            obj.slug = persian_slugify(obj.name)
            # If slug is empty (all Persian chars), create a unique ID
            if not obj.slug:
                import random
                # Generate a random ID based on the name and a random number
                name_hash = hash(obj.name) % 10000
                random_part = random.randint(1000, 9999)
                obj.slug = f"tag-{name_hash}-{random_part}"
        super().save_model(request, obj, form, change)
    
    def get_categories(self, obj):
        return ", ".join([c.name for c in obj.categories.all()])
    get_categories.short_description = 'Categories'

class CategoryTagManagerAdmin(admin.ModelAdmin):
    """Custom admin for managing tags within categories"""
    search_fields = ('name', 'label')
    list_display = ('id', 'name', 'label', 'parent', 'gender', 'get_product_count', 'manage_tags_link')
    list_filter = ('parent', 'category_type', 'gender')
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('manage-tags/<int:category_id>/', admin.site.admin_view(self.manage_category_tags), name='manage_category_tags'),
            path('add-tags/<int:category_id>/', admin.site.admin_view(self.add_tags_to_category), name='add_tags_to_category'),
            path('remove-tags/<int:category_id>/', admin.site.admin_view(self.remove_tags_from_category), name='remove_tags_from_category'),
            path('bulk-assign-tags/<int:category_id>/', admin.site.admin_view(self.bulk_assign_tags), name='bulk_assign_tags'),
        ]
        return custom_urls + urls

    def manage_category_tags(self, request, category_id):
        """Main interface for managing tags within a category"""
        category = get_object_or_404(Category, id=category_id)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'add_tags':
                return self.add_tags_to_category(request, category_id)
            elif action == 'remove_tags':
                return self.remove_tags_from_category(request, category_id)
            elif action == 'bulk_assign':
                return self.bulk_assign_tags(request, category_id)
        
        # Get current tags for this category
        current_tags = category.tags.all().order_by('name')
        
        # Get all available tags
        all_tags = Tag.objects.all().order_by('name')
        
        # Get products in this category with their current tags
        products = Product.objects.filter(category=category, is_active=True).prefetch_related('tags')
        
        context = {
            'category': category,
            'current_tags': current_tags,
            'all_tags': all_tags,
            'products': products,
            'title': f'مدیریت برچسب‌های دسته‌بندی: {category.name}',
            'opts': self.model._meta,
        }
        
        return render(request, 'admin/shop/category/manage_category_tags.html', context)

    def add_tags_to_category(self, request, category_id):
        """Add new tags to a category"""
        category = get_object_or_404(Category, id=category_id)
        
        if request.method == 'POST':
            tag_names = request.POST.get('tag_names', '').strip()
            if tag_names:
                tag_list = [name.strip() for name in tag_names.split(',') if name.strip()]
                
                with transaction.atomic():
                    for tag_name in tag_list:
                        tag, created = Tag.objects.get_or_create(name=tag_name)
                        category.tags.add(tag)
                        
                        if created:
                            messages.success(request, f'برچسب "{tag_name}" ایجاد و به دسته‌بندی اضافه شد')
                        else:
                            messages.info(request, f'برچسب "{tag_name}" به دسته‌بندی اضافه شد')
                
                return HttpResponseRedirect(reverse('admin:manage_category_tags', args=[category_id]))
        
        return HttpResponseRedirect(reverse('admin:manage_category_tags', args=[category_id]))

    def remove_tags_from_category(self, request, category_id):
        """Remove tags from a category"""
        category = get_object_or_404(Category, id=category_id)
        
        if request.method == 'POST':
            tag_ids = request.POST.getlist('tag_ids')
            if tag_ids:
                tags_to_remove = Tag.objects.filter(id__in=tag_ids)
                tag_names = [tag.name for tag in tags_to_remove]
                
                with transaction.atomic():
                    category.tags.remove(*tags_to_remove)
                
                messages.success(request, f'برچسب‌های {", ".join(tag_names)} از دسته‌بندی حذف شدند')
        
        return HttpResponseRedirect(reverse('admin:manage_category_tags', args=[category_id]))

    def bulk_assign_tags(self, request, category_id):
        """Bulk assign tags to products in a category"""
        category = get_object_or_404(Category, id=category_id)
        
        if request.method == 'POST':
            product_ids = request.POST.getlist('product_ids')
            tag_ids = request.POST.getlist('tag_ids')
            
            if product_ids and tag_ids:
                products = Product.objects.filter(id__in=product_ids, category=category)
                tags = Tag.objects.filter(id__in=tag_ids)
                
                with transaction.atomic():
                    for product in products:
                        product.tags.add(*tags)
                
                messages.success(request, f'برچسب‌ها به {products.count()} محصول اضافه شدند')
        
        return HttpResponseRedirect(reverse('admin:manage_category_tags', args=[category_id]))

    def get_actions(self, request):
        """Remove default actions and add custom ones"""
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def get_product_count(self, obj):
        """Show total product count for this category"""
        count = obj.get_product_count()
        return count if count > 0 else '-'
    get_product_count.short_description = 'تعداد محصولات'

    def manage_tags_link(self, obj):
        """Create a link to manage tags for this category"""
        from django.utils.html import format_html
        from django.urls import reverse
        
        tag_count = obj.tags.count()
        url = reverse('admin:manage_category_tags', args=[obj.id])
        
        if tag_count > 0:
            return format_html(
                '<a href="{}" class="button" style="background: #007bff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 12px;">مدیریت برچسب‌ها ({})</a>',
                url, tag_count
            )
        else:
            return format_html(
                '<a href="{}" class="button" style="background: #6c757d; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-size: 12px;">مدیریت برچسب‌ها</a>',
                url
            )
    manage_tags_link.short_description = 'مدیریت برچسب‌ها'

    def changelist_view(self, request, extra_context=None):
        """Override to show category list with tag management options"""
        extra_context = extra_context or {}
        extra_context['show_tag_manager'] = True
        return super().changelist_view(request, extra_context)

class ProductAdmin(admin.ModelAdmin):
    class Media:
        js = ('shop/js/product_detail_sidebar.js', 'shop/js/product_tags.js')
        css = {
            'all': ('shop/css/product_detail_sidebar.css',)
        }

    list_display = ('product_id_display', 'name', 'price_toman', 'price_usd', 'category', 'product_tags_display', 'image_count_display', 'variants_count_display', 'is_active', 'is_new_arrival')
    list_filter = ('category', 'is_active', 'is_new_arrival', 'tags', 'created_at')
    search_fields = ('id', 'name', 'description')
    readonly_fields = ['created_at']
    inlines = [ProductImageInlineAdmin, ProductVariantInline]
    form = ProductForm
    change_form_template = 'admin/shop/product/change_form.html'
    
    def get_inline_instances(self, request, obj=None):
        """Ensure inlines are properly instantiated"""
        return super().get_inline_instances(request, obj)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add variant information"""
        extra_context = extra_context or {}
        
        # Get the product
        product = self.get_object(request, object_id)
        if product:
            # Get variants for this product
            variants = ProductVariant.objects.filter(product=product)
            extra_context['product_variants'] = variants
            extra_context['variants_count'] = variants.count()
        
        return super().change_view(request, object_id, form_url, extra_context)

    delete_confirmation_template = 'admin/shop/product/delete_confirmation.html'
    filter_horizontal = ('tags',)
    autocomplete_fields = ['category']
    


    def get_available_attributes_count(self, obj):
        """Show how many attributes are available for this product's category"""
        if obj.category and obj.category.is_subcategory():
            return obj.get_available_attributes().count()
        return 0
    get_available_attributes_count.short_description = 'ویژگی‌های قابل استفاده'

    def product_id_display(self, obj):
        """Display product ID with custom formatting"""
        from django.utils.html import format_html
        return format_html('<strong style="color: #007bff; font-size: 14px;">{}</strong>', obj.id)
    product_id_display.short_description = 'شناسه محصول'
    product_id_display.admin_order_field = 'id'

    def product_tags_display(self, obj):
        """Display product tags in a readable format"""
        from django.utils.html import format_html
        tags = obj.tags.all()
        if tags:
            tag_list = [f'<span style="background: #e9ecef; padding: 2px 6px; border-radius: 3px; margin: 1px; font-size: 11px;">{tag.name}</span>' for tag in tags]
            return format_html(' '.join(tag_list))
        return format_html('<span style="color: #6c757d; font-style: italic;">بدون برچسب</span>')
    product_tags_display.short_description = 'برچسب‌ها'

    def image_count_display(self, obj):
        """Display the number of images for the product"""
        from django.utils.html import format_html
        count = obj.images.count()
        if count > 0:
            return format_html('<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>', count)
        return format_html('<span style="background: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">0</span>')
    image_count_display.short_description = 'تصاویر'

    def variants_count_display(self, obj):
        """Display the number of variants for the product"""
        from django.utils.html import format_html
        count = obj.variants.count()
        if count > 0:
            return format_html('<span style="background: #17a2b8; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{} نوع</span>', count)
        return format_html('<span style="background: #6c757d; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">بدون نوع</span>')
    variants_count_display.short_description = 'انواع محصول'

    def response_delete(self, request, obj_display, obj_id):
        """Override to redirect to custom admin products page after deletion"""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        
        # Redirect to custom admin products page
        return HttpResponseRedirect(reverse('shop:admin_products_explorer'))

    def delete_model(self, request, obj):
        """Override to set the current user before deletion"""
        obj._current_user = request.user
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Override to set the current user before bulk deletion"""
        for obj in queryset:
            obj._current_user = request.user
        super().delete_queryset(request, queryset)

    # Removed custom_edit_link method to use standard Django admin editing

    def response_change(self, request, obj):
        """Override to handle successful product changes"""
        # Use the default Django admin behavior
        return super().response_change(request, obj)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to redirect to suppliers add-product page"""
        from django.shortcuts import redirect
        from django.urls import reverse
        
        # Redirect to suppliers add-product page with product_id parameter
        return redirect(reverse('suppliers:add_product') + f'?product_id={object_id}')

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if isinstance(list_display, (list, tuple)):
            list_display = list(list_display)
            if 'quick_edit' in list_display:
                list_display.remove('quick_edit')
        return list_display

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'quick_edit' in actions:
            del actions['quick_edit']
        return actions

    def get_urls(self):
        urls = super().get_urls()
        # Filter out any quick edit related URLs
        urls = [url for url in urls if 'quick-edit' not in str(url.pattern)]
        return urls

    def get_change_view_url(self, obj):
        """Override to redirect to suppliers add-product page instead of admin change form"""
        from django.urls import reverse
        return reverse('suppliers:add_product') + f'?product_id={obj.id}'

    def display_supplier(self, obj):
        if obj.supplier:
            return obj.supplier.name
        return format_html('Unknown Supplier <span style="color: red; font-weight: bold;">[Deleted]</span>')
    display_supplier.short_description = 'تامین‌کننده'
    display_supplier.admin_order_field = 'supplier__name'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if isinstance(request.user, SupplierUser) and SupplierAdmin.objects.filter(user=request.user, is_active=True).exists():
            supplier_admin = SupplierAdmin.objects.get(user=request.user)
            return qs.filter(supplier=supplier_admin.supplier)
        elif not isinstance(request.user, SupplierUser):
            import logging
            logging.warning(f"[ProductAdmin] request.user is not a SupplierUser instance: {request.user} ({type(request.user)})")
        return qs

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if isinstance(request.user, SupplierUser) and SupplierAdmin.objects.filter(user=request.user, is_active=True).exists():
            supplier_admin = SupplierAdmin.objects.get(user=request.user)
            if 'supplier' in form.base_fields:
                form.base_fields['supplier'].initial = supplier_admin.supplier
                form.base_fields['supplier'].disabled = True
        elif not isinstance(request.user, SupplierUser):
            import logging
            logging.warning(f"[ProductAdmin] request.user is not a SupplierUser instance: {request.user} ({type(request.user)})")
        return form

    def save_model(self, request, obj, form, change):
        if not obj.supplier and isinstance(request.user, SupplierUser) and SupplierAdmin.objects.filter(user=request.user, is_active=True).exists():
            supplier_admin = SupplierAdmin.objects.get(user=request.user)
            obj.supplier = supplier_admin.supplier
        elif not isinstance(request.user, SupplierUser):
            import logging
            logging.warning(f"[ProductAdmin] request.user is not a SupplierUser instance: {request.user} ({type(request.user)})")
        super().save_model(request, obj, form, change)
            
        # Remove existing legacy attributes on edit
        if change:
            obj.legacy_attribute_set.all().delete()

        # Save only submitted and non-empty legacy attributes
        for key, value in request.POST.items():
            if key.startswith('attr_') and value.strip():
                attr_key = key.replace('attr_', '')
                
                # Check if this is a flexible attribute
                if obj.category and obj.category.is_subcategory():
                    try:
                        # Try to find the attribute in the flexible system
                        attribute = Attribute.objects.get(key=attr_key)
                        # This is a flexible attribute, save it properly
                        obj.set_attribute_value(attr_key, value)
                        continue
                    except Attribute.DoesNotExist:
                        pass
                
                # Fall back to legacy system
                ProductAttribute.objects.create(
                    product=obj,
                    key=attr_key,
                    value=value
                )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        images = request.FILES.getlist('images')
        for i, image in enumerate(images):
            ProductImage.create(
                product=form.instance,
                image=image,
                order=i  # Set the order based on the index
            )


    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['is_add_view'] = True
        return super().add_view(request, form_url, extra_context=extra_context)

    def changelist_view(self, request, extra_context=None):
        # Get all suppliers for the dropdown
        from suppliers.models import Supplier
        suppliers = Supplier.objects.all().order_by('name')
        
        # Get selected supplier if any
        selected_supplier = request.GET.get('supplier', '')
        
        # Add to context
        extra_context = extra_context or {}
        extra_context.update({
            'suppliers': suppliers,
            'selected_supplier': selected_supplier,
        })
        
        # Apply supplier filter directly to the request
        if selected_supplier:
            # Store the original queryset method
            original_get_queryset = self.get_queryset
            
            # Define a new method that will filter by supplier
            def filtered_queryset(request):
                return original_get_queryset(request).filter(supplier_id=selected_supplier)
                
            # Temporarily replace the get_queryset method
            # Have to use types.MethodType to properly bind the method to the instance
            import types
            self.get_queryset = types.MethodType(lambda self, request: filtered_queryset(request), self)
            
            # Call parent changelist_view
            response = super().changelist_view(request, extra_context=extra_context)
            
            # Restore the original method
            self.get_queryset = original_get_queryset
            
            return response
        else:
            # No supplier filter, just call parent method
            return super().changelist_view(request, extra_context=extra_context)

    def get_brand_image(self, obj):
        if obj.brand_image:
            return mark_safe(f'<img src="{obj.brand_image.url}" width="50" height="50" />')
        return "No image"
    get_brand_image.short_description = 'تصویر برند'

    def mark_as_new_arrival(self, request, queryset):
        """Admin action to mark selected products as new arrivals"""
        updated = queryset.update(is_new_arrival=True)
        self.message_user(request, f'{updated} محصول به عنوان "محصول جدید" علامت‌گذاری شد.')
    mark_as_new_arrival.short_description = 'علامت‌گذاری به عنوان محصول جدید'

    def unmark_as_new_arrival(self, request, queryset):
        """Admin action to remove new arrival status from selected products"""
        updated = queryset.update(is_new_arrival=False)
        self.message_user(request, f'علامت "محصول جدید" از {updated} محصول حذف شد.')
    unmark_as_new_arrival.short_description = 'حذف علامت محصول جدید'

    actions = ['mark_as_new_arrival', 'unmark_as_new_arrival']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'description', 'category', 'tags', 'is_active', 'is_new_arrival')
        }),
        ('قیمت‌گذاری', {
            'fields': ('price_toman', 'price_usd', 'price', 'price_currency')
        }),
        ('اطلاعات فنی', {
            'fields': ('weight', 'dimensions', 'warranty', 'stock_quantity')
        }),
        ('اطلاعات تکمیلی', {
            'fields': ('supplier', 'created_at')
        }),
    )

class ProductVariantAdmin(admin.ModelAdmin):
    """Admin interface for ProductVariant model"""
    list_display = ['product', 'product_id_display', 'sku', 'color_display', 'size_display', 'price_toman', 'stock_quantity', 'images_count_display', 'is_active', 'is_default', 'isDistinctive', 'created_at']
    list_filter = ['is_active', 'is_default', 'isDistinctive', 'created_at', 'product__category']
    search_fields = ['sku', 'product__name']
    list_editable = ['price_toman', 'stock_quantity', 'is_active', 'is_default', 'isDistinctive']
    inlines = [ProductVariantImageInline]
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('product', 'sku', 'is_active')
        }),
        ('تنظیمات نمایش', {
            'fields': ('is_default', 'isDistinctive'),
            'description': 'تنظیمات حالت نمایش نوع محصول'
        }),
        ('ویژگی‌ها', {
            'fields': ('attributes',),
            'description': 'JSON format: {"color": "قرمز", "size": "M", "material": "پنبه"}'
        }),
        ('قیمت و موجودی', {
            'fields': ('price_toman', 'stock_quantity')
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at']
    
    def product_id_display(self, obj):
        """Display product ID with link to product edit page"""
        if obj.product:
            url = reverse('admin:shop_product_change', args=[obj.product.id])
            return format_html('<a href="{}" target="_blank">#{}</a>', url, obj.product.id)
        return '-'
    product_id_display.short_description = 'Product ID'
    product_id_display.admin_order_field = 'product__id'
    
    def color_display(self, obj):
        """Display color from attributes"""
        color = obj.attributes.get('color', 'نامشخص')
        if color != 'نامشخص':
            return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>', 
                             self._get_color_code(color), color)
        return color
    color_display.short_description = 'رنگ'
    
    def size_display(self, obj):
        """Display size from attributes"""
        return obj.attributes.get('size', 'نامشخص')
    size_display.short_description = 'سایز'
    
    def images_count_display(self, obj):
        """Display count of variant images"""
        count = obj.images.count()
        if count == 0:
            return format_html('<span style="color: #999;">No images</span>')
        elif count == 1:
            return format_html('<span style="color: #28a745;">1 image</span>')
        else:
            return format_html('<span style="color: #007bff;">{} images</span>', count)
    images_count_display.short_description = 'Images'
    images_count_display.admin_order_field = 'images__count'
    
    def _get_color_code(self, color):
        """Get hex color code for common colors"""
        color_map = {
            'قرمز': '#dc3545',
            'آبی': '#007bff', 
            'سبز': '#28a745',
            'زرد': '#ffc107',
            'سیاه': '#343a40',
            'سفید': '#6c757d',
            'صورتی': '#e83e8c',
            'نارنجی': '#fd7e14',
            'بنفش': '#6f42c1',
            'قهوه‌ای': '#795548'
        }
        return color_map.get(color, '#6c757d')

class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'image', 'is_primary', 'order', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['product__name']
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'order' in form.base_fields:
            form.base_fields['order'].help_text = 'شماره ترتیب باید بین 1 تا 10 باشد'
            form.base_fields['order'].validators.append(
                lambda value: ValidationError('شماره ترتیب نمی‌تواند بیشتر از 10 باشد') if value > 10 else None
            )
        return form

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0
    fields = ['product', 'price', 'quantity', 'get_total']
    readonly_fields = ['get_total']
    
    def get_total(self, obj):
        if obj.pk:
            return f"{float(obj.get_cost()):,.0f} تومان"
        return "-"
    get_total.short_description = 'Total'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'first_name', 'last_name', 'email',
                   'address', 'postal_code', 'city', 'paid',
                   'get_total_cost_display', 'created', 'updated']
    list_filter = ['paid', 'created', 'updated']
    inlines = [OrderItemInline]
    search_fields = ['first_name', 'last_name', 'email']
    
    def get_total_cost_display(self, obj):
        if obj.pk:
            return f"{float(obj.get_total_cost()):,.0f} تومان"
        return "-"
    get_total_cost_display.short_description = 'Total Cost'


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'price', 'quantity', 'get_total']
    list_filter = ['order', 'order__paid', 'order__created']
    search_fields = ['product__name', 'order__email', 'order__first_name', 'order__last_name']
    raw_id_fields = ['order', 'product']
    readonly_fields = ['get_total']
    
    def get_total(self, obj):
        if obj.pk:
            return f"{float(obj.get_cost()):,.0f} تومان"
        return "-"
    get_total.short_description = 'Total'

# Register OrderItem
admin.site.register(OrderItem, OrderItemAdmin)

# Move these admin classes up before any registration calls:
class AttributeValueInlineForCategory(admin.TabularInline):
    model = AttributeValue
    extra = 1
    fields = ['value', 'display_order']
    ordering = ['display_order', 'value']

class CategoryAttributeAdmin(admin.ModelAdmin):
    list_display = ('category', 'key', 'label_fa', 'type', 'required', 'is_displayed_in_product', 'display_in_basket', 'display_order', 'manage_values_link')
    list_filter = ('category', 'type', 'required', 'is_displayed_in_product', 'display_in_basket')
    search_fields = ('key', 'label_fa', 'category__name')
    ordering = ('category', 'display_order', 'key')
    inlines = [AttributeValueInlineForCategory]
    fields = ('category', 'key', 'label_fa', 'type', 'required', 'is_displayed_in_product', 'display_in_basket', 'display_order')
    actions = ['manage_values_action']
    
    def manage_values_link(self, obj):
        """Create a link to manage attribute values"""
        if obj.pk:
            url = reverse('shop:manage_attribute_values', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" target="_blank" style="background: #28a745; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none;">'
                '🔧 مدیریت مقادیر</a>',
                url
            )
        return '-'
    manage_values_link.short_description = 'مدیریت مقادیر'
    manage_values_link.allow_tags = True
    
    def manage_values_action(self, request, queryset):
        """Admin action to manage values for selected attributes"""
        if len(queryset) == 1:
            # If only one attribute is selected, redirect to its values page
            attribute = queryset.first()
            url = reverse('shop:manage_attribute_values', args=[attribute.pk])
            return HttpResponseRedirect(url)
        else:
            # If multiple attributes are selected, show a message
            self.message_user(
                request, 
                'لطفاً فقط یک ویژگی را انتخاب کنید تا مقادیر آن را مدیریت کنید.',
                level=messages.WARNING
            )
    manage_values_action.short_description = 'مدیریت مقادیر ویژگی انتخاب شده'
    
    def get_queryset(self, request):
        """Add custom method to get queryset with related data"""
        return super().get_queryset(request).select_related('category')
    
    def get_list_display(self, request):
        """Customize list display based on user permissions"""
        list_display = list(super().get_list_display(request))
        if request.user.is_superuser:
            # Add additional columns for superusers
            if 'values_count' not in list_display:
                list_display.append('values_count')
        return list_display
    
    def values_count(self, obj):
        """Show count of values for this attribute"""
        count = obj.values.count()
        if count > 0:
            url = reverse('shop:manage_attribute_values', args=[obj.pk])
            return format_html(
                '<a href="{}" target="_blank" style="color: #007bff; text-decoration: none;">'
                '{} مقدار</a>',
                url, count
            )
        return '0 مقدار'
    values_count.short_description = 'تعداد مقادیر'
    values_count.admin_order_field = 'values__count'

class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ('attribute', 'value', 'display_order')
    list_filter = ('attribute',)
    search_fields = ('value', 'attribute__key')
    ordering = ['attribute__key', 'display_order']
    list_editable = ('display_order',)


class DeletedProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'original_id', 'category_name', 'supplier_name', 'deleted_at', 'deleted_by')
    list_filter = ('deleted_at', 'category_name', 'supplier_name')
    search_fields = ('name', 'original_id')
    readonly_fields = ('original_id', 'name', 'price_toman', 'price_usd', 'description', 
                      'category_name', 'supplier_name', 'sku', 'deleted_at')
    ordering = ['-deleted_at']
    
    def has_add_permission(self, request):
        return False  # Don't allow manual creation of deleted product records


class WishlistAdmin(admin.ModelAdmin):
    list_display = ('customer', 'product', 'created_at')
    list_filter = ('created_at', 'product__category')
    search_fields = ('customer__email', 'customer__first_name', 'customer__last_name', 'product__name')
    readonly_fields = ('created_at',)
    ordering = ['-created_at']
    
    def get_customer_display(self, obj):
        return obj.customer.get_full_name() or obj.customer.email
    get_customer_display.short_description = 'مشتری'
    get_customer_display.admin_order_field = 'customer__first_name'


# Admin classes for new improved category system
class CategoryGenderAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'display_name')
    ordering = ('display_order', 'name')
    list_editable = ('display_order', 'is_active')
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'display_name')
        }),
        ('تنظیمات', {
            'fields': ('is_active', 'display_order')
        }),
    )


class CategorySubgroupInline(admin.TabularInline):
    model = CategorySubgroup
    extra = 1
    fields = ('name', 'label', 'is_active', 'display_order')
    ordering = ('display_order', 'name')


class CategoryGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'label', 'supports_gender', 'is_active', 'display_order', 'get_product_count')
    list_filter = ('supports_gender', 'is_active')
    search_fields = ('name', 'label', 'description')
    ordering = ('display_order', 'name')
    list_editable = ('display_order', 'is_active', 'supports_gender')
    inlines = [CategorySubgroupInline]
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'label', 'description')
        }),
        ('تنظیمات', {
            'fields': ('icon', 'supports_gender', 'is_active', 'display_order')
        }),
    )
    
    def get_product_count(self, obj):
        """Show total product count for this group"""
        count = obj.get_product_count()
        return count if count > 0 else '-'
    get_product_count.short_description = 'تعداد محصولات'


class CategorySubgroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'parent', 'is_active', 'display_order', 'get_product_count')
    list_filter = ('group', 'parent', 'is_active')
    search_fields = ('name', 'label', 'group__name')
    ordering = ('group__name', 'display_order', 'name')
    list_editable = ('display_order', 'is_active')
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'label', 'group')
        }),
        ('سلسله مراتب', {
            'fields': ('parent',)
        }),
        ('تنظیمات', {
            'fields': ('is_active', 'display_order')
        }),
    )
    
    def get_product_count(self, obj):
        """Show total product count for this subgroup"""
        count = obj.get_product_count()
        return count if count > 0 else '-'
    get_product_count.short_description = 'تعداد محصولات'


# Registrations moved to myshop.admin to avoid circular import

# Also register with default admin site
admin.site.register(Category, CategoryAdmin)
admin.site.register(ProductAttribute, ProductAttributeAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(ProductImage, ProductImageAdmin)
class ProductVariantImageAdmin(admin.ModelAdmin):
    """Admin interface for ProductVariantImage model"""
    list_display = ['variant', 'variant_sku_display', 'image_preview', 'is_primary', 'order', 'created_at']
    list_filter = ['is_primary', 'created_at', 'variant__product']
    search_fields = ['variant__sku', 'variant__product__name']
    list_editable = ['is_primary', 'order']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('variant', 'image', 'is_primary', 'order')
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at']
    
    def variant_sku_display(self, obj):
        """Display variant SKU with link to variant edit page"""
        if obj.variant:
            url = reverse('admin:shop_productvariant_change', args=[obj.variant.id])
            return format_html('<a href="{}" target="_blank">{}</a>', url, obj.variant.sku)
        return '-'
    variant_sku_display.short_description = 'SKU'
    variant_sku_display.admin_order_field = 'variant__sku'
    
    def image_preview(self, obj):
        """Display image preview"""
        if obj.image:
            return format_html('<img src="{}" style="max-width: 50px; max-height: 50px; border-radius: 4px;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'تصویر'

admin.site.register(ProductVariant, ProductVariantAdmin)
admin.site.register(ProductVariantImage, ProductVariantImageAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Wishlist, WishlistAdmin)

# New flexible attribute system models on default admin
admin.site.register(Attribute, AttributeAdmin)
admin.site.register(NewAttributeValue, NewAttributeValueAdmin)
admin.site.register(CategoryAttribute, CategoryAttributeAdmin)
admin.site.register(AttributeValue, AttributeValueAdmin)
admin.site.register(DeletedProduct, DeletedProductAdmin)

# New improved category system models on default admin
admin.site.register(CategoryGender, CategoryGenderAdmin)
admin.site.register(CategoryGroup, CategoryGroupAdmin)
admin.site.register(CategorySubgroup, CategorySubgroupAdmin)

# Custom admin site registrations moved to myshop.admin to avoid circular import

@admin.register(SpecialOffer)
class SpecialOfferAdmin(admin.ModelAdmin):
    """Admin interface for SpecialOffer model"""
    list_display = [
        'title', 'offer_type', 'display_style', 'enabled', 'is_active', 
        'valid_from', 'valid_until', 'display_order', 'views_count', 'clicks_count'
    ]
    list_filter = [
        'offer_type', 'display_style', 'enabled', 'is_active', 
        'valid_from', 'valid_until'
    ]
    search_fields = ['title', 'description']
    list_editable = ['enabled', 'is_active', 'display_order']
    readonly_fields = ['views_count', 'clicks_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'offer_type', 'display_style')
        }),
        ('Banner Settings', {
            'fields': ('banner_image', 'banner_action_type', 'banner_action_target', 'banner_external_url')
        }),
        ('Timing', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Status', {
            'fields': ('enabled', 'is_active', 'display_order')
        }),
        ('Analytics', {
            'fields': ('views_count', 'clicks_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with related fields - handle decimal errors gracefully"""
        try:
            return super().get_queryset(request).prefetch_related('products')
        except Exception as e:
            # If prefetch fails due to decimal issues, fall back to basic queryset
            print(f"Warning: Prefetch failed due to decimal conversion error: {e}")
            return super().get_queryset(request)
    
    def delete_view(self, request, object_id, extra_context=None):
        """Override delete view to handle decimal conversion errors"""
        try:
            return super().delete_view(request, object_id, extra_context)
        except Exception as e:
            from django.contrib import messages
            from django.shortcuts import redirect
            from django.db import connection
            
            if 'InvalidOperation' in str(e) or 'decimal' in str(e).lower():
                try:
                    # Try to delete using raw SQL to avoid decimal conversion issues
                    with connection.cursor() as cursor:
                        # Get offer title first
                        cursor.execute("SELECT title FROM shop_specialoffer WHERE id = %s", [object_id])
                        result = cursor.fetchone()
                        offer_title = result[0] if result else f"Offer {object_id}"
                        
                        # Delete related products first
                        cursor.execute("DELETE FROM shop_specialofferproduct WHERE offer_id = %s", [object_id])
                        
                        # Delete the offer
                        cursor.execute("DELETE FROM shop_specialoffer WHERE id = %s", [object_id])
                    
                    messages.success(request, f'پیشنهاد ویژه "{offer_title}" با موفقیت حذف شد.')
                    return redirect('admin:shop_specialoffer_changelist')
                    
                except Exception as delete_error:
                    messages.error(request, f'خطا در حذف پیشنهاد ویژه: {str(delete_error)}')
                    return redirect('admin:shop_specialoffer_changelist')
            else:
                raise e


@admin.register(SpecialOfferProduct)
class SpecialOfferProductAdmin(admin.ModelAdmin):
    """Admin interface for SpecialOfferProduct model"""
    list_display = [
        'offer', 'product', 'is_active', 'display_order'
    ]
    
    class Media:
        js = ('admin/js/special_offer_product.js',)
    

    
    def safe_original_price(self, obj):
        """Safely display original price"""
        try:
            return f"{float(obj.original_price):.2f}" if obj.original_price else "0.00"
        except (ValueError, TypeError):
            return "خطا"
    safe_original_price.short_description = 'قیمت اصلی'
    
    def safe_discounted_price(self, obj):
        """Safely display discounted price"""
        try:
            return f"{float(obj.discounted_price):.2f}" if obj.discounted_price else "محاسبه نشده"
        except (ValueError, TypeError):
            return "خطا"
    safe_discounted_price.short_description = 'قیمت با تخفیف'
    
    def get_queryset(self, request):
        """Handle decimal conversion errors in queryset"""
        try:
            return super().get_queryset(request).select_related('offer', 'product')
        except Exception as e:
            print(f"Warning: Queryset failed due to decimal conversion error: {e}")
            return super().get_queryset(request)
    list_filter = ['offer', 'is_active', 'discount_percentage']
    search_fields = ['product__name', 'offer__title']
    list_editable = ['is_active', 'display_order']
    readonly_fields = ['created_at', 'discounted_price']
    
    def get_readonly_fields(self, request, obj=None):
        """Ensure discounted_price is always readonly"""
        readonly = list(self.readonly_fields)
        if 'discounted_price' not in readonly:
            readonly.append('discounted_price')
        return readonly
        
    def discounted_price_display(self, obj):
        """Custom display for discounted price with styling"""
        if obj.discounted_price:
            return f"{float(obj.discounted_price):.2f} تومان"
        return "محاسبه نشده"
    discounted_price_display.short_description = 'قیمت با تخفیف (تومان)'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('offer', 'product')
        }),
        ('Discount Settings', {
            'fields': ('discount_percentage', 'original_price', 'discounted_price'),
            'description': '🧮 درصد تخفیف را وارد کنید. قیمت با تخفیف به طور خودکار محاسبه خواهد شد و قابل ویرایش نیست.'
        }),
        ('Display', {
            'fields': ('is_active', 'display_order')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Auto-calculate discounted price if not set"""
        if not obj.original_price and obj.product:
            obj.original_price = obj.product.price_toman
        super().save_model(request, obj, form, change)


# Cart Admin
class CartItemInline(admin.TabularInline):
    """Inline for CartItems in CartAdmin"""
    model = CartItem
    extra = 0
    fields = ['product', 'variant', 'quantity', 'unit_price', 'get_total_price']
    readonly_fields = ['get_total_price']
    raw_id_fields = ['product', 'variant']
    
    def get_total_price(self, obj):
        if obj.pk:
            try:
                return f"{float(obj.get_total_price()):,.0f} تومان"
            except:
                return "-"
        return "-"
    get_total_price.short_description = 'Total'


class CartAdmin(admin.ModelAdmin):
    """Admin interface for Cart model"""
    list_display = [
        'id', 'get_customer_display', 'get_session_key_display', 
        'get_total_items', 'get_total_price_display', 
        'created_at', 'updated_at'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['customer__email', 'customer__first_name', 'customer__last_name', 'session_key']
    readonly_fields = ['created_at', 'updated_at', 'get_total_items', 'get_total_price_display']
    inlines = [CartItemInline]
    ordering = ['-updated_at']
    
    fieldsets = (
        ('اطلاعات سبد خرید', {
            'fields': ('customer', 'session_key')
        }),
        ('خلاصه', {
            'fields': ('get_total_items', 'get_total_price_display'),
            'classes': ('collapse',)
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_customer_display(self, obj):
        """Display customer info or Guest"""
        try:
            if obj.customer:
                customer_name = getattr(obj.customer, 'email', None) or f"{getattr(obj.customer, 'first_name', '')} {getattr(obj.customer, 'last_name', '')}".strip() or 'Customer'
                customer_id = getattr(obj.customer, 'id', None)
                if customer_id:
                    return format_html(
                        '<a href="/admin/accounts/customer/{}/change/">{}</a>',
                        customer_id,
                        customer_name
                    )
                return customer_name
            return format_html('<span style="color: #999;">Guest User</span>')
        except Exception as e:
            return f"Error: {str(e)}"
    get_customer_display.short_description = 'مشتری'
    get_customer_display.admin_order_field = 'customer__email'
    
    def get_session_key_display(self, obj):
        """Display session key (device ID) for guest users"""
        if obj.session_key:
            return format_html(
                '<code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</code>',
                obj.session_key[:20] + '...' if len(obj.session_key) > 20 else obj.session_key
            )
        return '-'
    get_session_key_display.short_description = 'Device ID / Session Key'
    
    def get_total_items(self, obj):
        """Display total number of items"""
        return obj.get_total_items()
    get_total_items.short_description = 'تعداد آیتم‌ها'
    
    def get_total_price_display(self, obj):
        """Display total price"""
        try:
            total = obj.get_total_price()
            return f"{float(total):,.0f} تومان"
        except:
            return "0 تومان"
    get_total_price_display.short_description = 'جمع کل'


class CartItemAdmin(admin.ModelAdmin):
    """Admin interface for CartItem model"""
    list_display = [
        'id', 'cart', 'product', 'variant', 'quantity', 
        'unit_price', 'get_total_price', 'created_at'
    ]
    list_filter = ['created_at', 'cart__customer', 'product__category']
    search_fields = ['product__name', 'cart__customer__email', 'cart__session_key']
    raw_id_fields = ['cart', 'product', 'variant']
    readonly_fields = ['created_at', 'updated_at', 'get_total_price']
    
    def get_total_price(self, obj):
        if obj.pk:
            try:
                return f"{float(obj.get_total_price()):,.0f} تومان"
            except:
                return "-"
        return "-"
    get_total_price.short_description = 'Total Price'


# Register Cart and CartItem (must be after class definitions)
admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem, CartItemAdmin)
