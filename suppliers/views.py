import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View, ListView, DetailView
from django.db.models import Q, Max, Sum
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse, HttpResponseServerError
from django.contrib import admin
from django.contrib.admin.helpers import AdminForm
from django.contrib.admin.options import get_ul_class
from django.contrib.admin.utils import flatten_fieldsets
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.core.exceptions import PermissionDenied
from functools import wraps
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from .models import BackupLog, Supplier, SupplierInvitation, SupplierAdmin, Store
from shop.models import Product, Category, ProductImage, ProductAttribute, OrderItem, Order, Tag, CategoryAttribute
from shop.forms import ProductForm
from django.db import transaction
from .forms import SupplierRegistrationForm, SupplierLoginForm

def supplier_landing(request):
    """Supplier landing page"""
    return render(request, 'suppliers/landing.html')

# Test view for simple product saving
def test_save_product(request):
    """Simple test view for product saving functionality"""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            price_toman = request.POST.get('price_toman')
            stock_quantity = request.POST.get('stock_quantity')
            category_id = request.POST.get('category')
            brand = request.POST.get('brand', '')
            is_active = request.POST.get('is_active') == 'on'
            
            # Validate required fields
            if not all([name, price_toman, stock_quantity, category_id]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields'
                })
            
            # Create product
            product = Product.objects.create(
                name=name,
                description=description,
                price_toman=int(price_toman),
                stock_quantity=int(stock_quantity),
                category_id=int(category_id),
                brand=brand,
                is_active=is_active,
                supplier_id=1  # Default supplier for testing
            )
            
            # Handle brand image if uploaded
            if 'brand_image' in request.FILES:
                brand_image = request.FILES['brand_image']
                # Save brand image logic here if needed
            
            return JsonResponse({
                'success': True,
                'message': f'Product "{product.name}" saved successfully!',
                'product_id': product.id,
                'redirect_url': '/suppliers/test-save-product/'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error saving product: {str(e)}'
            })
    
    # GET request - show form
    return render(request, 'suppliers/test_save_product.html')

# --- Helpers for robust Persian attribute handling ---
def _normalize_persian_key(text: str) -> str:
    """Normalize attribute keys to handle Persian ZWNJ and whitespace variants."""
    if not isinstance(text, str):
        return text
    # Remove zero-width joiner characters
    text = text.replace('\u200c', '').replace('\u200d', '')
    # Collapse whitespace and trim
    text = ' '.join(text.split()).strip()
    return text

def _build_normalized_attr_map(post_data) -> dict:
    """Build a map of normalized attribute key -> value(s) from POST data."""
    normalized = {}
    # Gather values (always as list for consistency)
    for key in post_data.keys():
        if key.startswith('attr_'):
            raw_key = key[len('attr_'):]
            norm_key = _normalize_persian_key(raw_key)
            values = post_data.getlist(key)
            normalized[norm_key] = values
    return normalized

# Get the custom user model
User = get_user_model()

# Custom login required decorator that allows superusers to bypass the login check
def supplier_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Superusers can access any supplier page
        if request.user.is_authenticated and request.user.is_superuser:
            return view_func(request, *args, **kwargs)
            
        # Use Django's login_required for regular users
        if not request.user.is_authenticated:
            # Redirect to supplier login rather than Django's default login
            return redirect('suppliers:login')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def supplier_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('suppliers:login')
        
        # Allow superusers to access all supplier pages
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
            
        # Check if user is a supplier admin or has supplier access
        try:
            SupplierAdmin.objects.get(user=request.user)
        except SupplierAdmin.DoesNotExist:
            # If no SupplierAdmin record, check if user has a supplier by email
            try:
                Supplier.objects.get(email=request.user.email)
            except Supplier.DoesNotExist:
                raise PermissionDenied(_("You don't have permission to access this page."))
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Custom mixin for class-based views
class SupplierLoginRequiredMixin:
    """
    CBV mixin that ensures superusers can access supplier pages without redirection
    """
    def dispatch(self, request, *args, **kwargs):
        # Allow superusers to access all supplier pages
        if request.user.is_authenticated and request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
            
        # Regular users need to be logged in
        if not request.user.is_authenticated:
            return redirect('suppliers:login')
            
        return super().dispatch(request, *args, **kwargs)

def register_with_token(request, token):
    try:
        invitation = SupplierInvitation.objects.get(token=token)
        if not invitation.is_valid():
            messages.error(request, "This invitation link is invalid or has expired.")
            return redirect('admin:index')

        if request.method == 'POST':
            form = SupplierRegistrationForm(request.POST)
            if form.is_valid():
                # Create the user
                user = form.save(commit=False)
                user.email = invitation.email
                user.username = form.cleaned_data['username']
                # Use the separate first and last name fields from invitation
                user.first_name = invitation.owner_first_name or ''
                user.last_name = invitation.owner_last_name or ''
                user.save()
                
                # Create or get supplier prioritized by user, fallback to email
                supplier = Supplier.objects.filter(user=user).first()
                if not supplier:
                    supplier = Supplier.objects.filter(email=invitation.email).first()
                    if supplier:
                        supplier.user = user
                        supplier.save()
                    else:
                        supplier = Supplier.objects.create(
                            user=user,
                            name=invitation.store_name or f"{invitation.email}'s Store",
                            email=invitation.email,
                            phone=invitation.phone or '',
                            address=invitation.address or ''
                        )
                
                # Create store if not exists and supplier exists
                if supplier:
                    store, created = Store.objects.get_or_create(
                        supplier=supplier,
                        defaults={
                            'name': invitation.store_name or supplier.name,
                            'address': invitation.address or ''
                        }
                    )
                    
                    # Create supplier admin role
                    SupplierAdmin.objects.get_or_create(
                        user=user,
                        supplier=supplier,
                        defaults={'role': 'Owner', 'is_active': True}
                    )
                
                # Mark invitation as used
                invitation.is_used = True
                invitation.status = 'accepted'
                invitation.supplier = supplier
                invitation.save()
                
                # Log the user in
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, "Registration successful! You are now logged in.")
                
                # Redirect to success page
                return render(request, 'suppliers/register_success.html', {
                    'user': user,
                    'supplier': supplier
                })
        else:
            # Pre-fill the form with invitation data
            initial_data = {
                'username': invitation.store_name,  # Using store_name since store_username was removed
                'email': invitation.email,
                'first_name': invitation.owner_first_name or '',  # Now we have separate first name
                'last_name': invitation.owner_last_name or '',  # Now we have separate last name
            }
            form = SupplierRegistrationForm(initial=initial_data)

        return render(request, 'suppliers/register.html', {
            'form': form,
            'invitation': invitation
        })
    except SupplierInvitation.DoesNotExist:
        messages.error(request, "Invalid invitation link.")
        return redirect('admin:index')

class SupplierLoginView(View):
    def get(self, request):
        print("GET request received for supplier login")
        if request.user.is_authenticated:
            print("User is authenticated")
            # Check if user has supplier access
            has_supplier_access = False
            if request.user.is_superuser:
                has_supplier_access = True
            else:
                # Check if user has a supplier record by email
                try:
                    from suppliers.models import Supplier
                    supplier = Supplier.objects.get(email=request.user.email)
                    if supplier.is_active:
                        has_supplier_access = True
                except Supplier.DoesNotExist:
                    pass
            
            if has_supplier_access:
                print("User has supplier access, redirecting to dashboard")
                return redirect('suppliers:dashboard')
            else:
                print("User does not have supplier access, logging out")
                logout(request)
        
        form = SupplierLoginForm()
        print("Rendering login template")
        return render(request, 'suppliers/login.html', {
            'form': form,
            'title': 'Supplier Login'
        })

    def post(self, request):
        print("POST request received for supplier login")
        form = SupplierLoginForm(data=request.POST)
        if form.is_valid():
            print("Form is valid")
            user = form.get_user()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, "You have been successfully logged in.")
            return redirect('suppliers:dashboard')
        
        print("Form is invalid")
        return render(request, 'suppliers/login.html', {
            'form': form,
            'title': 'Supplier Login'
        })

@login_required
def supplier_logout(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('suppliers:login')

class SupplierDashboardView(SupplierLoginRequiredMixin, ListView):
    model = Product
    template_name = 'suppliers/dashboard.html'
    context_object_name = 'products'
    paginate_by = 12

    def dispatch(self, request, *args, **kwargs):
        print("DEBUG: SupplierDashboardView dispatch started")
        print(f"DEBUG: User is: {request.user.username}, is_superuser: {request.user.is_superuser}")
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            print("DEBUG: User is not authenticated, redirecting to login")
            return redirect('suppliers:login')
        
        # For superusers, allow access without redirection
        if request.user.is_superuser:
            print("DEBUG: User is superuser, allowing access to dashboard")
            return super().dispatch(request, *args, **kwargs)
        
        # Check if user has a supplier account by email
        try:
            supplier = Supplier.objects.get(email=request.user.email)
            print(f"DEBUG: Found supplier by email: {supplier.name}")
            try:
                result = super().dispatch(request, *args, **kwargs)
                print("DEBUG: Supplier dispatch successful")
                return result
            except Exception as e:
                print(f"DEBUG: Error in supplier dispatch: {str(e)}")
                raise
        except Supplier.DoesNotExist:
            print("DEBUG: No supplier found for user email, raising PermissionDenied")
            raise PermissionDenied(_("This page is only accessible to supplier accounts."))
        except Exception as e:
            print(f"DEBUG: Unexpected error checking supplier: {str(e)}")
            raise

    def get_queryset(self):
        print("DEBUG: SupplierDashboardView get_queryset started")
        
        # For superusers, we might be viewing a specific supplier's products
        if self.request.user.is_superuser:
            print("DEBUG: get_queryset for superuser")
            supplier_id = self.request.GET.get('supplier_id')
            if supplier_id:
                try:
                    supplier = Supplier.objects.get(id=supplier_id)
                    print(f"DEBUG: Filtering products for supplier_id={supplier_id}")
                    return Product.objects.filter(supplier=supplier).order_by('-created_at')
                except Supplier.DoesNotExist:
                    print(f"DEBUG: Supplier with ID {supplier_id} not found")
                    pass
            # If no supplier_id specified or invalid, show all products for superusers
            print("DEBUG: Returning all products for superuser")
            return Product.objects.all().order_by('-created_at')

        # Get the supplier for the current user by email
        try:
            print(f"DEBUG: Getting supplier for user {self.request.user.email}")
            supplier = Supplier.objects.get(email=self.request.user.email)
            print(f"DEBUG: Found supplier: {supplier.name}")
        except Supplier.DoesNotExist:
            print("DEBUG: No supplier found for user email in get_queryset")
            raise PermissionDenied("You don't have permission to access this page.")
        except Exception as e:
            print(f"DEBUG: Error accessing supplier data: {str(e)}")
            raise PermissionDenied(f"Error accessing supplier data: {str(e)}")

        queryset = Product.objects.filter(supplier=supplier)

        # Handle category filtering
        category_id = self.request.GET.get('category')
        if category_id and category_id != 'all':
            print(f"DEBUG: Filtering by category_id={category_id}")
            queryset = queryset.filter(category_id=category_id)

        # Handle search
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            print(f"DEBUG: Searching for query: {search_query}")
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(sku__icontains=search_query)
            )

        print(f"DEBUG: get_queryset returning {queryset.count()} products")
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        print("DEBUG: SupplierDashboardView get_context_data started")
        try:
            context = super().get_context_data(**kwargs)
            print("DEBUG: Base context data retrieved successfully")
        except Exception as e:
            print(f"DEBUG: Error in super().get_context_data: {str(e)}")
            raise
        
        # For superusers, we might be viewing a specific supplier's products
        if self.request.user.is_superuser:
            print("DEBUG: Building context for superuser")
            supplier_id = self.request.GET.get('supplier_id')
            if supplier_id:
                try:
                    supplier = get_object_or_404(Supplier, id=supplier_id)
                    context['supplier'] = supplier
                    
                    # Add total sales for this supplier
                    context['total_sales'] = OrderItem.objects.filter(
                        product__supplier=supplier
                    ).aggregate(total=Sum('price'))['total'] or 0
                    
                    # Add total orders for this supplier
                    context['total_orders'] = Order.objects.filter(
                        items__product__supplier=supplier
                    ).distinct().count()
                except:
                    # Fallback for invalid supplier_id
                    context['suppliers'] = Supplier.objects.all()
                    context['total_sales'] = OrderItem.objects.filter(
                        order__paid=True
                    ).aggregate(total=Sum('price'))['total'] or 0
                    context['total_orders'] = Order.objects.filter(
                        paid=True
                    ).count()
                    context['is_superuser_view'] = True
            else:
                # No specific supplier selected, show all suppliers
                context['suppliers'] = Supplier.objects.all()
                
                # Add total sales across all suppliers
                context['total_sales'] = OrderItem.objects.filter(
                    order__paid=True
                ).aggregate(total=Sum('price'))['total'] or 0
                
                # Add total orders across all suppliers
                context['total_orders'] = Order.objects.filter(
                    paid=True
                ).count()
                
                # Flag to indicate we're in superuser mode without a specific supplier
                context['is_superuser_view'] = True
        else:
            # For Customer users, find supplier by email directly
            try:
                supplier = Supplier.objects.get(email=self.request.user.email)
                context['supplier'] = supplier
                
                # Add total sales for this supplier
                context['total_sales'] = OrderItem.objects.filter(
                    product__supplier=supplier
                ).aggregate(total=Sum('price'))['total'] or 0
                
                # Add total orders for this supplier
                context['total_orders'] = Order.objects.filter(
                    items__product__supplier=supplier
                ).distinct().count()
            except Supplier.DoesNotExist:
                # Handle the case where a user without supplier access somehow gets past dispatch
                context['total_sales'] = 0
                context['total_orders'] = 0
        
        # Add categories to context
        context['categories'] = Category.objects.all()
        
        # Add current category to context
        category_id = self.request.GET.get('category')
        if category_id and category_id != 'all':
            try:
                context['current_category'] = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                pass
        
        # Add search query to context
        context['search_query'] = self.request.GET.get('search', '')
        
        # Add total products count
        context['total_products'] = self.get_queryset().count()

        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                # For AJAX requests, render only the products section
                html = render_to_string('suppliers/includes/products_section.html', context)
                response = HttpResponse(html)
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                return response
            except Exception as e:
                return HttpResponseServerError(f"Error rendering products section: {str(e)}")
        return super().render_to_response(context, **response_kwargs)

@login_required
def select_supplier(request):
    """View for selecting a supplier before adding a product"""
    if not request.user.is_superuser:
        messages.error(request, _("Only superusers can access this page."))
        return redirect('suppliers:dashboard')
    
    suppliers = Supplier.objects.all().order_by('name')
    return render(request, 'suppliers/select_supplier.html', {
        'suppliers': suppliers,
        'title': _('Select Supplier')
    })

@supplier_login_required
def add_product(request):
    # Import ProductAttribute at the top of the function
    from shop.models import ProductAttribute
    
    # Check if this is an edit request (product_id in GET or POST parameters)
    product_id = request.GET.get('product_id') or request.POST.get('product_id')
    product = None
    if product_id:
        product = get_object_or_404(Product, id=product_id)
        # Check if user has permission to edit this product
        if not request.user.is_superuser:
            try:
                user_supplier = Supplier.objects.get(email=request.user.email)
                if product.supplier != user_supplier:
                    raise PermissionDenied
            except Supplier.DoesNotExist:
                raise PermissionDenied

    supplier = None
    if not request.user.is_superuser:
        try:
            supplier = Supplier.objects.get(email=request.user.email)
        except Supplier.DoesNotExist:
            raise PermissionDenied
    else:
        # For superusers, allow specifying supplier via URL parameter
        supplier_id = request.GET.get('supplier')
        if supplier_id:
            try:
                supplier = Supplier.objects.get(id=supplier_id)
            except Supplier.DoesNotExist:
                messages.error(request, "Invalid supplier ID")
                return redirect('suppliers:select_supplier')

    if request.method == 'POST':
        print("DEBUG: POST request received")
        print(f"DEBUG: POST data: {request.POST}")
        print(f"DEBUG: FILES data: {request.FILES}")
        print(f"DEBUG: User: {request.user}")
        print(f"DEBUG: Is AJAX: {request.headers.get('X-Requested-With') == 'XMLHttpRequest'}")
        print(f"DEBUG: product_id from GET: {request.GET.get('product_id')}")
        print(f"DEBUG: product_id from POST: {request.POST.get('product_id')}")
        print(f"DEBUG: final product_id: {product_id}")
        print(f"DEBUG: debug_test field: {request.POST.get('debug_test')}")
        print(f"DEBUG: variant_attributes field: {request.POST.get('variant_attributes')}")
        print(f"DEBUG: has_variants field: {request.POST.get('has_variants')}")
        
        # Print all POST keys that contain 'variant' or 'attr_'
        variant_keys = [k for k in request.POST.keys() if 'variant' in k.lower() or 'attr_' in k.lower()]
        print(f"DEBUG: All variant/attr keys in POST: {variant_keys}")
        for key in variant_keys:
            print(f"DEBUG: {key} = {request.POST.get(key)}")
        
        # Convert is_active to boolean - checkbox sends 'on' when checked, nothing when unchecked
        post_data = request.POST.copy()
        is_active_value = post_data.get('is_active')
        print(f"DEBUG: Raw is_active value: '{is_active_value}'")
        
        # Handle checkbox: 'on' means checked (True), None/empty means unchecked (False)
        if is_active_value == 'on':
            post_data['is_active'] = True
            print("DEBUG: Setting is_active to True (checkbox was checked)")
        else:
            post_data['is_active'] = False
            print("DEBUG: Setting is_active to False (checkbox was unchecked)")

        # Normalize numeric fields to ASCII digits without thousand separators
        def _normalize_number(value: str) -> str:
            if value is None:
                return None
            if value == '' or value.strip() == '':
                return None  # Return None instead of empty string for Decimal fields
            # Persian and Arabic-Indic digits to ASCII
            translation_table = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
            normalized = value.translate(translation_table)
            # Remove common separators/spaces
            normalized = normalized.replace(',', '').replace(' ', '').replace('\u200c', '').strip()
            # Return None if empty after normalization
            if normalized == '':
                return None
            return normalized

        if 'price_toman' in post_data:
            normalized_price = _normalize_number(post_data.get('price_toman', ''))
            if normalized_price is None:
                # Keep original value if normalization resulted in None (form will validate)
                pass
            else:
                post_data['price_toman'] = normalized_price
        if 'price_usd' in post_data:
            # Allow empty USD price (optional field)
            raw_usd = post_data.get('price_usd', '')
            normalized_usd = _normalize_number(raw_usd) if raw_usd else None
            if normalized_usd is None:
                post_data['price_usd'] = ''  # Empty string for optional field
            else:
                post_data['price_usd'] = normalized_usd
        if 'reduced_price_toman' in post_data:
            # Allow empty reduced price (optional field)
            raw_reduced = post_data.get('reduced_price_toman', '')
            normalized_reduced = _normalize_number(raw_reduced) if raw_reduced else None
            if normalized_reduced is None:
                post_data['reduced_price_toman'] = ''  # Empty string for optional field
            else:
                post_data['reduced_price_toman'] = normalized_reduced
        if 'discount_percentage' in post_data:
            # Allow empty discount percentage (optional field)
            raw_discount = post_data.get('discount_percentage', '')
            normalized_discount = _normalize_number(raw_discount) if raw_discount else None
            if normalized_discount is None:
                post_data['discount_percentage'] = ''  # Empty string for optional field
            else:
                post_data['discount_percentage'] = normalized_discount
        
        try:
            # Get variant attributes before creating the form
            variant_attributes = request.POST.get('variant_attributes', '')
            variant_attr_keys = []
            if variant_attributes:
                try:
                    variant_attr_keys = json.loads(variant_attributes)
                except Exception:
                    variant_attr_keys = []
            
            # ✨ Auto-select distinctive attribute if only one variant attribute is selected
            # First try to get from request.POST, then check if we need to auto-select
            distinctive_attr_key = request.POST.get('distinctive_attribute', '')
            
            # Auto-select if only one variant attribute is selected AND no distinctive attribute was explicitly chosen
            if not distinctive_attr_key and len(variant_attr_keys) == 1:
                distinctive_attr_key = variant_attr_keys[0]
                print(f"🎯 Auto-selected distinctive attribute (only one): {distinctive_attr_key}")
                # Store in post_data so it's available for form processing
                post_data['distinctive_attribute'] = distinctive_attr_key

            # Only exclude variant attributes in ProductForm when variants are enabled
            has_variants = request.POST.get('has_variants') == 'on'
            if has_variants and variant_attr_keys:
                post_data = post_data.copy()
                post_data['variant_attributes'] = variant_attributes
                print(f"DEBUG: Added variant_attributes to post_data (variants enabled): {variant_attributes}")
            else:
                # Ensure ProductForm does NOT exclude any attributes when variants are disabled
                if 'variant_attributes' in post_data:
                    post_data.pop('variant_attributes', None)
                print("DEBUG: Variants disabled or no variant attributes; not excluding any form attributes")
            
            # CRITICAL FIX: Always include variant_attributes in form data if variants are enabled
            # This ensures ProductForm can properly exclude variant attributes from the main form
            if has_variants:
                if 'variant_attributes' not in post_data:
                    post_data['variant_attributes'] = variant_attributes
                    print(f"DEBUG: CRITICAL FIX - Added missing variant_attributes to post_data: {variant_attributes}")
                else:
                    print(f"DEBUG: variant_attributes already in post_data: {post_data.get('variant_attributes')}")
                
                # FALLBACK: If variant_attributes is still empty, try to extract from variants_data
                if not variant_attributes and not post_data.get('variant_attributes'):
                    variants_data = request.POST.get('variants_data')
                    if variants_data:
                        try:
                            variants = json.loads(variants_data)
                            if variants:
                                # Extract attribute keys from the first variant
                                first_variant = variants[0]
                                variant_attrs = first_variant.get('attributes', {})
                                if variant_attrs:
                                    variant_keys = list(variant_attrs.keys())
                                    fallback_variant_attributes = json.dumps(variant_keys)
                                    post_data['variant_attributes'] = fallback_variant_attributes
                                    print(f"DEBUG: FALLBACK - Extracted variant attributes from variants_data: {fallback_variant_attributes}")
                        except Exception as e:
                            print(f"DEBUG: FALLBACK - Error extracting variant attributes from variants_data: {e}")
            
            # Create form with variant attributes to exclude them from validation
            # Pass variant attributes as initial data so ProductForm can access them
            form_kwargs = {
                'data': post_data,
                'files': request.FILES,
                'instance': product
            }
            form = ProductForm(**form_kwargs)
            print(f"DEBUG: Form created successfully")
            print(f"DEBUG: Form fields: {list(form.fields.keys())}")
            print(f"DEBUG: Variant attributes from POST: {post_data.get('variant_attributes', '')}")
            print(f"DEBUG: Variant attr keys: {variant_attr_keys}")
            print(f"DEBUG: Form is_valid: {form.is_valid()}")
            print(f"DEBUG: Form errors: {form.errors}")
            print(f"DEBUG: Form non-field errors: {form.non_field_errors()}")
            
            if form.is_valid():
                print(f"DEBUG: ✅ Form is valid, proceeding with save")
                print(f"DEBUG: Form cleaned_data keys: {list(form.cleaned_data.keys())}")
                print(f"DEBUG: Product name before save: {product.name if product else 'NEW PRODUCT'}")
                print(f"DEBUG: Product description before save: {product.description if product else 'NEW PRODUCT'}")
                
                # Check specific attributes before save
                print(f"DEBUG: 🔍 Checking attributes before save...")
                if 'attr_strap_material' in form.cleaned_data:
                    print(f"DEBUG: 🎯 strap_material before save: '{form.cleaned_data['attr_strap_material']}'")
                if 'attr_body_material' in form.cleaned_data:
                    print(f"DEBUG: 📝 body_material before save: '{form.cleaned_data['attr_body_material']}'")
                if 'attr_glass_material' in form.cleaned_data:
                    print(f"DEBUG: 📝 glass_material before save: '{form.cleaned_data['attr_glass_material']}'")
            else:
                print(f"DEBUG: ❌ Form is not valid")
                print(f"DEBUG: Form errors: {form.errors}")
                print(f"DEBUG: Form non-field errors: {form.non_field_errors()}")
            
            # Check if attr_color and attr_size are in form fields
            if 'attr_color' in form.fields:
                print(f"DEBUG: ERROR - attr_color field still exists in form!")
            if 'attr_size' in form.fields:
                print(f"DEBUG: ERROR - attr_size field still exists in form!")
            
            # Build a normalized map of attribute values for robust lookup
            normalized_attr_map = _build_normalized_attr_map(request.POST)
            print(f"DEBUG: Normalized attr map: {normalized_attr_map}")
            try:
                has_variants_flag = request.POST.get('has_variants')
                variant_attrs_raw = request.POST.get('variant_attributes')
                print(f"DEBUG: Attribute Save Trace → has_variants='{has_variants_flag}', variant_attributes='{variant_attrs_raw}'")
                posted_attr_keys = [k for k in request.POST.keys() if k.startswith('attr_')]
                sample_attr_items = {k: request.POST.getlist(k) for k in posted_attr_keys[:10]}
                print(f"DEBUG: Attribute Save Trace → posted attr_* keys count={len(posted_attr_keys)} sample={sample_attr_items}")
            except Exception as e:
                print(f"DEBUG: Attribute Save Trace → error while tracing post keys: {e}")
            
            if form.is_valid():
                print("DEBUG: Form is valid!")
                try:
                    # Validate required category attributes BEFORE saving anything
                    selected_category = form.cleaned_data.get('category')
                    if selected_category:
                        # Ensure category is saved before using in related filters
                        if not selected_category.pk:
                            selected_category.save()
                        
                        # Get variant attributes that are selected for variants
                        variant_attributes = request.POST.get('variant_attributes', '')
                        variant_attr_keys = []
                        print(f"DEBUG: Raw variant_attributes from POST: '{variant_attributes}'")
                        print(f"DEBUG: Type of variant_attributes: {type(variant_attributes)}")
                        if variant_attributes:
                            try:
                                variant_attr_keys = json.loads(variant_attributes)
                                print(f"DEBUG: Parsed variant_attr_keys: {variant_attr_keys}")
                            except Exception as e:
                                print(f"DEBUG: Error parsing variant_attributes JSON: {e}")
                                variant_attr_keys = []
                        else:
                            print("DEBUG: No variant_attributes found in POST data")
                        
                        print(f"DEBUG: Final variant_attr_keys: {variant_attr_keys}")
                        
                        required_attrs = CategoryAttribute.objects.filter(category=selected_category)
                        validation_errors = []
                        
                        for attr in required_attrs:
                            field_name = f'attr_{attr.key}'
                            norm_key = _normalize_persian_key(attr.key)
                            
                            # Skip validation if this attribute is used for variants
                            if attr.key in variant_attr_keys:
                                print(f"DEBUG: Skipping validation for variant attribute: {attr.key}")
                                continue
                            
                            # Allow brand to be optional for watch categories
                            # Allow size to be optional for t-shirt categories
                            attr_is_required = attr.required
                            try:
                                cat_name = (selected_category.get_display_name() or selected_category.name or '').lower()
                            except Exception:
                                cat_name = (getattr(selected_category, 'name', '') or '').lower()
                            if attr.key.lower() in ['brand', 'برند'] and 'ساعت' in cat_name:
                                attr_is_required = False
                            elif attr.key.lower() in ['size', 'سایز'] and 'تی شرت' in cat_name:
                                attr_is_required = False

                            if attr_is_required:
                                if attr.type == 'multiselect':
                                    values_entry = normalized_attr_map.get(norm_key, [])
                                    if isinstance(values_entry, str):
                                        values_list = [values_entry] if values_entry else []
                                    else:
                                        values_list = [v for v in values_entry if v]
                                    if len(values_list) == 0:
                                        validation_errors.append(f'ویژگی "{attr.key}" الزامی است')
                                else:
                                    value_entry = normalized_attr_map.get(norm_key, [])
                                    if isinstance(value_entry, (list, tuple)):
                                        # Take the first non-empty
                                        value = next((v for v in value_entry if isinstance(v, str) and v.strip()), '')
                                    else:
                                        value = value_entry.strip() if isinstance(value_entry, str) else ''
                                    if not value:
                                        validation_errors.append(f'ویژگی "{attr.key}" الزامی است')
                        
                        # Add validation errors to form if any
                        if validation_errors:
                            for error in validation_errors:
                                form.add_error(None, error)
                            print(f"DEBUG: Added validation errors: {validation_errors}")
                            
                except Exception as e:
                    error_msg = f'خطا در اعتبارسنجی ویژگی‌های دسته‌بندی: {str(e)}'
                    form.add_error(None, error_msg)
                    print(f"DEBUG: Category attribute validation error: {e}")
                    import traceback
                    traceback.print_exc()

                if form.errors:
                    # Do not save anything if attribute validation failed
                    print(f"DEBUG: Form/attribute validation errors: {form.errors}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': ' '.join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
                        })
                    messages.error(request, "Please correct the errors below.")
                else:
                    # Validate variant attributes BEFORE saving the product
                    variant_validation_errors = []
                    variants_data = request.POST.get('variants_data')
                    
                    if variants_data:
                        try:
                            variants = json.loads(variants_data)
                            print(f"DEBUG: Pre-save validation - Parsed variants: {variants}")
                            
                            # Get variant attributes that are selected for variants
                            variant_attributes = request.POST.get('variant_attributes', '')
                            variant_attr_keys = []
                            
                            if variant_attributes:
                                try:
                                    variant_attr_keys = json.loads(variant_attributes)
                                    print(f"DEBUG: Pre-save validation - Variant attribute keys: {variant_attr_keys}")
                                except Exception as e:
                                    print(f"DEBUG: Error parsing variant_attributes for pre-save validation: {e}")
                                    variant_attr_keys = []
                            
                            # Get required attributes for the selected variant attributes
                            if variant_attr_keys:
                                required_variant_attrs = CategoryAttribute.objects.filter(
                                    category=selected_category,
                                    key__in=variant_attr_keys,
                                    required=True
                                )
                                print(f"DEBUG: Pre-save validation - Required variant attributes: {[attr.key for attr in required_variant_attrs]}")
                                
                                # Validate each variant
                                for i, variant_data in enumerate(variants):
                                    variant_number = i + 1
                                    variant_attributes_data = variant_data.get('attributes', {})
                                    
                                    for attr in required_variant_attrs:
                                        attr_value = variant_attributes_data.get(attr.key, '')
                                        if not attr_value or (isinstance(attr_value, str) and attr_value.strip() == ''):
                                            variant_validation_errors.append(f'نوع {variant_number}: ویژگی "{attr.key}" انتخاب نشده است')
                                            print(f"DEBUG: ❌ Pre-save validation - Variant {variant_number} missing required attribute: {attr.key}")
                                    
                                    print(f"DEBUG: ✅ Pre-save validation - Variant {variant_number} passed")
                            
                        except Exception as e:
                            print(f"DEBUG: Error in pre-save variant validation: {e}")
                            variant_validation_errors.append(f'خطا در اعتبارسنجی انواع محصول: {str(e)}')
                    
                    # If there are validation errors, don't save the product
                    if variant_validation_errors:
                        print(f"DEBUG: ❌ Pre-save validation failed: {variant_validation_errors}")
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'error': ' '.join(variant_validation_errors)
                            })
                        messages.error(request, "خطا در ذخیره محصول: " + ' '.join(variant_validation_errors))
                        # Re-render the form with the submitted data preserved
                        form = ProductForm(request.POST, request.FILES, instance=product)
                    else:
                        print(f"DEBUG: ✅ Pre-save validation passed, proceeding with product save")
                        
                        try:
                            with transaction.atomic():
                                # Save the product first
                                product = form.save(commit=False)
                                if supplier:
                                    product.supplier = supplier
                                
                                # ✨ Set distinctive attribute key BEFORE saving
                                # Use distinctive_attr_key that was set earlier (with auto-selection logic)
                                if distinctive_attr_key:
                                    product.distinctive_attribute_key = distinctive_attr_key
                                    print(f"✅ Set distinctive attribute key: {distinctive_attr_key}")
                                else:
                                    product.distinctive_attribute_key = None
                                    print("🔧 No distinctive attribute key")
                                
                                product.save()
                                print(f"DEBUG: ✅ Product saved successfully!")
                                print(f"DEBUG: Product name after save: {product.name}")
                                print(f"DEBUG: Product description after save: {product.description}")
                                print(f"DEBUG: Product price_toman after save: {product.price_toman}")
                                print(f"DEBUG: Product stock_quantity after save: {product.stock_quantity}")
                                print(f"DEBUG: Product is_active after save: {product.is_active}")
                                
                                # Check specific attributes after save
                                print(f"DEBUG: 🔍 Checking attributes after save...")
                                from shop.models import ProductAttribute
                                saved_attrs = ProductAttribute.objects.filter(product=product)
                                for attr in saved_attrs:
                                    if attr.key == 'strap_material':
                                        print(f"DEBUG: 🎯 strap_material after save: '{attr.value}'")
                                    elif attr.key in ['body_material', 'glass_material', 'sadas', 'water resistant', 'جنس شیشه', 'مقاوم در برابر آب']:
                                        print(f"DEBUG: 📝 {attr.key}: '{attr.value}'")
                                
                                # Save tags using form's save_m2m method
                                form.save_m2m()

                                # Save category attributes within the same transaction
                                category = form.cleaned_data.get('category')
                                if category:
                                    # Get variant attributes that are selected for variants (same logic as earlier)
                                    variant_attributes_save = request.POST.get('variant_attributes', '')
                                    variant_attr_keys_save = []
                                    print(f"DEBUG: Raw variant_attributes during save: '{variant_attributes_save}'")
                                    if variant_attributes_save:
                                        try:
                                            variant_attr_keys_save = json.loads(variant_attributes_save)
                                            print(f"DEBUG: Parsed variant_attr_keys during save: {variant_attr_keys_save}")
                                        except Exception as e:
                                            print(f"DEBUG: Error parsing variant_attributes during save: {e}")
                                            variant_attr_keys_save = []
                                    
                                    # Ensure category is saved before using in related filters
                                    if not category.pk:
                                        category.save()
                                    category_attrs = CategoryAttribute.objects.filter(category=category)
                                    for attr in category_attrs:
                                        # Skip saving attributes that are used for variants
                                        if attr.key in variant_attr_keys_save:
                                            print(f"DEBUG: Skipping save for variant attribute: {attr.key}")
                                            continue
                                        attr_key = f'attr_{attr.key}'
                                        norm_key = _normalize_persian_key(attr.key)
                                        if attr.type == 'multiselect':
                                            values_entry = normalized_attr_map.get(norm_key, [])
                                            if isinstance(values_entry, str):
                                                values = [values_entry] if values_entry else []
                                            else:
                                                values = [v for v in values_entry if v]
                                            value_to_store = ','.join(values) if values else ''
                                        else:
                                            # Prefer cleaned_data; fall back to normalized POST map
                                            raw_value = form.cleaned_data.get(attr_key)
                                            if raw_value in (None, ''):
                                                entry = normalized_attr_map.get(norm_key, [])
                                                if isinstance(entry, (list, tuple)):
                                                    raw_value = next((v for v in entry if isinstance(v, str) and v.strip()), '')
                                                else:
                                                    raw_value = entry
                                            value_to_store = (raw_value if raw_value is not None else '')
                                            if isinstance(value_to_store, str):
                                                value_to_store = value_to_store.strip()

                                        # Note: Variant attributes are already skipped above, so we don't need to skip them again here

                                        # Allow brand to be optional for watch categories
                                        attr_is_required = attr.required
                                        try:
                                            cat_name = (category.get_display_name() or category.name or '').lower()
                                        except Exception:
                                            cat_name = (getattr(category, 'name', '') or '').lower()
                                        if attr.key.lower() in ['brand', 'برند'] and 'ساعت' in cat_name:
                                            attr_is_required = False

                                        if attr_is_required and not value_to_store:
                                            # Only raise error if the field actually exists in the form
                                            if hasattr(form, 'fields') and attr_key in form.fields:
                                                raise ValueError(_(f'فیلد {attr.key} الزامی است'))
                                            else:
                                                print(f"DEBUG: Required field {attr_key} is empty but field doesn't exist in form, skipping validation")

                                        if value_to_store:
                                            pav, _created = ProductAttribute.objects.get_or_create(product=product, key=attr.key)
                                            prev_value = getattr(pav, 'value', None)
                                            print(
                                                f"DEBUG: Attribute Save Trace → product_id={getattr(product, 'id', None)} "
                                                f"key='{attr.key}' prev='{prev_value}' new='{value_to_store}' created={_created}"
                                            )
                                            pav.value = value_to_store
                                            pav.save()
                                            print(
                                                f"DEBUG: Attribute Save Trace → SAVED key='{attr.key}' final='{pav.value}'"
                                            )
                                        else:
                                            print(
                                                f"DEBUG: Attribute Save Trace → SKIP EMPTY product_id={getattr(product, 'id', None)} key='{attr.key}'"
                                            )

                        except Exception as e:
                            print(f"DEBUG: Error saving product (rolled back): {str(e)}")
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': False,
                                    'error': str(e)
                                })
                            messages.error(request, f"Error saving product: {str(e)}")
                        else:
                            # Collect image-related data after saving product (outside atomic)
                            all_images = request.FILES.getlist('all_images')
                            image_orders = [int(x) for x in request.POST.getlist('image_order')]
                            replace_image_ids = request.POST.getlist('replace_image_id')
                            existing_image_ids = request.POST.getlist('existing_image_ids')
                            existing_image_orders = request.POST.getlist('existing_image_orders')

                            # Normalize lengths
                            while len(image_orders) < len(all_images):
                                image_orders.append(len(image_orders) + 1)
                            while len(replace_image_ids) < len(all_images):
                                replace_image_ids.append('')

                            print(f"📥 New files={len(all_images)}, replace_ids={replace_image_ids}")
                            print(f"📥 Existing IDs preserved={existing_image_ids}")

                            # Initialize variables if not set
                            if 'existing_image_ids' not in locals():
                                existing_image_ids = []
                                existing_image_orders = []
                                replace_image_ids = []
                                all_images = []
                                image_orders = []

                            # Snapshot of current images
                            current_images = list(ProductImage.objects.filter(product=product)) if product_id else []
                            current_by_id = {str(img.id): img for img in current_images}

                            # Decide preservation set
                            preserved_ids = set(existing_image_ids)
                            preserved_ids.update({rid for rid in replace_image_ids if rid})

                            # 1) Delete images not preserved
                            for img in current_images:
                                if str(img.id) not in preserved_ids:
                                    try:
                                        print(f"🗑️ Deleting removed image {img.id} {img.image.name}")
                                        if img.image and os.path.isfile(img.image.path):
                                            os.remove(img.image.path)
                                        img.delete()
                                    except Exception as e:
                                        print(f"❌ Delete error for image {img.id}: {e}")

                            # 2) Handle replacements (overwrite file to keep URL if possible)
                            for upload_file, order, replace_id in zip(all_images, image_orders, replace_image_ids):
                                if replace_id and replace_id in current_by_id:
                                    img_obj = current_by_id[replace_id]
                                    try:
                                        # Overwrite by deleting and saving with the same storage name
                                        storage = img_obj.image.storage
                                        current_name = img_obj.image.name  # relative path in storage
                                        print(f"✍️ Replacing existing image {img_obj.id} at {current_name}")
                                        try:
                                            storage.delete(current_name)
                                        except Exception as del_err:
                                            print(f"  ⚠️ Could not delete before replace (may not exist): {del_err}")
                                        # Save new content under the same name
                                        img_obj.image.save(current_name, upload_file, save=False)
                                        # Recalculate hash and update order/primary
                                        img_obj.image_hash = None
                                        img_obj.order = int(order)
                                        img_obj.is_primary = (int(order) == 1)
                                        img_obj.save()
                                    except Exception as e:
                                        print(f"❌ Replace error for image {img_obj.id}: {e}")
                                else:
                                    # Create new image
                                    try:
                                        new_img = ProductImage.create(
                                            product=product,
                                            image=upload_file,
                                            is_primary=(int(order) == 1),
                                            order=int(order)
                                        )
                                        print(f"✅ Created new image {new_img.id}")
                                    except Exception as e:
                                        print(f"❌ Create error: {e}")

                            # 3) Update orders for preserved existing images
                            print(f"🔄 UPDATING IMAGE ORDERS:")
                            print(f"   Received {len(existing_image_ids)} image IDs: {existing_image_ids}")
                            print(f"   Received {len(existing_image_orders)} image orders: {existing_image_orders}")
                            
                            if len(existing_image_ids) != len(existing_image_orders):
                                print(f"❌ ERROR: Mismatch! {len(existing_image_ids)} IDs but {len(existing_image_orders)} orders")
                            else:
                                print(f"✅ Lists match - processing {len(existing_image_ids)} images")
                            
                            # ✨ CRITICAL FIX: Update orders in two passes to avoid conflicts
                            # First pass: Set all orders to temporary high values to avoid conflicts
                            max_temp_order = 10000  # Use a high temp order value
                            images_to_update = []
                            
                            for img_id, order in zip(existing_image_ids, existing_image_orders):
                                try:
                                    img = ProductImage.objects.get(id=img_id, product=product)
                                    old_order = img.order
                                    final_order = int(order)
                                    
                                    # Store in list for second pass
                                    images_to_update.append({
                                        'img': img,
                                        'img_id': img_id,
                                        'old_order': old_order,
                                        'final_order': final_order
                                    })
                                    
                                    # First pass: Set to temporary order to avoid conflicts
                                    img.order = max_temp_order + len(images_to_update)
                                    img.save()
                                    print(f"🔄 Pass 1: Image {img_id} set to temp order {img.order} (will be {final_order})")
                                except Exception as e:
                                    print(f"❌ Order update error for {img_id}: {e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            # Second pass: Set all orders to their final values
                            print(f"🔄 Pass 2: Setting final orders...")
                            for item in images_to_update:
                                try:
                                    img = item['img']
                                    img.order = item['final_order']
                                    img.is_primary = (item['final_order'] == 1)
                                    img.save()
                                    print(f"✅ Updated image {item['img_id']}: order {item['old_order']} -> {img.order} (is_primary: {img.is_primary})")
                                except Exception as e:
                                    print(f"❌ Order update error for {item['img_id']} in pass 2: {e}")
                                    import traceback
                                    traceback.print_exc()

                            print("✅ IMAGE PROCESSING COMPLETE")
                            
                            # Final verification: Check actual orders in database
                            print(f"🔍 FINAL VERIFICATION - Current image orders in database:")
                            all_images_final = ProductImage.objects.filter(product=product).order_by('order')
                            for img in all_images_final:
                                print(f"   Image ID {img.id}: order {img.order} (is_primary: {img.is_primary})")
                            
                            # Verify the orders match what we sent
                            expected_orders = {str(img_id): int(order) for img_id, order in zip(existing_image_ids, existing_image_orders)}
                            actual_orders = {str(img.id): img.order for img in all_images_final}
                            
                            mismatch = False
                            for img_id, expected_order in expected_orders.items():
                                if img_id in actual_orders:
                                    if actual_orders[img_id] != expected_order:
                                        print(f"❌ MISMATCH: Image {img_id} has order {actual_orders[img_id]} but should be {expected_order}")
                                        mismatch = True
                                else:
                                    print(f"❌ ERROR: Image {img_id} not found in database!")
                                    mismatch = True
                            
                            if not mismatch:
                                print(f"✅ VERIFICATION PASSED: All orders match!")
                            else:
                                print(f"❌ VERIFICATION FAILED: Orders don't match!")

                            # Also handle any new images from the regular file input (fallback)
                            regular_images = request.FILES.getlist('images')
                            if regular_images:
                                print(f"📥 Processing {len(regular_images)} additional regular images")
                                current_max_order = ProductImage.objects.filter(product=product).aggregate(Max('order'))['order__max'] or 0
                                
                                for i, image in enumerate(regular_images):
                                    order = current_max_order + i + 1
                                    print(f"   📷 Creating additional image: order={order}")
                                    
                                    try:
                                        new_image = ProductImage.create(
                                            product=product,
                                            image=image,
                                            is_primary=(order == 1),
                                            order=order
                                        )
                                        print(f"   ✅ Created additional image ID {new_image.id}")
                                    except Exception as e:
                                        print(f"   ❌ Error creating additional image: {str(e)}")
                                        continue

                            # Process product variants
                            variants_data = request.POST.get('variants_data')
                            # Debug form submission data
                            print(f"DEBUG: Form submission started")
                            print(f"DEBUG: POST keys: {list(request.POST.keys())}")
                            print(f"DEBUG: Category value: {request.POST.get('category')}")
                            print(f"DEBUG: Product name: {request.POST.get('name')}")
                            print(f"DEBUG: Form errors: {form.errors}")
                            
                            print(f"DEBUG: variants_data received: {variants_data}")
                            print(f"DEBUG: variants_data type: {type(variants_data)}")
                            print(f"DEBUG: variants_data length: {len(variants_data) if variants_data else 0}")
                            
                            # Log all POST data for debugging
                            print(f"DEBUG: All POST data:")
                            for key, value in request.POST.items():
                                if 'variant' in key.lower():
                                    print(f"  {key}: {value}")
                            
                            # Check if variants checkbox is checked
                            has_variants = request.POST.get('has_variants')
                            print(f"DEBUG: has_variants checkbox: {has_variants}")
                            
                            # Also check for variant_attributes
                            variant_attributes = request.POST.get('variant_attributes')
                            print(f"DEBUG: variant_attributes received: {variant_attributes}")
                            
                            if variants_data:
                                try:
                                    from shop.models import ProductVariant
                                    
                                    variants = json.loads(variants_data)
                                    print(f"DEBUG: Parsed variants: {variants}")
                                    print(f"DEBUG: Processing {len(variants)} variants")
                                    
                                    # Validate variant attributes before creating variants
                                    variant_validation_errors = []
                                    variant_attributes = request.POST.get('variant_attributes', '')
                                    variant_attr_keys = []
                                    
                                    if variant_attributes:
                                        try:
                                            variant_attr_keys = json.loads(variant_attributes)
                                            print(f"DEBUG: Variant attribute keys for validation: {variant_attr_keys}")
                                        except Exception as e:
                                            print(f"DEBUG: Error parsing variant_attributes for validation: {e}")
                                            variant_attr_keys = []
                                    
                                    # Get required attributes for the selected variant attributes
                                    if variant_attr_keys:
                                        required_variant_attrs = CategoryAttribute.objects.filter(
                                            category=selected_category,
                                            key__in=variant_attr_keys,
                                            required=True
                                        )
                                        print(f"DEBUG: Required variant attributes: {[attr.key for attr in required_variant_attrs]}")
                                        
                                        # Validate each variant
                                        for i, variant_data in enumerate(variants):
                                            variant_number = i + 1
                                            variant_attributes_data = variant_data.get('attributes', {})
                                            
                                            for attr in required_variant_attrs:
                                                attr_value = variant_attributes_data.get(attr.key, '')
                                                if not attr_value or (isinstance(attr_value, str) and attr_value.strip() == ''):
                                                    variant_validation_errors.append(f'نوع {variant_number}: ویژگی "{attr.key}" انتخاب نشده است')
                                                    print(f"DEBUG: ❌ Variant {variant_number} missing required attribute: {attr.key}")
                                            
                                            print(f"DEBUG: ✅ Variant {variant_number} validation passed")
                                    
                                    # If there are validation errors, don't save the product
                                    if variant_validation_errors:
                                        print(f"DEBUG: ❌ Variant validation failed: {variant_validation_errors}")
                                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                            return JsonResponse({
                                                'success': False,
                                                'error': ' '.join(variant_validation_errors)
                                            })
                                        messages.error(request, "خطا در ذخیره محصول: " + ' '.join(variant_validation_errors))
                                        # Don't proceed with variant creation
                                    else:
                                        print(f"DEBUG: ✅ All variants passed validation, proceeding with upsert")
                                        
                                        # Upsert variants by SKU: update existing, create new, remove stale
                                        from shop.models import ProductVariant, ProductVariantImage
                                        existing_variants = {v.sku: v for v in ProductVariant.objects.filter(product=product)}
                                        incoming_skus = set()
                                        
                                        for i, variant_data in enumerate(variants):
                                            sku_val = variant_data.get('sku', '') or ''
                                            incoming_skus.add(sku_val)
                                            attrs_val = variant_data.get('attributes', {}) or {}
                                            price_val = variant_data.get('priceToman', product.price_toman)
                                            stock_val = variant_data.get('stock', 0)
                                            is_active_val = variant_data.get('isActive', True)
                                            is_default_val = variant_data.get('isDefault', False)
                                            
                                            if sku_val in existing_variants:
                                                variant = existing_variants[sku_val]
                                                print(f"DEBUG: Updating existing variant {sku_val} (ID {variant.id})")
                                                variant.attributes = attrs_val
                                                variant.price_toman = price_val
                                                variant.stock_quantity = stock_val
                                                variant.is_active = is_active_val
                                                variant.is_default = is_default_val
                                                variant.save()
                                            else:
                                                print(f"DEBUG: Creating new variant for SKU {sku_val}")
                                                variant = ProductVariant.objects.create(
                                                    product=product,
                                                    sku=sku_val,
                                                    attributes=attrs_val,
                                                    price_toman=price_val,
                                                    stock_quantity=stock_val,
                                                    is_active=is_active_val,
                                                    is_default=is_default_val
                                                )
                                                existing_variants[sku_val] = variant
                                            
                                            # Process variant images: if provided, replace; if not, preserve existing
                                            variant_images = variant_data.get('images', [])
                                            if variant_images:
                                                # Remove existing images for this variant
                                                ProductVariantImage.objects.filter(variant=variant).delete()
                                                print(f"DEBUG: Replacing images for variant {sku_val} with {len(variant_images)} new images")
                                                for j, image_data in enumerate(variant_images):
                                                    try:
                                                        if isinstance(image_data, str) and image_data.startswith('data:image'):
                                                            import base64
                                                            from django.core.files.base import ContentFile
                                                            format, imgstr = image_data.split(';base64,')
                                                            ext = format.split('/')[-1]
                                                            image_file = ContentFile(base64.b64decode(imgstr), name=f"{sku_val}_{j+1}.{ext}")
                                                            ProductVariantImage.create(
                                                                variant=variant,
                                                                image=image_file,
                                                                is_primary=(j == 0),
                                                                order=j + 1
                                                            )
                                                        elif hasattr(image_data, 'read'):
                                                            ProductVariantImage.create(
                                                                variant=variant,
                                                                image=image_data,
                                                                is_primary=(j == 0),
                                                                order=j + 1
                                                            )
                                                    except Exception as e:
                                                        print(f"DEBUG: Error creating variant image {j+1} for {sku_val}: {e}")
                                                        continue
                                            else:
                                                print(f"DEBUG: No new images supplied for {sku_val}; preserving existing images")
                                        
                                        # Delete variants that are no longer present
                                        stale = [v for s, v in existing_variants.items() if s not in incoming_skus]
                                        if stale:
                                            print(f"DEBUG: Deleting {len(stale)} stale variants not present in submission")
                                            for v in stale:
                                                try:
                                                    v.delete()
                                                except Exception as e:
                                                    print(f"DEBUG: Error deleting stale variant {v.sku}: {e}")
                                
                                except Exception as e:
                                    print(f"DEBUG: Error processing variants: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    messages.warning(request, f"Product saved but variants could not be processed: {e}")
                            else:
                                print("DEBUG: ❌ No variants_data found in POST request")
                                print("DEBUG: Checking for variant_attributes:", request.POST.get('variant_attributes'))
                                print("DEBUG: Has variants checkbox value:", request.POST.get('has_variants'))
                                print("DEBUG: All POST keys containing 'variant':", [k for k in request.POST.keys() if 'variant' in k.lower()])

                            messages.success(request, _("Product has been saved successfully."))
                            
                            # Determine redirect URL based on the submit button clicked
                            print(f"DEBUG: About to redirect. product_id={product_id}, product.id={product.id}")
                            print(f"DEBUG: POST buttons: _addanother={request.POST.get('_addanother')}, _continue={request.POST.get('_continue')}, _save={request.POST.get('_save')}")
                            
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                # Preserve supplier parameter in redirect URLs
                                supplier_param = request.GET.get('supplier', '')
                                supplier_query = f'?supplier={supplier_param}' if supplier_param else ''
                                
                                if '_addanother' in request.POST:
                                    redirect_url = f'{reverse("suppliers:add_product")}{supplier_query}'
                                elif '_continue' in request.POST:
                                    redirect_url = f'{reverse("suppliers:add_product")}?product_id={product.id}{"&" if supplier_param else ""}{supplier_query.replace("?", "")}'
                                elif product_id:  # If editing existing product, stay on edit page
                                    redirect_url = f'{reverse("suppliers:add_product")}?product_id={product.id}{"&" if supplier_param else ""}{supplier_query.replace("?", "")}'
                                elif request.user.is_superuser:
                                    redirect_url = reverse('shop:admin_products_explorer')
                                else:
                                    redirect_url = reverse('suppliers:dashboard')
                                
                                print(f"DEBUG: AJAX redirect_url: {redirect_url}")
                                return JsonResponse({
                                    'success': True,
                                    'redirect_url': redirect_url
                                })
                            else:
                                # Handle regular form submission
                                # Preserve supplier parameter in redirect URLs
                                supplier_param = request.GET.get('supplier', '')
                                supplier_query = f'?supplier={supplier_param}' if supplier_param else ''
                                
                                if '_addanother' in request.POST:
                                    redirect_url = f'{reverse("suppliers:add_product")}{supplier_query}'
                                elif '_continue' in request.POST:
                                    redirect_url = f'{reverse("suppliers:add_product")}?product_id={product.id}{"&" if supplier_param else ""}{supplier_query.replace("?", "")}'
                                elif product_id:  # If editing existing product, stay on edit page
                                    redirect_url = f'{reverse("suppliers:add_product")}?product_id={product.id}{"&" if supplier_param else ""}{supplier_query.replace("?", "")}'
                                elif request.user.is_superuser:
                                    redirect_url = reverse('shop:admin_products_explorer')
                                else:
                                    redirect_url = reverse('suppliers:dashboard')
                                
                                print(f"DEBUG: Regular form redirect_url: {redirect_url}")
                                return redirect(redirect_url)
            else:
                print(f"DEBUG: Form errors: {form.errors}")
                print(f"DEBUG: Form non-field errors: {form.non_field_errors()}")
                print(f"DEBUG: Form is_valid: {form.is_valid()}")
                
                # Log each field error in detail
                for field_name, errors in form.errors.items():
                    print(f"DEBUG: Field '{field_name}' errors: {errors}")
                    if hasattr(form, field_name):
                        field = form[field_name]
                        print(f"DEBUG: Field '{field_name}' value: {field.value()}")
                        print(f"DEBUG: Field '{field_name}' data: {form.data.get(field_name)}")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': ' '.join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
                    })
                messages.error(request, "Please correct the errors below.")
                # Re-render the form with the submitted data preserved
                form = ProductForm(request.POST, request.FILES, instance=product)
        except Exception as e:
            print(f"DEBUG: Exception in POST processing: {str(e)}")
            import traceback
            print(f"DEBUG: Traceback: {traceback.format_exc()}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': f'خطا در پردازش فرم: {str(e)}'
                })
            messages.error(request, f"خطا در پردازش فرم: {str(e)}")
            # Re-render the form with the submitted data preserved
            form = ProductForm(request.POST, request.FILES, instance=product)
    else:
        # Initialize form with product instance if editing
        if product:
            form = ProductForm(instance=product)
            print(f"DEBUG: Created form with product instance: {product.name}")
        else:
            # Check if a category is selected via URL parameter
            selected_category_id = request.GET.get('category')
            print(f"DEBUG: URL category parameter: {selected_category_id}")
            if selected_category_id:
                try:
                    selected_category = Category.objects.get(id=selected_category_id)
                    form = ProductForm(initial={'category': selected_category})
                    print(f"DEBUG: Created form with initial category: {selected_category.name} (ID: {selected_category.id})")
                except Category.DoesNotExist:
                    form = ProductForm()
                    print(f"DEBUG: Category with ID {selected_category_id} not found, using default form")
            else:
                form = ProductForm()
                print(f"DEBUG: No category selected, using default form")
        
        # Debug: Print form fields to see if dynamic fields were created
        print(f"DEBUG: Form fields after creation: {list(form.fields.keys())}")
        attr_fields = [field for field in form.fields.keys() if field.startswith('attr_')]
        print(f"DEBUG: Dynamic attribute fields created: {attr_fields}")
        print(f"DEBUG: Total dynamic fields: {len(attr_fields)}")
    
    # Get all categories for dropdown
    categories = Category.objects.all()
    print(f"🔍 DEBUG: Total categories found: {categories.count()}")
    
    # Get category attributes for dynamic form
    category_attributes = {}
    for category in categories:
        # Legacy attributes
        # Ensure category is saved before using in related filters
        if not category.pk:
            category.save()
        legacy_attrs = CategoryAttribute.objects.filter(category=category)
        
        print(f"🔍 DEBUG: Category '{category.name}' (ID: {category.id}) has {legacy_attrs.count()} attributes")
        
        legacy_list = [{
            'key': attr.key,
            'required': attr.required,
            'type': attr.type,
            'value': '',
            'source': 'legacy',
            'values': [v.value for v in attr.values.all()]
        } for attr in legacy_attrs]
        
        if legacy_list:
            print(f"✅ DEBUG: Category '{category.name}' attributes: {[attr['key'] for attr in legacy_list]}")

        # Flexible attributes (if subcategory)
        flexible_list = []
        # Remove any code that directly uses SubcategoryAttribute (such as queries, filters, etc.)
        
        category_attributes[category.id] = legacy_list + flexible_list
    
    print(f"🔍 DEBUG: Total categories with attributes: {len([k for k, v in category_attributes.items() if v])}")
    print(f"🔍 DEBUG: Category IDs with attributes: {[k for k, v in category_attributes.items() if v]}")
    
    # Load existing attribute values if editing
    existing_attrs = {}
    if product:
        # Get all product attributes
        product_attrs = ProductAttribute.objects.filter(product=product)
        for attr in product_attrs:
            existing_attrs[attr.key] = attr.value
    
    # Get available tags for each category
    category_tags = {}
    for category in categories:
        tags = Tag.objects.filter(categories=category).values('id', 'name').distinct()
        category_tags[category.id] = list(tags)
    
    # Get currently selected tags if editing
    selected_tags = []
    if product:
        selected_tags = list(product.tags.values_list('id', flat=True).distinct())
    
    # Get current product images if editing
    product_images = []
    if product:
        for img in product.images.all().order_by('order'):
            product_images.append({
                'id': img.id,
                'url': img.image.url,
                'is_primary': img.is_primary,
                'order': img.order
            })
    
    title = _('Edit Product') if product else _('Add Product')
    
    # Get existing variants for the product if editing OR preserve submitted variant data on validation errors
    existing_variants = []
    submitted_variants_data = None
    
    # Check if we have submitted variant data from POST (for validation error preservation)
    if request.method == 'POST':
        variants_data = request.POST.get('variants_data')
        if variants_data:
            try:
                submitted_variants_data = json.loads(variants_data)
                print(f"DEBUG: Preserving submitted variant data: {submitted_variants_data}")
            except Exception as e:
                print(f"DEBUG: Error parsing submitted variant data: {e}")
    
    if product:
        from shop.models import ProductVariant, ProductVariantImage
        variants = ProductVariant.objects.filter(product=product).prefetch_related('images')
        for variant in variants:
            # Get variant images - explicitly filter by variant ID to ensure correct images
            variant_images = []
            try:
                # Explicitly filter by variant ID to ensure we only get images for this specific variant
                images = ProductVariantImage.objects.filter(
                    variant_id=variant.id
                ).order_by('-is_primary', 'order', 'created_at')
                for img in images:
                    # Double-check that the image belongs to this variant
                    if img.image and img.variant_id == variant.id:
                        # Convert image to base64 for frontend
                        import base64
                        try:
                            with open(img.image.path, 'rb') as f:
                                image_data = base64.b64encode(f.read()).decode('utf-8')
                                variant_images.append(f"data:image/jpeg;base64,{image_data}")
                        except Exception as e:
                            print(f"Error reading variant image {img.id} for variant {variant.id} (SKU: {variant.sku}): {e}")
            except Exception as e:
                print(f"Error loading variant images for variant {variant.id} (SKU: {variant.sku}): {e}")
                import traceback
                traceback.print_exc()
            
            existing_variants.append({
                'id': variant.id,
                'sku': variant.sku,
                'attributes': variant.attributes,
                'color': variant.attributes.get('color', ''),
                'size': variant.attributes.get('size', ''),
                'material': variant.attributes.get('material', ''),
                'price_toman': float(variant.price_toman),  # Convert Decimal to float
                'stock_quantity': variant.stock_quantity,
                'is_active': variant.is_active,
                'is_default': getattr(variant, 'is_default', False),  # Handle missing field gracefully
                'images': variant_images  # Add variant images
            })
    elif submitted_variants_data:
        # Use submitted variant data for validation error preservation
        existing_variants = submitted_variants_data
        print(f"DEBUG: Using submitted variant data for preservation: {len(existing_variants)} variants")
    
    # Preserve variant attributes selection on validation errors
    preserved_variant_attributes = None
    if request.method == 'POST':
        variant_attributes = request.POST.get('variant_attributes')
        if variant_attributes:
            try:
                preserved_variant_attributes = json.loads(variant_attributes)
                print(f"DEBUG: Preserving variant attributes selection: {preserved_variant_attributes}")
            except Exception as e:
                print(f"DEBUG: Error parsing preserved variant attributes: {e}")
    
    # Create form for GET requests
    if request.method == 'GET':
        if product:
            print(f"DEBUG: Creating form for GET request (editing product {product.id})")
            form = ProductForm(instance=product)
        else:
            print(f"DEBUG: Creating form for GET request (new product)")
            form = ProductForm()
        print(f"DEBUG: Form created for GET request with {len(form.fields)} fields")
    
    # Preserve supplier parameter in the context for form action URL
    supplier_param = request.GET.get('supplier', '')
    supplier_query = f'?supplier={supplier_param}' if supplier_param else ''
    
    return render(request, 'suppliers/add_product.html', {
        'form': form,
        'product': product,
        'categories': categories,
        'category_attributes': json.dumps(category_attributes),
        'existing_attrs': json.dumps(existing_attrs),
        'category_tags': json.dumps(category_tags),
        'selected_tags': json.dumps(selected_tags),
        'product_images': json.dumps(product_images),
        'existing_variants': existing_variants,  # Pass raw list, not JSON
        'existing_variants_json': json.dumps(existing_variants),  # Keep JSON for JavaScript
        'preserved_variant_attributes': json.dumps(preserved_variant_attributes) if preserved_variant_attributes else '[]',
        'supplier': supplier,
        'is_superuser': request.user.is_superuser,
        'title': title,
        'is_edit': bool(product),
        'supplier_query': supplier_query  # Pass supplier query for form action
    })

@supplier_login_required
def edit_product(request, product_id):
    """Redirect to add_product with product_id as a query parameter"""
    return redirect(f'{reverse("suppliers:add_product")}?product_id={product_id}')

@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        # Get the deletion reason from the form
        deletion_reason = request.POST.get('deletion_reason', '')
        
        # Delete the product using the new method
        product.delete(deleted_by=request.user, deletion_reason=deletion_reason)
        
        messages.success(request, 'محصول با موفقیت حذف شد.')
        return redirect('suppliers:product_list')
    
    return render(request, 'suppliers/delete_product.html', {
        'product': product
    })

@login_required
@supplier_required
def sold_items(request):
    # For superusers, allow viewing all sales or filter by supplier
    if request.user.is_superuser:
        supplier_id = request.GET.get('supplier_id')
        if supplier_id:
            try:
                supplier = Supplier.objects.get(id=supplier_id)
                sold_items = OrderItem.objects.filter(
                    product__supplier=supplier,
                    order__paid=True
                ).select_related('product', 'order').order_by('-order__created')
                
                # Calculate totals for this supplier
                total_sales = sold_items.aggregate(total=Sum('price'))['total'] or 0
                total_items = sold_items.aggregate(total=Sum('quantity'))['total'] or 0
                
                # Get sales by product
                sales_by_product = sold_items.values(
                    'product__name',
                    'product__sku'
                ).annotate(
                    total_quantity=Sum('quantity'),
                    total_revenue=Sum('price')
                ).order_by('-total_quantity')
                
                context = {
                    'sold_items': sold_items,
                    'total_sales': total_sales,
                    'total_items': total_items,
                    'sales_by_product': sales_by_product,
                    'supplier': supplier,
                    'suppliers': Supplier.objects.all(),
                    'is_superuser': True
                }
                return render(request, 'suppliers/sold_items.html', context)
            except Supplier.DoesNotExist:
                pass
        
        # Show all sales for all suppliers
        sold_items = OrderItem.objects.filter(
            order__paid=True
        ).select_related('product', 'order').order_by('-order__created')
        
        # Calculate totals
        total_sales = sold_items.aggregate(total=Sum('price'))['total'] or 0
        total_items = sold_items.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Get sales by product
        sales_by_product = sold_items.values(
            'product__name',
            'product__sku',
            'product__supplier__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('price')
        ).order_by('-total_quantity')
        
        context = {
            'sold_items': sold_items,
            'total_sales': total_sales,
            'total_items': total_items,
            'sales_by_product': sales_by_product,
            'suppliers': Supplier.objects.all(),
            'is_superuser': True
        }
        return render(request, 'suppliers/sold_items.html', context)
    
    # Regular supplier flow - find supplier by email
    try:
        supplier = Supplier.objects.get(email=request.user.email)
    except Supplier.DoesNotExist:
        raise PermissionDenied(_("You don't have permission to access this page."))

    # Get all order items for products belonging to this supplier
    sold_items = OrderItem.objects.filter(
        product__supplier=supplier,
        order__paid=True
    ).select_related('product', 'order').order_by('-order__created')

    # Calculate total sales and items
    total_sales = sold_items.aggregate(total=Sum('price'))['total'] or 0
    total_items = sold_items.aggregate(total=Sum('quantity'))['total'] or 0

    # Get sales by product
    sales_by_product = sold_items.values(
        'product__name',
        'product__sku'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('price')
    ).order_by('-total_quantity')

    context = {
        'sold_items': sold_items,
        'total_sales': total_sales,
        'total_items': total_items,
        'sales_by_product': sales_by_product,
        'supplier': supplier
    }
    return render(request, 'suppliers/sold_items.html', context)

@login_required
def test_add_product(request):
    try:
        supplier = Supplier.objects.get(email=request.user.email)
    except Supplier.DoesNotExist:
        raise PermissionDenied(_("You don't have permission to add products."))
    
    if request.method == 'POST':
        # Debug information
        print("POST request received for test add product")
        print(f"POST data: {request.POST}")
        print(f"FILES data: {request.FILES}")
        
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            print("Form is valid")
            product = form.save(commit=False)
            product.supplier = supplier
            product.save()
            
            # Handle multiple image uploads
            images = request.FILES.getlist('images')
            print(f"Found {len(images)} images")
            if images:
                for i, image in enumerate(images):
                    ProductImage.create(
                        product=product,
                        image=image,
                        is_primary=(i == 0)  # First image is primary
                    )
            
            messages.success(request, _('Product was added successfully.'))
            return redirect('suppliers:dashboard')
        else:
            print(f"Form errors: {form.errors}")
    else:
        form = ProductForm()
    
    return render(request, 'suppliers/test_add_product.html', {
        'form': form,
        'categories': Category.objects.all(),
        'supplier': supplier
    })

@supplier_login_required
def get_category_form_fields(request, category_id):
    """AJAX endpoint to get form fields for a specific category"""
    try:
        category = Category.objects.get(id=category_id)
        
        # Create a form with the category to get the dynamic fields
        form = ProductForm(initial={'category': category})
        
        # Get the dynamic attribute fields
        attr_fields = {}
        for field_name, field in form.fields.items():
            if field_name.startswith('attr_'):
                attr_key = field_name[5:]  # Remove 'attr_' prefix
                attr_fields[attr_key] = {
                    'name': field_name,
                    'label': field.label,
                    'required': field.required,
                    'field_type': field.__class__.__name__,
                    'choices': getattr(field, 'choices', None),
                    'initial': getattr(field, 'initial', None),
                }
        
        return JsonResponse({
            'success': True,
            'category_id': category_id,
            'category_name': category.name,
            'attribute_fields': attr_fields
        })
        
    except Category.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Category not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@supplier_login_required
def bulk_delete_products(request):
    # If user is a superuser, they can delete any products
    if request.user.is_superuser:
        if request.method == 'POST':
            product_ids = request.POST.getlist('product_ids')
            if product_ids:
                products = Product.objects.filter(id__in=product_ids)
                products_count = products.count()
                products.delete()
                messages.success(request, _(f"{products_count} products were deleted successfully."))
            return redirect('shop:admin_products_explorer')
    else:
        # Regular supplier admin flow - use the supplier_required decorator's logic
        def _wrapped_view(request, *args, **kwargs):
            try:
                # Check if the user is a supplier
                supplier = Supplier.objects.get(email=request.user.email)
                
                # Continue with the original view
                if request.method == 'POST':
                    product_ids = request.POST.getlist('product_ids')
                    if product_ids:
                        products = Product.objects.filter(id__in=product_ids, supplier=supplier)
                        products_count = products.count()
                        products.delete()
                        messages.success(request, _(f"{products_count} products were deleted successfully."))
                    return redirect('suppliers:dashboard')
                
                return render(request, 'suppliers/bulk_delete_products.html')
                
            except SupplierAdmin.DoesNotExist:
                raise PermissionDenied(_("You must be a supplier admin to access this page."))
        
        return _wrapped_view(request)

class ProductsExplorerView(SupplierLoginRequiredMixin, ListView):
    model = Product
    template_name = 'suppliers/products_explorer.html'
    context_object_name = 'products'
    paginate_by = 12

    def get_queryset(self):
        # For superusers, show all products
        if self.request.user.is_superuser:
            supplier_id = self.request.GET.get('supplier_id')
            if supplier_id:
                try:
                    supplier = Supplier.objects.get(id=supplier_id)
                    queryset = Product.objects.filter(supplier=supplier)
                except Supplier.DoesNotExist:
                    queryset = Product.objects.all()
            else:
                queryset = Product.objects.all()
        else:
            # For Customer users, find supplier by email directly
            try:
                supplier = Supplier.objects.get(email=self.request.user.email)
            except Supplier.DoesNotExist:
                raise PermissionDenied("You don't have permission to access this page.")
            
            # Start with all products for this supplier
            queryset = Product.objects.filter(supplier=supplier)
        
        # Apply search filter
        query = self.request.GET.get('q', '')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | 
                Q(description__icontains=query) |
                Q(sku__icontains=query)
            )
        
        # Apply category filter
        category_id = self.request.GET.get('category', '')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Apply brand filter
        brand = self.request.GET.get('brand', '')
        if brand:
            queryset = queryset.filter(brand=brand)
        
        # Apply status filter
        status = self.request.GET.get('status', '')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'draft':
            queryset = queryset.filter(draft=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Apply sorting
        sort = self.request.GET.get('sort', 'created_desc')
        if sort == 'created_desc':
            queryset = queryset.order_by('-created_at')
        elif sort == 'created_asc':
            queryset = queryset.order_by('created_at')
        elif sort == 'name_asc':
            queryset = queryset.order_by('name')
        elif sort == 'name_desc':
            queryset = queryset.order_by('-name')
        elif sort == 'price_asc':
            queryset = queryset.order_by('price')
        elif sort == 'price_desc':
            queryset = queryset.order_by('-price')
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all categories
        context['categories'] = Category.objects.all()
        
        # Get all brands
        if self.request.user.is_superuser:
            supplier_id = self.request.GET.get('supplier_id')
            if supplier_id:
                try:
                    supplier = Supplier.objects.get(id=supplier_id)
                    brands = Product.objects.filter(
                        supplier=supplier
                    ).exclude(
                        brand__isnull=True
                    ).exclude(
                        brand__exact=''
                    ).values_list('brand', flat=True).distinct()
                    context['suppliers'] = Supplier.objects.all()
                    context['current_supplier'] = supplier
                except Supplier.DoesNotExist:
                    brands = Product.objects.exclude(
                        brand__isnull=True
                    ).exclude(
                        brand__exact=''
                    ).values_list('brand', flat=True).distinct()
                    context['suppliers'] = Supplier.objects.all()
            else:
                brands = Product.objects.exclude(
                    brand__isnull=True
                ).exclude(
                    brand__exact=''
                ).values_list('brand', flat=True).distinct()
                context['suppliers'] = Supplier.objects.all()
        else:
            try:
                # Get unique brands from supplier's products
                supplier = Supplier.objects.get(email=self.request.user.email)
                
                brands = Product.objects.filter(
                    supplier=supplier
                ).exclude(
                    brand__isnull=True
                ).exclude(
                    brand__exact=''
                ).values_list('brand', flat=True).distinct()
            except SupplierAdmin.DoesNotExist:
                brands = []
        
        context['brands'] = brands
        
        return context

@login_required
def direct_dashboard(request):
    """
    A simplified dashboard view that bypasses most permission checks.
    This is for debugging purposes only.
    """
    print("DEBUG: direct_dashboard called")
    print(f"DEBUG: User: {request.user.username}, is_superuser: {request.user.is_superuser}, is_supplier_admin: {getattr(request.user, 'is_supplier_admin', False)}")
    
    # Get all suppliers
    suppliers = Supplier.objects.all()
    print(f"DEBUG: Found {len(suppliers)} suppliers")
    
    # Get all products
    products = Product.objects.all()
    print(f"DEBUG: Found {len(products)} products")
    
    # Try to get supplier admin for this user
    supplier_admin = None
    supplier = None
    try:
        if hasattr(request.user, 'supplieradmin'):
            supplier_admin = request.user.supplieradmin
            supplier = supplier_admin.supplier
            print(f"DEBUG: Found supplier_admin: {supplier_admin}, supplier: {supplier}")
        else:
            # Try to find supplier by email
            try:
                supplier = Supplier.objects.get(email=request.user.email)
                print(f"DEBUG: Found supplier via email: {supplier}")
            except Supplier.DoesNotExist:
                print("DEBUG: No supplier found for this user email")
    except Exception as e:
        print(f"DEBUG: Error getting supplier_admin: {str(e)}")
    
    # Prepare minimal context
    context = {
        'products': products[:20],  # Limit to first 20
        'categories': Category.objects.all(),
        'total_products': products.count(),
        'total_sales': 0,
        'total_orders': 0,
        'is_superuser': request.user.is_superuser,
        'suppliers': suppliers,
    }
    
    # Add supplier if found
    if supplier:
        context['supplier'] = supplier
    
    print("DEBUG: Rendering dashboard template with minimal context")
    return render(request, 'suppliers/dashboard.html', context)

@login_required
def product_detail_api(request, product_id):
    """API endpoint to get product details in JSON format"""
    try:
        # Get the product
        if request.user.is_superuser:
            product = get_object_or_404(Product, id=product_id)
        else:
            try:
                supplier = Supplier.objects.get(email=request.user.email)
                product = get_object_or_404(Product, id=product_id, supplier=supplier)
            except Supplier.DoesNotExist:
                # If the user isn't a supplier but is still authenticated, just try to get the product
                product = get_object_or_404(Product, id=product_id)
        
        # Start with basic product data that should always be available
        product_data = {
            'id': product.id,
            'name': product.name,
            'description': product.description or '',
            'price': str(product.price),
            'price_toman': float(product.price_toman) if hasattr(product, 'price_toman') and product.price_toman else None,
            'price_usd': float(product.price_usd) if hasattr(product, 'price_usd') and product.price_usd else None,
            'reduced_price_toman': float(product.reduced_price_toman) if hasattr(product, 'reduced_price_toman') and product.reduced_price_toman else None,
            'discount_percentage': float(product.discount_percentage) if hasattr(product, 'discount_percentage') and product.discount_percentage else None,
            'sku': product.sku or '',
            'is_active': product.is_active if hasattr(product, 'is_active') else True,
            'created_at': product.created_at.isoformat() if hasattr(product, 'created_at') else '',
        }
        
        # Add category information if available
        try:
            if hasattr(product, 'category') and product.category is not None:
                product_data['category'] = {
                    'id': product.category.id,
                    'name': product.category.name
                }
            else:
                product_data['category'] = {
                    'id': None,
                    'name': 'Uncategorized'
                }
        except Exception as e:
            print(f"Error getting category: {str(e)}")
            product_data['category'] = {'id': None, 'name': 'Uncategorized'}
        
        # Add supplier information if available
        try:
            if hasattr(product, 'supplier') and product.supplier is not None:
                product_data['supplier'] = {
                    'id': product.supplier.id,
                    'name': product.supplier.name
                }
            else:
                product_data['supplier'] = {
                    'id': None,
                    'name': 'Unknown'
                }
        except Exception as e:
            print(f"Error getting supplier: {str(e)}")
            product_data['supplier'] = {'id': None, 'name': 'Unknown'}
        
        # Add brand
        product_data['brand'] = product.brand if hasattr(product, 'brand') and product.brand else ''
        
        # Add brand image
        try:
            if hasattr(product, 'brand_image') and product.brand_image:
                current_site = request.build_absolute_uri('/').rstrip('/')
                brand_image_url = product.brand_image.url
                if not brand_image_url.startswith(('http://', 'https://')):
                    brand_image_url = f"{current_site}{brand_image_url}"
                product_data['brand_image'] = brand_image_url
            else:
                product_data['brand_image'] = None
        except Exception as e:
            print(f"Error getting brand image: {str(e)}")
            product_data['brand_image'] = None
        
        # Collect product attributes
        attributes = {}
        try:
            # Try to get product attributes from the ProductAttribute model directly
            product_attrs = ProductAttribute.objects.filter(product=product)
            for attr in product_attrs:
                attributes[attr.key] = attr.value
            product_data['attributes'] = attributes
        except Exception as e:
            print(f"Error getting product attributes: {str(e)}")
            product_data['attributes'] = {}
        
        # Collect product images
        images = []
        try:
            if hasattr(product, 'images'):
                for img in product.images.all().order_by('order'):
                    images.append({
                        'id': img.id,
                        'url': img.image.url,
                        'is_primary': img.is_primary if hasattr(img, 'is_primary') else False,
                        'order': img.order if hasattr(img, 'order') else 0
                    })
            product_data['images'] = images
        except Exception as e:
            print(f"Error getting product images: {str(e)}")
            product_data['images'] = []
        
        # Collect tags if available
        tags = []
        try:
            if hasattr(product, 'tags'):
                for tag in product.tags.all():
                    tags.append({
                        'id': tag.id,
                        'name': tag.name
                    })
            product_data['tags'] = tags
        except Exception as e:
            print(f"Error getting product tags: {str(e)}")
            product_data['tags'] = []
        
        return JsonResponse(product_data)
    except Exception as e:
        import traceback
        print(f"Error in product_detail_api: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=400)

def product_debug_api(request, product_id):
    """Simple debug API endpoint that returns minimal product information"""
    try:
        # Get the product without any permission checks
        product = get_object_or_404(Product, id=product_id)
        
        # Return only basic product data
        product_data = {
            'id': product.id,
            'name': product.name,
            'description': product.description or '',
            'price': str(product.price),
            'success': True
        }
        
        return JsonResponse(product_data)
    except Exception as e:
        import traceback
        print(f"Error in product_debug_api: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e), 'success': False}, status=400)

@staff_member_required
def create_backup(request):
    """Create a new database backup"""
    try:
        # Create backup using management command
        call_command('backup_database', user=request.user.id)
        return JsonResponse({
            'status': 'success',
            'message': 'Backup started successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@staff_member_required
def get_backup_status(request):
    """Get the status of recent backups"""
    backups = BackupLog.objects.all().order_by('-started_at')[:10]
    backup_list = []
    
    for backup in backups:
        backup_list.append({
            'id': backup.id,
            'filename': backup.filename,
            'status': backup.status,
            'started_at': backup.started_at.isoformat(),
            'completed_at': backup.completed_at.isoformat() if backup.completed_at else None,
            'file_size': backup.file_size_display,
            'duration': str(backup.duration) if backup.duration else None,
            'error_message': backup.error_message
        })
    
    return JsonResponse({
        'status': 'success',
        'backups': backup_list
    })

@staff_member_required
def download_backup(request, backup_id):
    """Download a backup file"""
    try:
        backup = BackupLog.objects.get(id=backup_id)
        backup_path = os.path.join(settings.BASE_DIR, 'backups', backup.filename)
        
        if not os.path.exists(backup_path):
            return JsonResponse({
                'status': 'error',
                'message': 'Backup file not found'
            }, status=404)
        
        with open(backup_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{backup.filename}"'
            return response
            
    except BackupLog.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Backup not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@staff_member_required
def backup_dashboard(request):
    """Render the backup dashboard"""
    return render(request, 'admin/backup_dashboard.html')

@login_required
def delete_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)
    
    if request.method == 'POST':
        # Get the deletion reason from the form
        deletion_reason = request.POST.get('deletion_reason', '')
        
        # Delete the supplier using the new method
        supplier.delete(deleted_by=request.user, deletion_reason=deletion_reason)
        
        messages.success(request, 'تامین‌کننده با موفقیت حذف شد.')
        return redirect('suppliers:supplier_list')
    
    return render(request, 'suppliers/delete_supplier.html', {
        'supplier': supplier
    })
