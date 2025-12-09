from django.http import JsonResponse
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Category, Product, ProductImage, ProductAttribute, Tag, CategoryAttribute, AttributeValue, Attribute, ProductVariant
from .forms import ProductForm
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
import os
from django.views.generic import ListView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.db.models import Q, Max
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage
import datetime
from pathlib import Path
import subprocess
import psutil
import humanize
from django.views.decorators.cache import never_cache
from .models import ProductAttributeValue

def home(request):
    """Home page view showing featured products and categories."""
    try:
        # Get featured products (active products with images)
        featured_products = Product.objects.filter(
            is_active=True
        ).select_related('category').prefetch_related('images')[:8]  # Limit to 8 featured products
        
        # Get all categories
        categories = Category.objects.all()
        
        # Get latest products
        latest_products = Product.objects.filter(
            is_active=True
        ).select_related('category').prefetch_related('images').order_by('-created_at')[:4]  # Latest 4 products
        
        # Get new arrivals
        try:
            new_arrivals = Product.get_new_arrivals(limit=6)  # Get first 6 new arrivals
        except Exception:
            new_arrivals = []
        
        context = {
            'featured_products': featured_products,
            'categories': categories,
            'latest_products': latest_products,
            'new_arrivals': new_arrivals,
        }
        return render(request, 'shop/home.html', context)
    except Exception as e:
        # If there's an error (database, template, etc.), return a simple response
        from django.http import HttpResponse
        return HttpResponse(f"<h1>Welcome to MyShop</h1><p>App is running. Error loading home page: {str(e)}</p><p><a href='/health/'>Health Check</a></p>", content_type='text/html')

def new_arrivals(request):
    """View showing all new arrivals products."""
    
    # Handle POST requests for admin actions
    if request.method == 'POST' and request.user.is_staff:
        action = request.POST.get('action')
        product_ids = request.POST.getlist('product_ids')
        
        if not product_ids:
            return JsonResponse({'success': False, 'message': 'هیچ محصولی انتخاب نشده است.'})
        
        try:
            if action == 'remove_new_arrival':
                # Remove from new arrivals
                Product.objects.filter(id__in=product_ids).update(is_new_arrival=False)
                return JsonResponse({
                    'success': True, 
                    'message': f'علامت "محصول جدید" از {len(product_ids)} محصول حذف شد.'
                })
                
# Delete functionality removed - only new arrival management allowed
                
            elif action == 'keep_new_arrival':
                # This is a no-op, just for confirmation
                return JsonResponse({
                    'success': True, 
                    'message': f'{len(product_ids)} محصول در لیست محصولات جدید باقی ماند.'
                })
                
            else:
                return JsonResponse({'success': False, 'message': 'عملیات نامعتبر.'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'خطا: {str(e)}'})
    
    # GET request - show the page
    # Get all new arrivals with pagination
    new_arrivals = Product.get_new_arrivals()
    
    # Apply pagination
    paginator = Paginator(new_arrivals, 12)  # 12 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'products': page_obj,
        'title': 'محصولات جدید',
        'is_new_arrivals': True,
    }
    return render(request, 'shop/new_arrivals.html', context)

def api_new_arrivals(request):
    """API endpoint for new arrivals products."""
    limit = request.GET.get('limit', 10)
    try:
        limit = int(limit) if limit else 10
        limit = min(limit, 50)  # Maximum 50 products
    except (ValueError, TypeError):
        limit = 10
    
    new_arrivals = Product.get_new_arrivals(limit=limit)
    
    products_data = []
    for product in new_arrivals:
        # Get primary image
        primary_image = product.images.filter(is_primary=True).first()
        image_url = None
        if primary_image and primary_image.image:
            # Convert relative URL to absolute URL
            image_url = request.build_absolute_uri(primary_image.image.url)
        
        products_data.append({
            'id': product.id,
            'name': product.name,
            'price_toman': float(product.price_toman),
            'price_usd': float(product.price_usd) if product.price_usd else None,
            'description': product.description,
            'category': product.category.name,
            'image': image_url,
            'created_at': product.created_at.timestamp(),
            'is_active': product.is_active,
        })
    
    return JsonResponse({
        'status': 'success',
        'count': len(products_data),
        'products': products_data
    })

@staff_member_required
def admin_new_arrivals(request):
    """Admin view for managing new arrivals."""
    
    # Handle POST requests for actions
    if request.method == 'POST':
        action = request.POST.get('action')
        product_id = request.POST.get('product_id')
        
        if action == 'remove_new_arrival' and product_id:
            try:
                product = Product.objects.get(id=product_id)
                product.unmark_as_new_arrival()
                return JsonResponse({'success': True, 'message': 'علامت جدید از محصول حذف شد.'})
            except Product.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'محصول یافت نشد.'})
        
        return JsonResponse({'success': False, 'message': 'عملیات نامعتبر.'})
    
    # GET request - show the page
    # Get all new arrivals
    new_arrivals = Product.objects.filter(is_new_arrival=True).select_related('category', 'supplier').prefetch_related('images')
    
    # Get statistics
    total_new_arrivals = new_arrivals.count()
    active_new_arrivals = new_arrivals.filter(is_active=True).count()
    
    # Apply pagination
    paginator = Paginator(new_arrivals, 20)  # 20 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'products': page_obj,
        'total_new_arrivals': total_new_arrivals,
        'active_new_arrivals': active_new_arrivals,
        'title': 'مدیریت محصولات جدید',
    }
    return render(request, 'shop/admin_new_arrivals.html', context)

def create_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            
            # Handle multiple image uploads
            images = request.FILES.getlist('images')
            if images:
                for i, image in enumerate(images):
                    ProductImage.create(
                        product=product,
                        image=image,
                        is_primary=(i == 0)  # First image is primary
                    )
            
            messages.success(request, 'محصول با موفقیت ایجاد شد')
            return redirect('admin:shop_product_changelist')
    else:
        form = ProductForm()
    
    return render(request, 'admin/shop/product/create.html', {
        'form': form,
        'categories': Category.objects.all()
    })

@csrf_exempt
def reorder_images(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        for index, image_id in enumerate(data.get('image_ids', [])):
            ProductImage.objects.filter(id=image_id).update(order=index)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


def sort_product_images(request, product_id):
    product = Product.objects.get(id=product_id)
    images = product.images.all()
    return render(request, 'shop/sort_images.html', {'images': product.images.all})

@require_POST
def delete_product_image(request, image_id):
    try:
        image = get_object_or_404(ProductImage, id=image_id)
        product = image.product
        
        # Delete the image file from storage
        if image.image:
            try:
                # Get the full path to the image file
                image_path = image.image.path
                # Delete the file if it exists
                if os.path.isfile(image_path):
                    os.remove(image_path)
            except Exception as e:
                print(f"Error deleting image file: {e}")
        
        # Store the order before deletion for reordering
        deleted_order = image.order
        
        # Delete the database record
        image.delete()
        
        # Reorder remaining images
        remaining_images = ProductImage.objects.filter(product=product).order_by('order')
        for i, img in enumerate(remaining_images):
            if img.order > deleted_order:
                img.order = i + 1
                img.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Image deleted successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_POST
def update_image_order(request, image_id):
    try:
        data = json.loads(request.body)
        image = get_object_or_404(ProductImage, id=image_id)
        image.order = data.get('order', 0)
        image.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@method_decorator(staff_member_required, name='dispatch')
class ProductsExplorerAdminView(ListView):
    model = Product
    template_name = 'suppliers/products_explorer.html'
    context_object_name = 'products'
    paginate_by = 24
    
    def get_queryset(self):
        # Start with all products
        queryset = Product.objects.all()
        
        # Apply search filter
        query = self.request.GET.get('q', '')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | 
                Q(description__icontains=query) |
                Q(sku__icontains=query) |
                Q(supplier__name__icontains=query) |
                Q(supplier__email__icontains=query)
            )
        
        # Apply category filter
        category_id = self.request.GET.get('category', '')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Apply status filter
        status = self.request.GET.get('status', '')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'draft':
            queryset = queryset.filter(draft=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Apply supplier filter (admin-specific)
        supplier_id = self.request.GET.get('supplier', '')
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        
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
        elif sort == 'supplier_asc':
            queryset = queryset.order_by('supplier__name')
        elif sort == 'supplier_desc':
            queryset = queryset.order_by('-supplier__name')
        else:
            queryset = queryset.order_by('-created_at')
        
        # Apply new arrivals filter
        new_arrivals = self.request.GET.get('new_arrivals', '')
        if new_arrivals == 'yes':
            queryset = queryset.filter(is_new_arrival=True)
        elif new_arrivals == 'no':
            queryset = queryset.filter(is_new_arrival=False)
        
        return queryset.select_related('supplier', 'category')

    def post(self, request, *args, **kwargs):
        """Handle POST requests for bulk actions"""
        action = request.POST.get('action')
        product_ids = request.POST.getlist('product_ids')
        
        if action == 'mark_new_arrivals' and product_ids:
            Product.objects.filter(id__in=product_ids).update(is_new_arrival=True)
            messages.success(request, f'{len(product_ids)} محصول به عنوان "محصول جدید" علامت‌گذاری شد.')
        elif action == 'unmark_new_arrivals' and product_ids:
            Product.objects.filter(id__in=product_ids).update(is_new_arrival=False)
            messages.success(request, f'علامت "محصول جدید" از {len(product_ids)} محصول حذف شد.')
        elif action == 'toggle_active' and product_ids:
            for product_id in product_ids:
                product = Product.objects.get(id=product_id)
                product.is_active = not product.is_active
                product.save()
            messages.success(request, f'وضعیت {len(product_ids)} محصول تغییر کرد.')
        
        return redirect(request.get_full_path())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all categories
        context['categories'] = Category.objects.all()
        # Removed brands logic
        # Get all suppliers for admin filtering
        from suppliers.models import Supplier
        suppliers = Supplier.objects.all().order_by('name')
        # Create a list of suppliers
        supplier_list = []
        for supplier in suppliers:
            supplier_list.append({
                'id': supplier.id,
                'name': supplier.name
            })
        # Sort the list by supplier name
        supplier_list.sort(key=lambda x: x['name'].lower())
        context['suppliers'] = supplier_list
        # Save search parameters
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_supplier'] = self.request.GET.get('supplier', '')
        context['selected_category'] = self.request.GET.get('category', '')
        # Removed selected_brand
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_sort'] = self.request.GET.get('sort', 'created_desc')
        context['selected_new_arrivals'] = self.request.GET.get('new_arrivals', '')
        
        # Add new arrivals statistics
        total_products = Product.objects.count()
        new_arrivals_count = Product.objects.filter(is_new_arrival=True).count()
        active_new_arrivals = Product.objects.filter(is_new_arrival=True, is_active=True).count()
        
        context['total_products'] = total_products
        context['new_arrivals_count'] = new_arrivals_count
        context['active_new_arrivals'] = active_new_arrivals
        
        # Set admin flag to customize template behavior
        context['is_admin'] = True
        return context

@staff_member_required
def product_detail(request, product_id):
    """Get product details for the sidebar view in admin."""
    product = get_object_or_404(Product, id=product_id)
    
    # Get product attributes
    attributes = ProductAttribute.objects.filter(product=product)
    attributes_dict = {attr.key: attr.value for attr in attributes}
    
    # Get product variants
    variants = ProductVariant.objects.filter(product=product).order_by('sku')
    variants_data = []
    for variant in variants:
        variants_data.append({
            'id': variant.id,
            'sku': variant.sku,
            'attributes': variant.attributes,
            'color': variant.attributes.get('color', 'نامشخص'),
            'size': variant.attributes.get('size', 'نامشخص'),
            'price_toman': variant.price_toman,
            'stock_quantity': variant.stock_quantity,
            'is_active': variant.is_active,
            'created_at': variant.created_at
        })
    
    # Get product images
    images = ProductImage.objects.filter(product=product).order_by('order', 'created_at')
    
    # Format all product images
    product_images = []
    for image in images:
        try:
            image_url = image.image.url
            if not image_url.startswith(('http://', 'https://')):
                current_site = request.build_absolute_uri('/').rstrip('/')
                image_url = f"{current_site}{image_url}"
            product_images.append({
                'url': image_url,
                'is_primary': image.is_primary
            })
        except Exception as e:
            print(f"Error getting image URL: {e}")
    
    # Get similar products (prefer tag-based, fallback to category-based)
    product_tags = set(product.tags.values_list('id', flat=True))
    
    if product_tags:
        # Use tag-based similarity when tags are available
        from django.db.models import Count, Q
        similar_products = Product.objects.filter(
            tags__in=product_tags,
            is_active=True
        ).exclude(id=product.id).annotate(
            tag_overlap=Count('tags', filter=Q(tags__in=product_tags))
        ).order_by('-tag_overlap', '-created_at')[:4]
    else:
        # Fallback to category-based similarity
        similar_products = Product.objects.filter(
            category=product.category,
            is_active=True
        ).exclude(id=product.id)[:4]
    
    # Format similar products data
    similar_products_data = []
    for similar in similar_products:
        similar_image = ProductImage.objects.filter(product=similar).first()
        image_url = None
        if similar_image and similar_image.image:
            try:
                image_url = similar_image.image.url
                if not image_url.startswith(('http://', 'https://')):
                    current_site = request.build_absolute_uri('/').rstrip('/')
                    image_url = f"{current_site}{image_url}"
            except Exception as e:
                print(f"Error getting similar product image URL: {e}")
        
        # Get tags for similar product
        similar_tags = list(similar.tags.values('id', 'name'))
        
        similar_products_data.append({
            'id': similar.id,
            'name': similar.name,
            'price': str(similar.price),
            'price_toman': float(similar.price_toman) if similar.price_toman else None,
            'reduced_price_toman': float(similar.reduced_price_toman) if similar.reduced_price_toman else None,
            'discount_percentage': float(similar.discount_percentage) if similar.discount_percentage else None,
            'image_url': image_url,
            'tags': similar_tags,
            'similarity_type': 'tags' if product_tags else 'category'
        })
    
    # Get product tags
    tags = product.tags.all().values('id', 'name')
    
    # Return JSON response for API
    data = {
        'id': product.id,
        'name': product.name,
        'price': str(product.price),
        'price_toman': float(product.price_toman) if product.price_toman else None,
        'price_usd': float(product.price_usd) if product.price_usd else None,
        'reduced_price_toman': float(product.reduced_price_toman) if product.reduced_price_toman else None,
        'discount_percentage': float(product.discount_percentage) if product.discount_percentage else None,
        'description': product.description or '',
        'category': str(product.category),
        'supplier': str(product.supplier) if product.supplier else '',
        'is_active': product.is_active,
        'created_at': product.created_at.timestamp(),  # Return as seconds since 1970 for Swift Date
        'attributes': attributes_dict,
        'variants': variants_data,  # Add variants to the response
        'variants_count': len(variants_data),
        'total_stock': sum(v['stock_quantity'] for v in variants_data),
        'images': product_images,
        'similar_products': similar_products_data,
        'tags': list(tags)  # Add tags to the response
    }
    
    return JsonResponse(data)

def get_tags_for_category(request):
    """
    Endpoint to fetch tags for a specific category
    Example: /shop/get_tags_for_category/?category_id=1
    """
    category_id = request.GET.get('category_id')
    if not category_id:
        return JsonResponse({'error': 'Category ID is required'}, status=400)
    
    try:
        tags = Tag.objects.filter(categories__id=category_id).values('id', 'name')
        return JsonResponse({'tags': list(tags)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_popular_tags(request):
    """
    Get popular tags with product counts
    Example: /shop/api/tags/popular/?limit=20&min_products=2
    """
    limit = request.GET.get('limit', 20)
    min_products = request.GET.get('min_products', 2)
    
    try:
        limit = int(limit)
        min_products = int(min_products)
        if limit > 100:  # Prevent excessive queries
            limit = 100
    except ValueError:
        limit = 20
        min_products = 2
    
    try:
        from django.db.models import Count, Q
        
        # Get tags with product counts, ordered by popularity
        popular_tags = Tag.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        ).filter(
            product_count__gte=min_products
        ).order_by('-product_count', 'name')[:limit]
        
        # Format response
        tags_data = []
        for tag in popular_tags:
            tags_data.append({
                'id': tag.id,
                'name': tag.name,
                'slug': tag.slug,
                'product_count': tag.product_count
            })
        
        return JsonResponse({
            'tags': tags_data,
            'total_found': len(tags_data),
            'limit': limit,
            'min_products': min_products
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_tag_suggestions(request):
    """
    Get tag suggestions based on search query
    Example: /shop/api/tags/suggest/?q=راک&limit=10
    """
    query = request.GET.get('q', '')
    limit = request.GET.get('limit', 10)
    
    try:
        limit = int(limit)
        if limit > 50:  # Prevent excessive queries
            limit = 50
    except ValueError:
        limit = 10
    
    if not query or len(query.strip()) < 2:
        return JsonResponse({'error': 'Query must be at least 2 characters long'}, status=400)
    
    try:
        query = query.strip()
        
        # Search for tags that match the query
        from django.db.models import Count, Q
        matching_tags = Tag.objects.filter(
            name__icontains=query
        ).annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        ).order_by('-product_count', 'name')[:limit]
        
        # Format response
        tags_data = []
        for tag in matching_tags:
            tags_data.append({
                'id': tag.id,
                'name': tag.name,
                'slug': tag.slug,
                'product_count': tag.product_count
            })
        
        return JsonResponse({
            'query': query,
            'tags': tags_data,
            'total_found': len(tags_data),
            'limit': limit
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_products_by_tags(request):
    """
    Get products filtered by specific tags
    Example: /shop/api/products/by-tags/?tags=1,2,3&limit=10
    """
    tags = request.GET.get('tags')
    limit = request.GET.get('limit', 20)
    
    try:
        limit = int(limit)
        if limit > 100:  # Prevent excessive queries
            limit = 100
    except ValueError:
        limit = 20
    
    if not tags:
        return JsonResponse({'error': 'Tags parameter is required'}, status=400)
    
    try:
        # Parse tags (comma-separated IDs)
        tag_ids = [int(tid.strip()) for tid in tags.split(',') if tid.strip().isdigit()]
        
        if not tag_ids:
            return JsonResponse({'error': 'Invalid tag IDs provided'}, status=400)
        
        # Get products that have ANY of the specified tags
        from django.db.models import Q
        products = Product.objects.filter(
            tags__id__in=tag_ids,
            is_active=True
        ).distinct().order_by('-created_at')[:limit]
        
        # Format response
        products_data = []
        for product in products:
            # Get primary image
            primary_image = product.images.filter(is_primary=True).first()
            if not primary_image:
                primary_image = product.images.first()
            
            # Get product tags
            product_tags = list(product.tags.values('id', 'name'))
            
            # Get matching tags (tags that were used in the filter)
            matching_tags = [tag for tag in product_tags if tag['id'] in tag_ids]
            
            products_data.append({
                'id': product.id,
                'name': product.name,
                'price_toman': float(product.price_toman),
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'image_url': request.build_absolute_uri(primary_image.image.url) if primary_image else None,
                'tags': product_tags,
                'matching_tags': matching_tags,
                'match_count': len(matching_tags)
            })
        
        return JsonResponse({
            'tags_requested': tag_ids,
            'products': products_data,
            'total_found': len(products_data),
            'limit': limit
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_similar_products_by_tags(request, product_id):
    """
    Get similar products based on tag similarity
    Example: /shop/product/123/similar-by-tags/
    """
    try:
        product = Product.objects.get(id=product_id)
        product_tags = set(product.tags.values_list('id', flat=True))
        
        if not product_tags:
            # Fallback to category-based similarity if no tags
            similar_products = Product.objects.filter(
                category=product.category,
                is_active=True
            ).exclude(id=product.id).order_by('-created_at')[:6]
            
            similar_data = []
            for similar in similar_products:
                similar_image = similar.images.first()
                similar_data.append({
                    'id': similar.id,
                    'name': similar.name,
                    'price_toman': float(similar.price_toman),
                    'price_usd': float(similar.price_usd) if similar.price_usd else None,
                    'image_url': request.build_absolute_uri(similar_image.image.url) if similar_image else None,
                    'tag_overlap': 0,
                    'similarity_type': 'category',
                    'tags': []
                })
        else:
            # Find products with overlapping tags, ordered by tag overlap
            from django.db.models import Count, Q
            
            similar_products = Product.objects.filter(
                tags__in=product_tags,
                is_active=True
            ).exclude(id=product.id).annotate(
                tag_overlap=Count('tags', filter=Q(tags__in=product_tags))
            ).order_by('-tag_overlap', '-created_at')[:6]
            
            # Format response with tag information
            similar_data = []
            for similar in similar_products:
                similar_image = similar.images.first()
                similar_tags = list(similar.tags.values('id', 'name'))
                
                similar_data.append({
                    'id': similar.id,
                    'name': similar.name,
                    'price_toman': float(similar.price_toman),
                    'price_usd': float(similar.price_usd) if similar.price_usd else None,
                    'image_url': request.build_absolute_uri(similar_image.image.url) if similar_image else None,
                    'tag_overlap': getattr(similar, 'tag_overlap', 0),
                    'similarity_type': 'tags',
                    'tags': similar_tags
                })
        
        return JsonResponse({
            'product_id': product_id,
            'product_name': product.name,
            'similar_products': similar_data,
            'total_found': len(similar_data)
        })
        
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_similar_products_by_attributes(request, product_id):
    """
    Get similar products based on attribute overlap
    Example: /shop/product/123/similar-by-attributes/
    """
    try:
        product = Product.objects.get(id=product_id)
        
        # Import the helper function
        from shop.api_views import get_product_attributes
        
        # Get product's attribute values from both systems
        product_attributes = set()
        
        # From new system (attribute_values)
        for attr_value in product.attribute_values.all():
            key = attr_value.attribute.key
            value = attr_value.get_display_value()
            if value and value.strip():
                product_attributes.add((key, value.strip()))
        
        # From legacy system (legacy_attribute_set)
        for attr in product.legacy_attribute_set.all():
            key = attr.key
            value = attr.value
            if value and value.strip():
                product_attributes.add((key, value.strip()))
        
        if not product_attributes:
            # Fallback to category-based similarity if no attributes
            similar_products = Product.objects.filter(
                category=product.category,
                is_active=True
            ).exclude(id=product.id).order_by('-created_at')[:6]
            
            similar_data = []
            for similar in similar_products:
                similar_image = similar.images.first()
                similar_data.append({
                    'id': similar.id,
                    'name': similar.name,
                    'price_toman': float(similar.price_toman),
                    'price_usd': float(similar.price_usd) if similar.price_usd else None,
                    'image_url': request.build_absolute_uri(similar_image.image.url) if similar_image else None,
                    'attribute_overlap': 0,
                    'similarity_type': 'category',
                    'attributes': get_product_attributes(similar)
                })
        else:
            # Find products with overlapping attributes
            from django.db.models import Count, Q
            
            # Build query for attribute overlap
            attribute_conditions = Q()
            for attr_key, attr_value in product_attributes:
                # Match in legacy system
                attribute_conditions |= Q(
                    legacy_attribute_set__key=attr_key, 
                    legacy_attribute_set__value__iexact=attr_value
                )
                # Match in new system (attribute_value)
                attribute_conditions |= Q(
                    attribute_values__attribute__key=attr_key, 
                    attribute_values__attribute_value__value__iexact=attr_value
                )
                # Match in new system (custom_value)
                attribute_conditions |= Q(
                    attribute_values__attribute__key=attr_key, 
                    attribute_values__custom_value__iexact=attr_value
                )
            
            # Count attribute overlaps for scoring
            overlap_conditions = Q()
            for attr_key, attr_value in product_attributes:
                overlap_conditions |= Q(
                    legacy_attribute_set__key=attr_key, 
                    legacy_attribute_set__value__iexact=attr_value
                )
            
            similar_products = Product.objects.filter(
                attribute_conditions,
                is_active=True
            ).exclude(id=product.id).annotate(
                attribute_overlap=Count('legacy_attribute_set', filter=overlap_conditions)
            ).order_by('-attribute_overlap', '-created_at')[:6]
            
            # Format response with attribute information
            similar_data = []
            for similar in similar_products:
                similar_image = similar.images.first()
                similar_attributes = get_product_attributes(similar)
                
                similar_data.append({
                    'id': similar.id,
                    'name': similar.name,
                    'price_toman': float(similar.price_toman),
                    'price_usd': float(similar.price_usd) if similar.price_usd else None,
                    'image_url': request.build_absolute_uri(similar_image.image.url) if similar_image else None,
                    'attribute_overlap': getattr(similar, 'attribute_overlap', 0),
                    'similarity_type': 'attributes',
                    'attributes': similar_attributes
                })
        
        return JsonResponse({
            'product_id': product_id,
            'product_name': product.name,
            'product_attributes': list(product_attributes),
            'similar_products': similar_data,
            'total_found': len(similar_data)
        })
        
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@staff_member_required
@require_POST
def delete_product(request, product_id):
    """Handle product deletion via AJAX"""
    try:
        product = Product.objects.get(id=product_id)
        product_name = str(product)
        product.delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Product "{product_name}" was successfully deleted.'
        })
    except Product.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Product not found.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_http_methods(["GET"])
def api_products(request):
    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 10)
    
    try:
        page = int(page)
        per_page = int(per_page)
    except ValueError:
        return JsonResponse({'error': 'Invalid page or per_page parameter'}, status=400)
    
    products = Product.objects.filter(is_active=True).order_by('-created_at')
    paginator = Paginator(products, per_page)
    
    try:
        products_page = paginator.page(page)
    except:
        return JsonResponse({'error': 'Page not found'}, status=404)
    
    products_data = []
    for product in products_page:
        product_dict = {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price_toman': float(product.price_toman),
            'price_usd': float(product.price_usd) if product.price_usd else None,
            'reduced_price_toman': float(product.reduced_price_toman) if product.reduced_price_toman else None,
            'discount_percentage': float(product.discount_percentage) if product.discount_percentage else None,
            'model': product.model,
            'sku': product.sku,
            'stock_quantity': product.stock_quantity,
            'created_at': product.created_at.timestamp(),  # Return as seconds since 1970 for Swift Date
            'is_in_special_offers': product.is_in_special_offers,
            'images': [],
            'attributes': []
        }
        
        # Add images
        for image in product.images.all():
            product_dict['images'].append({
                'url': request.build_absolute_uri(image.image.url),
                'is_primary': image.is_primary
            })
            
        # Add attributes from new system (attribute_values)
        for attr_value in product.attribute_values.all():
            product_dict['attributes'].append({
                'key': attr_value.attribute.key,
                'value': attr_value.get_display_value()
            })
            
        # Add attributes from legacy system (legacy_attribute_set)
        for legacy_attr in product.legacy_attribute_set.all():
            product_dict['attributes'].append({
                'key': legacy_attr.key,
                'value': legacy_attr.value
            })
            
        products_data.append(product_dict)
    
    return JsonResponse({
        'products': products_data,
        'pagination': {
            'total_pages': paginator.num_pages,
            'current_page': page,
            'total_items': paginator.count,
            'has_next': products_page.has_next(),
            'has_previous': products_page.has_previous(),
        }
    })

@require_http_methods(["GET"])
def api_advanced_search(request):
    """
    Advanced search API endpoint that supports multiple search criteria:
    - Text search in name, description, SKU
    - Price range (min/max) in both Toman and USD
    - Category filter
    - Tag filter
    - Brand filter
    - Attribute filters
    - Stock availability
    - Active status
    """
    try:
        # Start with base queryset
        queryset = Product.objects.select_related('category', 'supplier').prefetch_related('tags', 'attribute_set', 'images')

        # Text search
        search_query = request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(sku__icontains=search_query) |
                Q(model__icontains=search_query)
            )

        # Price range filters
        min_price_toman = request.GET.get('min_price_toman')
        max_price_toman = request.GET.get('max_price_toman')
        min_price_usd = request.GET.get('min_price_usd')
        max_price_usd = request.GET.get('max_price_usd')

        if min_price_toman:
            queryset = queryset.filter(price_toman__gte=min_price_toman)
        if max_price_toman:
            queryset = queryset.filter(price_toman__lte=max_price_toman)
        if min_price_usd:
            queryset = queryset.filter(price_usd__gte=min_price_usd)
        if max_price_usd:
            queryset = queryset.filter(price_usd__lte=max_price_usd)

        # Category filter
        category_id = request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Tag filter
        tags = request.GET.getlist('tags')
        if tags:
            queryset = queryset.filter(tags__id__in=tags).distinct()

        # Stock availability
        in_stock = request.GET.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(stock_quantity__gt=0)
        elif in_stock == 'false':
            queryset = queryset.filter(stock_quantity=0)

        # Active status
        is_active = request.GET.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)

        # Attribute filters
        for key, value in request.GET.items():
            if key.startswith('attr_'):
                attr_key = key[5:]  # Remove 'attr_' prefix
                queryset = queryset.filter(attribute_set__key=attr_key, attribute_set__value=value)

        # Enforce explicit ordering by '-created_at' unless overridden by a sort param
        sort_by = request.GET.get('sort_by')
        valid_sort_fields = {
            'name': 'name',
            '-name': '-name',
            'price': 'price_toman',
            '-price': '-price_toman',
            'date': 'created_at',
            '-date': '-created_at'
        }
        if sort_by:
            sort_field = valid_sort_fields.get(sort_by, '-created_at')
            queryset = queryset.order_by(sort_field)
        else:
            queryset = queryset.order_by('-created_at')

        # Pagination
        page = request.GET.get('page', 1)
        per_page = int(request.GET.get('per_page', 24))
        paginator = Paginator(queryset, per_page)
        
        try:
            products_page = paginator.page(page)
        except:
            products_page = paginator.page(1)

        # Prepare response data
        products_data = []
        for product in products_page:
            product_data = {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price_toman': float(product.price_toman),
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'category': {
                    'id': product.category.id,
                    'name': product.category.name
                },
                'model': product.model,
                'sku': product.sku,
                'stock_quantity': product.stock_quantity,
                'is_active': product.is_active,
                'tags': [{'id': tag.id, 'name': tag.name} for tag in product.tags.all()],
                'attributes': [
                    {'key': attr.key, 'value': attr.value}
                    for attr in product.attribute_set.all()
                ],
                'images': [
                    {
                        'id': img.id,
                        'url': request.build_absolute_uri(img.image.url),
                        'is_primary': img.is_primary
                    }
                    for img in product.images.all()
                ]
            }
            products_data.append(product_data)

        response_data = {
            'products': products_data,
            'pagination': {
                'current_page': products_page.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': products_page.has_next(),
                'has_previous': products_page.has_previous(),
            }
        }

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

@require_http_methods(["GET"])
def api_simple_search(request):
    """
    Flexible product API endpoint that supports:
    - Optional text search in name, description, SKU, brand, and model
    - Category filtering
    - Pagination
    - Sorting by price, date, or name
    - Can be used as search API (with q parameter) or category browsing API (without q parameter)
    """
    try:
        # Get search parameters (optional)
        search_query = request.GET.get('q', '').strip()
        
        # Apply search validation only if search query is provided
        if search_query:
            # 1. Check minimum search length (prevent overly broad searches)
            if len(search_query) < 2:
                return JsonResponse({
                    'error': 'Search query must be at least 2 characters long. Please enter a more specific search term.',
                    'products': [],
                    'pagination': {
                        'current_page': 1,
                        'total_pages': 1,
                        'total_items': 0,
                        'has_next': False,
                        'has_previous': False,
                    }
                }, status=400)
            
            # 2. Check maximum search length (prevent extremely long queries)
            if len(search_query) > 100:
                return JsonResponse({
                    'error': 'Search query too long. Please use a shorter search term (maximum 100 characters).',
                    'products': [],
                    'pagination': {
                        'current_page': 1,
                        'total_pages': 1,
                        'total_items': 0,
                        'has_next': False,
                        'has_previous': False,
                    }
                }, status=400)
            
            # 3. Sanitize search query (remove dangerous characters and normalize)
            suspicious_patterns = ['%', '_', '[', ']', '--', '/*', '*/', 'xp_', 'sp_']
            if any(pattern in search_query.lower() for pattern in suspicious_patterns):
                return JsonResponse({
                    'error': 'Search query contains invalid characters. Please use only letters, numbers, and basic punctuation.',
                    'products': [],
                    'pagination': {
                        'current_page': 1,
                        'total_pages': 1,
                        'total_items': 0,
                        'has_next': False,
                        'has_previous': False,
                    }
                }, status=400)
        
        # Handle pagination parameters with proper error handling
        try:
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 24))
        except (ValueError, TypeError):
            return JsonResponse({
                'error': 'Invalid page or per_page parameter. Both must be positive integers.',
                'pagination': {
                    'current_page': 1,
                    'total_pages': 1,
                    'total_items': 0,
                    'has_next': False,
                    'has_previous': False,
                }
            }, status=400)
        
        # Validate page and per_page values
        if page < 1 or per_page < 1:
            return JsonResponse({
                'error': 'Page and per_page must be positive integers greater than 0.',
                'pagination': {
                    'current_page': page,
                    'total_pages': 1,
                    'total_items': 0,
                    'has_next': False,
                    'has_previous': False,
                }
            }, status=400)
        
        # SECURITY: Limit maximum results per page to prevent abuse
        if per_page > 100:
            return JsonResponse({
                'error': 'Maximum items per page is 100. Please use a smaller per_page value.',
                'pagination': {
                    'current_page': page,
                    'total_pages': 1,
                    'total_items': 0,
                    'has_next': False,
                    'has_previous': False,
                }
            }, status=400)
        
        # SECURITY: Limit maximum page number to prevent deep pagination abuse
        if page > 1000:
            return JsonResponse({
                'error': 'Page number too high. Please use a page number between 1 and 1000.',
                'pagination': {
                    'current_page': page,
                    'total_pages': 1,
                    'total_items': 0,
                    'has_next': False,
                    'has_previous': False,
                }
            }, status=400)
        
        sort_by = request.GET.get('sort_by', 'created_at')  # Default sort by newest first
        sort_order = request.GET.get('sort_order', 'desc')  # Default sort order
        use_fuzzy = request.GET.get('fuzzy', 'true').lower() == 'true'  # Enable fuzzy by default
        
        # Handle legacy sort_by values for backward compatibility
        if sort_by == 'price':
            sort_by = 'price_toman'
        elif sort_by == 'date':
            sort_by = 'created_at'
        elif sort_by.startswith('-'):
            # Handle legacy negative prefixes
            if sort_by == '-price':
                sort_by = 'price_toman'
                sort_order = 'desc'
            elif sort_by == '-date':
                sort_by = 'created_at'
                sort_order = 'desc'
            elif sort_by == '-name':
                sort_by = 'name'
                sort_order = 'desc'
            else:
                sort_by = 'created_at'
                sort_order = 'desc'
        
        # Validate sort_by parameter
        valid_sort_fields = ['created_at', 'price_toman', 'price_usd', 'name']
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'  # Default to created_at if invalid
        
        # Apply sorting
        if sort_by == 'created_at':
            if sort_order == 'asc':
                sort_field = 'created_at'
            else:
                sort_field = '-created_at'
        elif sort_by == 'price_toman':
            if sort_order == 'asc':
                sort_field = 'price_toman'
            else:
                sort_field = '-price_toman'
        elif sort_by == 'price_usd':
            if sort_order == 'asc':
                sort_field = 'price_usd'
            else:
                sort_field = '-price_usd'
        elif sort_by == 'name':
            if sort_order == 'asc':
                sort_field = 'name'
            else:
                sort_field = '-name'
        else:
            # Default sorting by created_at desc
            sort_field = '-created_at'
        
        # Start with base queryset
        queryset = Product.objects.filter(is_active=True).prefetch_related('images', 'attribute_values', 'attribute_values__attribute')
        
        # Apply category filter
        category_id = request.GET.get('category')
        if category_id:
            print(f"DEBUG: Filtering by category ID: {category_id}")
            queryset = queryset.filter(category_id=category_id)
            print(f"DEBUG: Products after category filter: {queryset.count()}")
        
        # Apply search if query exists
        if search_query:
            # First try exact matching including tags
            exact_queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(sku__icontains=search_query) |
                Q(model__icontains=search_query) |
                Q(tags__name__icontains=search_query)  # Add tag-based search
            )
            
            # If no results and fuzzy matching is enabled, try fuzzy matching
            if exact_queryset.count() == 0 and use_fuzzy:
                from django.db import connection
                if connection.vendor == 'postgresql':
                    from django.contrib.postgres.search import TrigramSimilarity
                    queryset = queryset.annotate(
                        name_similarity=TrigramSimilarity('name', search_query),
                        model_similarity=TrigramSimilarity('model', search_query),
                        sku_similarity=TrigramSimilarity('sku', search_query)
                    ).filter(
                        Q(name_similarity__gt=0.3) |
                        Q(model_similarity__gt=0.3) |
                        Q(sku_similarity__gt=0.3)
                    ).order_by(
                        '-name_similarity',
                        '-model_similarity',
                        '-sku_similarity'
                    )
                else:
                    # For non-PostgreSQL databases, try to find products by tag names
                    queryset = queryset.filter(
                        Q(tags__name__icontains=search_query)
                    ).distinct()
            else:
                queryset = exact_queryset
        
        # Apply sorting (only if not using fuzzy matching)
        if not (use_fuzzy and search_query and exact_queryset.count() == 0):
            queryset = queryset.order_by(sort_field)
        else:
            queryset = queryset.order_by('-created_at')
        
        # FINAL SECURITY CHECK: Limit total results to prevent massive data dumps
        total_results = queryset.count()
        if total_results > 10000:
            return JsonResponse({
                'error': f'Search returned too many results ({total_results:,} products). Please use a more specific search term to narrow down results.',
                'products': [],
                'pagination': {
                    'current_page': 1,
                    'total_pages': 1,
                    'total_items': total_results,
                    'has_next': False,
                    'has_previous': False,
                }
            }, status=400)
        
        # Apply pagination
        paginator = Paginator(queryset, per_page)
        
        try:
            products_page = paginator.page(page)
        except (ValueError, TypeError):
            # Invalid page number (non-integer or negative)
            return JsonResponse({
                'error': 'Invalid page number. Page must be a positive integer.',
                'pagination': {
                    'current_page': 1,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'has_next': paginator.num_pages > 1,
                    'has_previous': False,
                }
            }, status=400)
        except EmptyPage:
            # Page number is out of range
            return JsonResponse({
                'error': f'Page {page} does not exist. Available pages: 1 to {paginator.num_pages}',
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'has_next': False,
                    'has_previous': paginator.num_pages > 0,
                }
            }, status=404)
        
        # Prepare response data
        products_data = []
        for product in products_page:
            # Get all images for the product
            images = []
            for image in product.images.all().order_by('-is_primary', 'order'):
                images.append({
                    'id': image.id,
                    'url': request.build_absolute_uri(image.image.url),
                    'is_primary': image.is_primary,
                    'order': image.order
                })
            
            # If no direct product images, try to get from variants
            if not images:
                variants = ProductVariant.objects.filter(product=product, is_active=True).order_by('sku')
                default_variant = variants.filter(is_default=True).first()
                if not default_variant:
                    default_variant = variants.first()
                
                if default_variant:
                    first_variant_image = default_variant.images.first()
                    if first_variant_image and first_variant_image.image:
                        images.append({
                            'id': first_variant_image.id,
                            'url': request.build_absolute_uri(first_variant_image.image.url),
                            'is_primary': True,
                            'order': first_variant_image.order if hasattr(first_variant_image, 'order') else 1
                        })
            
            # --- Populate attributes using attribute_values and legacy_attribute_set ---
            # Only include attributes defined for the product's category, using new system first, then legacy fallback
            attributes = []
            if product.category:
                allowed_keys = list(product.category.category_attributes.values_list('key', flat=True))
                for key in allowed_keys:
                    value = None
                    # Try new system (ProductAttributeValue)
                    pav = product.attribute_values.filter(attribute__key=key).first()
                    if pav and hasattr(pav, 'get_display_value') and pav.get_display_value():
                        value = pav.get_display_value()
                    else:
                        # Fallback to legacy
                        legacy = product.legacy_attribute_set.filter(key=key).first()
                        if legacy and legacy.value:
                            value = legacy.value
                    # Always add the attribute if a value is found
                    if value is not None and value != "":
                        attributes.append({'key': key, 'value': value})
                # Ensure 'brand' is always included if it is a category attribute and has a value
                if 'brand' in allowed_keys and not any(attr['key'] == 'brand' for attr in attributes):
                    # Always fetch brand from attribute_values or legacy_attribute_set
                    brand_value = None
                    pav = product.attribute_values.filter(attribute__key='brand').first()
                    if pav and hasattr(pav, 'get_display_value') and pav.get_display_value():
                        brand_value = pav.get_display_value()
                    else:
                        legacy = product.legacy_attribute_set.filter(key='brand').first()
                        if legacy and legacy.value:
                            brand_value = legacy.value
                    if brand_value:
                        attributes.append({'key': 'brand', 'value': brand_value})
            
            # Remove 'brand' and rename 'برند' to 'brand'
            new_attributes = []
            for attr in attributes:
                if attr['key'] == 'برند':
                    attr['key'] = 'brand'
                new_attributes.append(attr)
            attributes = new_attributes
            
            # Remove any 'brand' from attributes (to avoid duplicates)
            attributes = [attr for attr in attributes if attr['key'] != 'brand']
            # Add 'brand' from flexible attributes only (never from product.brand)
            brand_value = None
            pav = product.attribute_values.filter(attribute__key='brand').first()
            if pav and hasattr(pav, 'get_display_value') and pav.get_display_value():
                brand_value = pav.get_display_value()
            else:
                legacy = product.legacy_attribute_set.filter(key='brand').first()
                if legacy and legacy.value:
                    brand_value = legacy.value
            if brand_value:
                attributes.append({'key': 'brand', 'value': brand_value})
            
            product_data = {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price_toman': float(product.price_toman),
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'model': product.model,
                'sku': product.sku,
                'stock_quantity': product.stock_quantity,
                'images': images,
                'attributes': attributes,
                'created_at': product.created_at.timestamp(),  # Return as timestamp for Swift Date
            }
            
            # Add brand image if available
            if hasattr(product, 'brand_image') and product.brand_image:
                current_site = request.build_absolute_uri('/').rstrip('/')
                brand_image_url = product.brand_image.url
                if not brand_image_url.startswith(('http://', 'https://')):
                    brand_image_url = f"{current_site}{brand_image_url}"
                product_data['brand_image'] = brand_image_url
            else:
                product_data['brand_image'] = None
            
            # Add similarity scores if using fuzzy matching
            if use_fuzzy and search_query and exact_queryset.count() == 0:
                product_data['similarity_scores'] = {
                    'name': float(getattr(product, 'name_similarity', 0)),
                    'model': float(getattr(product, 'model_similarity', 0)),
                    'sku': float(getattr(product, 'sku_similarity', 0))
                }
            
            products_data.append(product_data)
        
        response_data = {
            'products': products_data,
            'pagination': {
                'current_page': products_page.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': products_page.has_next(),
                'has_previous': products_page.has_previous(),
            },
            'sorting_applied': {
                'sort_by': sort_by,
                'sort_order': sort_order
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

@staff_member_required
@never_cache
def backup_logs(request):
    """Enhanced view for monitoring database backup logs with statistics"""
    log_file = "/var/log/postgres_backup.log"
    backup_dir = "/backups"
    
    # Get backup logs
    logs = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = f.readlines()[-100:]  # Get last 100 lines
    
    # Get backup files with enhanced information
    backup_files = []
    total_size = 0
    if os.path.exists(backup_dir):
        for f in Path(backup_dir).glob('backup-*.sql.gz'):
            size = f.stat().st_size
            total_size += size
            backup_files.append({
                'name': f.name,
                'size': size,
                'size_human': humanize.naturalsize(size),
                'date': datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'age_days': (datetime.datetime.now() - datetime.datetime.fromtimestamp(f.stat().st_mtime)).days
            })
    
    # Sort backups by date
    backup_files.sort(key=lambda x: x['date'], reverse=True)
    
    # Get system statistics
    disk_usage = psutil.disk_usage(backup_dir)
    system_stats = {
        'disk_total': humanize.naturalsize(disk_usage.total),
        'disk_used': humanize.naturalsize(disk_usage.used),
        'disk_free': humanize.naturalsize(disk_usage.free),
        'disk_percent': disk_usage.percent,
        'backup_count': len(backup_files),
        'total_backup_size': humanize.naturalsize(total_size)
    }
    
    # Get backup statistics
    backup_stats = {
        'success_count': sum(1 for log in logs if 'Backup completed successfully' in log),
        'error_count': sum(1 for log in logs if 'ERROR' in log),
        'last_success': next((log for log in reversed(logs) if 'Backup completed successfully' in log), 'Never'),
        'last_error': next((log for log in reversed(logs) if 'ERROR' in log), 'None')
    }
    
    context = {
        'logs': logs,
        'backup_files': backup_files,
        'log_file': log_file,
        'backup_dir': backup_dir,
        'system_stats': system_stats,
        'backup_stats': backup_stats
    }
    
    return render(request, 'shop/backup_logs.html', context)

@staff_member_required
@require_POST
def delete_backup(request, filename):
    """Delete a specific backup file"""
    backup_path = os.path.join('/backups', filename)
    if os.path.exists(backup_path):
        try:
            os.remove(backup_path)
            messages.success(request, f'Backup {filename} deleted successfully')
        except Exception as e:
            messages.error(request, f'Error deleting backup: {str(e)}')
    else:
        messages.error(request, 'Backup file not found')
    return redirect('backup_logs')

@staff_member_required
def download_backup(request, filename):
    """Download a specific backup file"""
    backup_path = os.path.join('/backups', filename)
    if os.path.exists(backup_path):
        with open(backup_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/gzip')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    return HttpResponse('Backup file not found', status=404)

@staff_member_required
@require_POST
def trigger_backup(request):
    """Manually trigger a backup"""
    try:
        # Execute the backup script
        result = subprocess.run(['/usr/local/bin/backup_postgres.sh'], 
                              capture_output=True, 
                              text=True)
        
        if result.returncode == 0:
            messages.success(request, 'Backup triggered successfully')
        else:
            messages.error(request, f'Backup failed: {result.stderr}')
    except Exception as e:
        messages.error(request, f'Error triggering backup: {str(e)}')
    
    return redirect('backup_logs')

@staff_member_required
def get_backup_status(request):
    """API endpoint for real-time backup status"""
    log_file = "/var/log/postgres_backup.log"
    backup_dir = "/backups"
    
    # Get latest logs
    logs = []
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = f.readlines()[-10:]  # Get last 10 lines
    
    # Get backup files
    backup_files = []
    if os.path.exists(backup_dir):
        backup_files = sorted([
            {
                'name': f.name,
                'size': humanize.naturalsize(f.stat().st_size),
                'date': datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            }
            for f in Path(backup_dir).glob('backup-*.sql.gz')
        ], key=lambda x: x['date'], reverse=True)
    
    return JsonResponse({
        'logs': logs,
        'backup_files': backup_files,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

def api_categories(request):
    """
    Returns all categories (main and subcategories) with their id, name, parent (id and name if exists),
    and a list of subcategories (id and name).
    """
    from .models import Category
    from django.http import JsonResponse

    categories = Category.objects.all()
    data = []
    for cat in categories:
        parent_obj = None
        if cat.parent:
            parent_obj = {
                'id': cat.parent.id,
                'name': cat.parent.name
            }
        subcats = cat.subcategories.all()
        subcategories_list = [
            {
                'id': sub.id, 
                'name': sub.name,
                'label': sub.get_display_name(),
                'gender': sub.get_gender()
            } for sub in subcats
        ]
        data.append({
            'id': cat.id,
            'name': cat.name,
            'label': cat.get_display_name(),
            'parent': parent_obj,
            'subcategories': subcategories_list,
        })
    return JsonResponse({'categories': data})

def search_page(request):
    """
    Search page with category filtering
    """
    # Get search parameters
    search_query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 12))
    sort_by = request.GET.get('sort_by', '-created_at')
    
    # Get all categories for the filter dropdown
    categories = Category.objects.all().order_by('name')
    
    # Build search URL
    search_params = {}
    if search_query:
        search_params['q'] = search_query
    if category_id:
        search_params['category'] = category_id
    if page != 1:
        search_params['page'] = page
    if per_page != 12:
        search_params['per_page'] = per_page
    if sort_by != '-created_at':
        search_params['sort_by'] = sort_by
    
    # Get selected category name
    selected_category = None
    if category_id:
        try:
            selected_category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            pass
    
    context = {
        'search_query': search_query,
        'categories': categories,
        'selected_category': selected_category,
        'selected_category_id': category_id,
        'current_page': int(page),
        'per_page': per_page,
        'sort_by': sort_by,
        'search_params': search_params,
    }
    
    return render(request, 'shop/search.html', context)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def manage_category_attributes(request, category_id):
    """
    Beautiful interface for managing category attributes
    """
    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return JsonResponse({'error': 'Category not found'}, status=404)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'add_attribute':
                # Add new attribute
                key = data.get('key', '').strip()
                label_fa = data.get('label_fa', '').strip()
                attr_type = data.get('type', 'text')
                required = data.get('required', False)
                is_displayed_in_product = data.get('is_displayed_in_product', True)
                display_in_basket = data.get('display_in_basket', False)
                display_order = data.get('display_order', 0)
                
                if not key or not label_fa:
                    return JsonResponse({
                        'error': 'Key and label are required'
                    }, status=400)
                
                # Check if attribute already exists
                if CategoryAttribute.objects.filter(category=category, key=key).exists():
                    return JsonResponse({
                        'error': f'Attribute "{key}" already exists for this category'
                    }, status=400)
                
                # Create new attribute
                attr = CategoryAttribute.objects.create(
                    category=category,
                    key=key,
                    label_fa=label_fa,
                    type=attr_type,
                    required=required,
                    is_displayed_in_product=is_displayed_in_product,
                    display_in_basket=display_in_basket,
                    display_order=display_order
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Attribute "{key}" added successfully',
                    'attribute': {
                        'id': attr.id,
                        'key': attr.key,
                        'label_fa': attr.label_fa,
                        'type': attr.type,
                        'required': attr.required,
                        'display_order': attr.display_order
                    }
                })
                
            elif action == 'update_attribute':
                # Update existing attribute
                attr_id = data.get('id')
                try:
                    attr = CategoryAttribute.objects.get(id=attr_id, category=category)
                except CategoryAttribute.DoesNotExist:
                    return JsonResponse({'error': 'Attribute not found'}, status=404)
                
                # Update fields
                if 'key' in data:
                    new_key = data['key'].strip()
                    if new_key and new_key != attr.key:
                        # Check if new key already exists
                        if CategoryAttribute.objects.filter(category=category, key=new_key).exclude(id=attr_id).exists():
                            return JsonResponse({'error': f'Attribute key "{new_key}" already exists'}, status=400)
                        attr.key = new_key
                
                if 'label_fa' in data:
                    attr.label_fa = data['label_fa'].strip()
                if 'type' in data:
                    attr.type = data['type']
                if 'required' in data:
                    attr.required = data['required']
                if 'is_displayed_in_product' in data:
                    attr.is_displayed_in_product = data['is_displayed_in_product']
                if 'display_in_basket' in data:
                    attr.display_in_basket = data['display_in_basket']
                if 'display_order' in data:
                    attr.display_order = data['display_order']
                
                attr.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Attribute "{attr.key}" updated successfully',
                    'attribute': {
                        'id': attr.id,
                        'key': attr.key,
                        'label_fa': attr.label_fa,
                        'type': attr.type,
                        'required': attr.required,
                        'display_order': attr.display_order
                    }
                })
                
            elif action == 'delete_attribute':
                # Delete attribute
                attr_id = data.get('id')
                try:
                    attr = CategoryAttribute.objects.get(id=attr_id, category=category)
                    attr_name = attr.key
                    attr.delete()
                    return JsonResponse({
                        'success': True,
                        'message': f'Attribute "{attr_name}" deleted successfully'
                    })
                except CategoryAttribute.DoesNotExist:
                    return JsonResponse({'error': 'Attribute not found'}, status=404)
                    
            elif action == 'reorder_attributes':
                # Reorder attributes
                order_data = data.get('order', [])
                for item in order_data:
                    attr_id = item.get('id')
                    new_order = item.get('order')
                    try:
                        attr = CategoryAttribute.objects.get(id=attr_id, category=category)
                        attr.display_order = new_order
                        attr.save()
                    except CategoryAttribute.DoesNotExist:
                        continue
                
                return JsonResponse({
                    'success': True,
                    'message': 'Attributes reordered successfully'
                })
                
            elif action == 'toggle_display_in_product':
                # Toggle display in product view
                attr_id = data.get('id')
                is_displayed = data.get('is_displayed_in_product', True)
                
                try:
                    attr = CategoryAttribute.objects.get(id=attr_id, category=category)
                    attr.is_displayed_in_product = is_displayed
                    attr.save()
                    
                    status_text = 'نمایش در محصول' if is_displayed else 'مخفی از محصول'
                    return JsonResponse({
                        'success': True,
                        'message': f'ویژگی "{attr.key}" حالا {status_text} است'
                    })
                except CategoryAttribute.DoesNotExist:
                    return JsonResponse({'error': 'Attribute not found'}, status=404)
                
            elif action == 'toggle_display_in_basket':
                # Toggle display in basket
                attr_id = data.get('id')
                display_in_basket = data.get('display_in_basket', False)
                
                try:
                    attr = CategoryAttribute.objects.get(id=attr_id, category=category)
                    attr.display_in_basket = display_in_basket
                    attr.save()
                    
                    status_text = 'نمایش در سبد' if display_in_basket else 'مخفی از سبد'
                    return JsonResponse({
                        'success': True,
                        'message': f'ویژگی "{attr.key}" حالا {status_text} است'
                    })
                except CategoryAttribute.DoesNotExist:
                    return JsonResponse({'error': 'Attribute not found'}, status=404)
                
            else:
                return JsonResponse({'error': 'Invalid action'}, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET request - render the management interface
    attributes = CategoryAttribute.objects.filter(category=category).order_by('display_order', 'key')
    
    # Get attribute values for each attribute
    for attr in attributes:
        attr.values_list = list(AttributeValue.objects.filter(attribute=attr).order_by('display_order', 'value'))
    
    context = {
        'category': category,
        'attributes': attributes,
        'attribute_types': CategoryAttribute.ATTRIBUTE_TYPES,
    }
    
    return render(request, 'shop/manage_category_attributes.html', context)

@require_http_methods(["GET"])
def api_category_attributes(request, category_id):
    """
    Returns all attributes for a given category (e.g., ساعت) as a list of dicts keyed by attribute key.
    Example response:
    {
        "category": {"id": 1, "name": "ساعت"},
        "attributes": [
            {
                "key": "نوع موومنت",
                "type": "select",
                "required": true,
                "display_order": 0,
                "label_fa": "نوع موومنت",
                "values": ["کوارتز", "اتوماتیک", "دستی"]
            },
            ...
        ]
    }
    """
    try:
        category = Category.objects.get(id=category_id)
        attributes = CategoryAttribute.objects.filter(category=category).order_by('display_order', 'key')
        attributes_data = []
        for attr in attributes:
            values = list(attr.values.order_by('display_order', 'value').values_list('value', flat=True))
            attributes_data.append({
                'key': attr.key,
                'type': attr.type,
                'required': attr.required,
                'display_order': attr.display_order,
                'label_fa': attr.label_fa,
                'values': values
            })
        return JsonResponse({
            'category': {'id': category.id, 'name': category.name},
            'attributes': attributes_data
        })
    except Category.DoesNotExist:
        return JsonResponse({'error': 'Category not found'}, status=404)


# Wishlist Views
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from .models import Wishlist

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def add_to_wishlist(request):
    """Add a product to user's wishlist."""
    try:
        # Check if request has JSON content
        if not request.body:
            return JsonResponse({
                'success': False,
                'error': 'Request body is required',
                'message': 'لطفاً اطلاعات محصول را ارسال کنید'
            }, status=400)
        
        # Parse JSON data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON format',
                'message': 'فرمت JSON نامعتبر است'
            }, status=400)
        
        # Validate product_id
        product_id = data.get('product_id')
        if not product_id:
            return JsonResponse({
                'success': False,
                'error': 'Product ID is required',
                'message': 'شناسه محصول الزامی است'
            }, status=400)
        
        # Validate product_id is a number
        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Product ID must be a valid number',
                'message': 'شناسه محصول باید عدد معتبر باشد'
            }, status=400)
        
        # Get the product
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Product not found',
                'message': 'محصول مورد نظر یافت نشد'
            }, status=404)
        
        # Check if user is trying to add their own product (optional business logic)
        if hasattr(product, 'supplier') and product.supplier and product.supplier.user == request.user:
            return JsonResponse({
                'success': False,
                'error': 'Cannot add own product to wishlist',
                'message': 'نمی‌توانید محصول خود را به لیست علاقه‌مندی اضافه کنید'
            }, status=400)
        
        # Create or get wishlist item
        wishlist_item, created = Wishlist.objects.get_or_create(
            customer=request.user,
            product=product
        )
        
        if created:
            return JsonResponse({
                'success': True,
                'message': 'محصول به لیست علاقه‌مندی اضافه شد',
                'added': True,
                'product_id': product_id,
                'product_name': product.name,
                'wishlist_id': wishlist_item.id,
                'timestamp': wishlist_item.created_at.isoformat()
            }, status=201)
        else:
            return JsonResponse({
                'success': True,
                'message': 'محصول در لیست علاقه‌مندی شما موجود است',
                'added': False,
                'product_id': product_id,
                'product_name': product.name,
                'wishlist_id': wishlist_item.id,
                'timestamp': wishlist_item.created_at.isoformat()
            }, status=200)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Internal server error',
            'message': 'خطای داخلی سرور',
            'details': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def remove_from_wishlist(request):
    """Remove a product from user's wishlist."""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        
        if not product_id:
            return JsonResponse({'error': 'Product ID is required'}, status=400)
        
        try:
            wishlist_item = Wishlist.objects.get(
                customer=request.user,
                product_id=product_id
            )
            wishlist_item.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'محصول از لیست علاقه‌مندی حذف شد',
                'removed': True
            })
            
        except Wishlist.DoesNotExist:
            return JsonResponse({
                'success': True,
                'message': 'محصول در لیست علاقه‌مندی شما موجود نیست',
                'removed': False
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def wishlist_view(request):
    """Display user's wishlist."""
    wishlist_items = Wishlist.objects.filter(
        customer=request.user
    ).select_related('product', 'product__category').prefetch_related('product__images').order_by('-created_at')
    
    # Add pagination
    paginator = Paginator(wishlist_items, 12)  # Show 12 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'wishlist_items': page_obj,
        'total_items': wishlist_items.count(),
    }
    
    return render(request, 'shop/wishlist.html', context)


@login_required
def get_wishlist_status(request):
    """Get wishlist status for multiple products (for showing heart icons)."""
    product_ids = request.GET.getlist('product_ids')
    
    if not product_ids:
        return JsonResponse({'error': 'Product IDs are required'}, status=400)
    
    try:
        # Convert to integers
        product_ids = [int(pid) for pid in product_ids if pid.isdigit()]
        
        # Get wishlist status for all products
        wishlist_items = Wishlist.objects.filter(
            customer=request.user,
            product_id__in=product_ids
        ).values_list('product_id', flat=True)
        
        wishlist_status = {
            str(pid): pid in wishlist_items 
            for pid in product_ids
        }
        
        return JsonResponse({
            'success': True,
            'wishlist_status': wishlist_status
        })
        
    except ValueError:
        return JsonResponse({'error': 'Invalid product IDs'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def product_list_with_wishlist(request):
    """Product list view with wishlist status for authenticated users."""
    products = Product.objects.filter(is_active=True).select_related('category').prefetch_related('images')
    
    # Apply filters
    category_id = request.GET.get('category')
    search_query = request.GET.get('search')
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Add wishlist status for authenticated users
    if request.user.is_authenticated:
        products = products.annotate(
            is_in_wishlist=Exists(
                Wishlist.objects.filter(
                    customer=request.user,
                    product=OuterRef('pk')
                )
            )
        )
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj,
        'categories': Category.objects.all(),
        'current_category': category_id,
        'search_query': search_query,
    }
    
    return render(request, 'shop/product_list.html', context)

def public_product_detail(request, product_id):
    """Get public product details for API"""
    try:
        product = Product.objects.select_related(
            'category', 'supplier'
        ).prefetch_related(
            'images',
            'attribute_values',
            'attribute_values__attribute',
            'legacy_attribute_set',
            'tags'
        ).get(id=product_id, is_active=True)
        
        # Prepare product images
        product_images = []
        for image in product.images.all():
            try:
                image_url = request.build_absolute_uri(image.image.url)
                product_images.append({
                    'id': image.id,
                    'url': image_url,
                    'is_primary': image.is_primary
                })
            except Exception as e:
                print(f"Error getting image URL: {e}")
        
        # Prepare attributes (new system)
        new_attributes = []
        for attr_value in product.attribute_values.all():
            new_attributes.append({
                'key': attr_value.attribute.key,
                'key_fa': attr_value.attribute.label_fa,
                'value': attr_value.get_display_value(),
                'type': attr_value.attribute.type
            })
        
        # Build attributes list (non-empty, category-allowed), preferring new system values
        combined_attributes = []
        allowed_keys = []
        # Get CategoryAttribute mapping for display names
        category_attributes_map = {}
        if product.category:
            allowed_keys = list(product.category.category_attributes.values_list('key', flat=True))
            category_attrs = CategoryAttribute.objects.filter(category=product.category)
            category_attributes_map = {ca.key: ca for ca in category_attrs}
        for key in allowed_keys:
            value = None
            # Prefer new system (ProductAttributeValue)
            pav = product.attribute_values.filter(attribute__key=key).first()
            if pav and hasattr(pav, 'get_display_value') and pav.get_display_value():
                value = pav.get_display_value()
            else:
                # Fallback to legacy
                legacy = product.legacy_attribute_set.filter(key=key).first()
                if legacy and legacy.value and str(legacy.value).strip() != '':
                    value = legacy.value
            if value is not None and value != "":
                attr_dict = {'key': key, 'value': value}
                # Add display_name if available from CategoryAttribute
                if key in category_attributes_map:
                    attr_dict['display_name'] = category_attributes_map[key].label_fa
                combined_attributes.append(attr_dict)
        
        # Prepare tags
        tags = list(product.tags.values('id', 'name'))
        
        # Prepare variants with prefetch_related for images to avoid N+1 queries
        variants = ProductVariant.objects.filter(
            product=product, 
            is_active=True
        ).prefetch_related(
            'images'
        ).order_by('sku')
        
        # Get CategoryAttribute mapping for display names
        category_attributes_map = {}
        if product.category:
            category_attrs = CategoryAttribute.objects.filter(category=product.category)
            category_attributes_map = {ca.key: ca for ca in category_attrs}
        
        variants_data = []
        for variant in variants:
            # Get variant images - explicitly filter by variant to ensure correct images
            variant_images = []
            try:
                # Explicitly filter images by variant ID to ensure we only get images for this variant
                variant_image_queryset = variant.images.all().order_by('-is_primary', 'order', 'created_at')
                for variant_image in variant_image_queryset:
                    if variant_image.image and variant_image.variant_id == variant.id:
                        image_url = request.build_absolute_uri(variant_image.image.url)
                        variant_images.append({
                            'id': variant_image.id,
                            'url': image_url,
                            'is_primary': variant_image.is_primary,
                            'order': variant_image.order
                        })
            except Exception as e:
                print(f"Error getting variant images for variant {variant.id} (SKU: {variant.sku}): {e}")
                import traceback
                traceback.print_exc()
            
            # Convert attributes dictionary to array format
            attributes_array = []
            if variant.attributes:
                # Get the distinctive attribute key from product
                distinctive_key = getattr(product, 'distinctive_attribute_key', None)
                
                # If no distinctive key is set and there's only one attribute, auto-mark it as distinctive
                if not distinctive_key and len(variant.attributes) == 1:
                    distinctive_key = list(variant.attributes.keys())[0]
                    print(f"🎯 Auto-detected distinctive attribute: {distinctive_key} (only one attribute)")
                
                for key, value in variant.attributes.items():
                    # Check if this specific attribute is the distinctive one
                    is_distinctive = (distinctive_key and key == distinctive_key)
                    
                    # Get display information from CategoryAttribute
                    display_name = None
                    priority = None
                    if key in category_attributes_map:
                        ca = category_attributes_map[key]
                        display_name = ca.label_fa
                        priority = ca.display_order
                    
                    attributes_array.append({
                        'key': key,
                        'value': value,
                        'isDistinctive': is_distinctive
                    })
                    # Add display_name if available
                    if display_name:
                        attributes_array[-1]['display_name'] = display_name
                    if priority is not None:
                        attributes_array[-1]['priority'] = priority
            
            variants_data.append({
                'id': variant.id,
                'sku': variant.sku,
                'attributes': attributes_array,
                'color': variant.attributes.get('color', 'نامشخص') if variant.attributes else 'نامشخص',
                'size': variant.attributes.get('size', 'نامشخص') if variant.attributes else 'نامشخص',
                'price_toman': float(variant.price_toman),
                'stock_quantity': variant.stock_quantity,
                'is_active': variant.is_active,
                'is_default': variant.is_default,
                'isDistinctive': variant.isDistinctive,
                'images': variant_images
            })
        
        # Prepare display attributes (only those marked for product view with actual product values)
        display_attributes = []
        category_attributes = CategoryAttribute.objects.filter(
            category=product.category,
            is_displayed_in_product=True
        ).order_by('display_order', 'key')
        
        for cat_attr in category_attributes:
            # Find the actual values assigned to this specific product
            product_attribute_values = set()

            # Check variants for actual values
            for variant in variants:
                if variant.attributes and cat_attr.key in variant.attributes:
                    if str(variant.attributes[cat_attr.key]).strip() != '':
                        product_attribute_values.add(variant.attributes[cat_attr.key])

            # Check legacy attributes for actual values
            for legacy_attr in product.legacy_attribute_set.all():
                if legacy_attr.key == cat_attr.key and legacy_attr.value and str(legacy_attr.value).strip() != '':
                    product_attribute_values.add(legacy_attr.value)

            # Check new attribute system for actual values
            for attr_value in product.attribute_values.all():
                if attr_value.attribute.key == cat_attr.key:
                    display_val = attr_value.get_display_value()
                    if display_val is not None and str(display_val).strip() != '':
                        product_attribute_values.add(display_val)

            # Include only if the product actually has a value for this attribute
            if product_attribute_values:
                single_value = list(product_attribute_values)[0]
                display_attributes.append({
                    'key': cat_attr.key,
                    'display_name': cat_attr.label_fa,
                    'priority': cat_attr.display_order,
                    'value': single_value
                })
        
        # Prepare similar products
        similar_products = Product.objects.filter(
            category=product.category,
            is_active=True
        ).exclude(id=product.id)[:4]
        
        similar_products_data = []
        for similar in similar_products:
            similar_image = similar.images.first()
            similar_products_data.append({
                'id': similar.id,
                'name': similar.name,
                'price_toman': float(similar.price_toman),
                'price_usd': float(similar.price_usd) if similar.price_usd else None,
                'reduced_price_toman': float(similar.reduced_price_toman) if similar.reduced_price_toman else None,
                'discount_percentage': float(similar.discount_percentage) if similar.discount_percentage else None,
                'image_url': request.build_absolute_uri(similar_image.image.url) if similar_image else None
            })
        
        # Prepare full product data
        product_data = {
            'id': product.id,
            'name': product.name,
            'description': product.description or '',
            'price_toman': float(product.price_toman),
            'price_usd': float(product.price_usd) if product.price_usd else None,
            'reduced_price_toman': float(product.reduced_price_toman) if product.reduced_price_toman else None,
            'discount_percentage': float(product.discount_percentage) if product.discount_percentage else None,
            'model': product.model,
            'sku': product.sku,
            'stock_quantity': product.stock_quantity,
            'created_at': product.created_at.timestamp(),
            
            # Category and supplier
            'category': {
                'id': product.category.id,
                'name': product.category.name
            },
            'supplier': {
                'id': product.supplier.id,
                'name': str(product.supplier)
            } if product.supplier else None,
            
            # Images and attributes
            'images': product_images,
            'attributes': combined_attributes,
            'display_attributes': display_attributes,
            
            # Variants
            'variants': variants_data,
            'variants_count': len(variants_data),
            'total_stock': sum(v['stock_quantity'] for v in variants_data),
            
            # Additional details
            'tags': tags,
            'similar_products': similar_products_data
        }
        
        return JsonResponse(product_data)
    
    except Product.DoesNotExist:
        return JsonResponse({
            'error': 'Product not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

@csrf_exempt
def test_simple_view(request, category_id):
    """Simple test view to isolate the issue"""
    try:
        category = Category.objects.get(id=category_id)
        return JsonResponse({
            'success': True,
            'category_name': category.name,
            'category_id': category.id
        })
    except Category.DoesNotExist:
        return JsonResponse({'error': 'Category not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET", "POST"])
@csrf_exempt
def manage_attribute_values(request, attribute_id):
    """
    Beautiful interface for managing attribute values with drag-and-drop reordering
    """
    try:
        attribute = CategoryAttribute.objects.get(id=attribute_id)
        
        if request.method == 'POST':
            print(f"DEBUG: Received POST request to manage_attribute_values for attribute {attribute_id}")
            print(f"DEBUG: Request body: {request.body}")
            print(f"DEBUG: Content-Type: {request.headers.get('Content-Type')}")
            
            try:
                data = json.loads(request.body)
                action = data.get('action')
                print(f"DEBUG: Action: {action}")
                print(f"DEBUG: Data: {data}")
                
                if action == 'reorder_values':
                    # Reorder attribute values
                    order_data = data.get('order', [])
                    for item in order_data:
                        value_id = item.get('id')
                        new_order = item.get('order')
                        try:
                            value = AttributeValue.objects.get(id=value_id, attribute=attribute)
                            value.display_order = new_order
                            value.save()
                        except AttributeValue.DoesNotExist:
                            continue
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'مقادیر با موفقیت مرتب شدند'
                    })
                    
                elif action == 'add_value':
                    # Add new attribute value
                    value_text = data.get('value', '').strip()
                    print(f"DEBUG: Adding value: '{value_text}'")
                    
                    if not value_text:
                        return JsonResponse({'error': 'مقدار نمی‌تواند خالی باشد'}, status=400)
                    
                    # Check if value already exists
                    if AttributeValue.objects.filter(attribute=attribute, value=value_text).exists():
                        return JsonResponse({'error': 'این مقدار قبلاً وجود دارد'}, status=400)
                    
                    # Get the highest display_order and add 1
                    max_order = AttributeValue.objects.filter(attribute=attribute).aggregate(
                        Max('display_order'))['display_order__max'] or 0
                    
                    new_value = AttributeValue.objects.create(
                        attribute=attribute,
                        value=value_text,
                        display_order=max_order + 1
                    )
                    
                    print(f"DEBUG: Successfully created value: {new_value.value} with ID: {new_value.id}")
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'مقدار "{value_text}" با موفقیت اضافه شد',
                        'value': {
                            'id': new_value.id,
                            'value': new_value.value,
                            'display_order': new_value.display_order
                        }
                    })
                    
                elif action == 'delete_value':
                    # Delete attribute value
                    value_id = data.get('id')
                    try:
                        value = AttributeValue.objects.get(id=value_id, attribute=attribute)
                        value_name = value.value
                        value.delete()
                        return JsonResponse({
                            'success': True,
                            'message': f'مقدار "{value_name}" با موفقیت حذف شد'
                        })
                    except AttributeValue.DoesNotExist:
                        return JsonResponse({'error': 'مقدار مورد نظر یافت نشد'}, status=404)
                        
                else:
                    return JsonResponse({'error': 'عملیات نامعتبر'}, status=400)
                    
            except json.JSONDecodeError as e:
                print(f"DEBUG: JSON decode error: {e}")
                return JsonResponse({'error': 'داده‌های JSON نامعتبر'}, status=400)
            except Exception as e:
                print(f"DEBUG: Exception in POST handling: {e}")
                return JsonResponse({'error': str(e)}, status=500)
        
        # GET request - render the management interface
        values = AttributeValue.objects.filter(attribute=attribute).order_by('display_order', 'value')
        
        context = {
            'attribute': attribute,
            'values': values,
        }
        
        return render(request, 'shop/manage_attribute_values.html', context)
        
    except CategoryAttribute.DoesNotExist:
        return JsonResponse({'error': 'ویژگی مورد نظر یافت نشد'}, status=404)


def modern_special_offers_view(request):
    """Modern UI view for special offers"""
    context = {
        'page_title': 'پیشنهادات ویژه',
        'meta_description': 'بهترین تخفیف‌ها و پیشنهادات ویژه فروشگاه عینک',
    }
    return render(request, 'shop/modern_special_offers.html', context)


from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def admin_special_offers_view(request):
    """Admin UI view for managing special offers - Staff only"""
    context = {
        'page_title': 'مدیریت پیشنهادات ویژه',
        'meta_description': 'پنل مدیریت پیشنهادات ویژه فروشگاه',
    }
    return render(request, 'shop/admin_special_offers.html', context)


# Customer API Views
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth import get_user_model
from .models import Product, ProductVariant, ProductImage
from accounts.models import Customer, Address
import json

User = get_user_model()

def _build_image_url(request, image_url):
    """Build absolute image URL with Render fallback"""
    if not image_url:
        return ''
    if image_url.startswith(('http://', 'https://')):
        return image_url
    if request:
        return request.build_absolute_uri(image_url)
    # Fallback for Render deployment
    import os
    render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://myshop-backend-an7h.onrender.com')
    if image_url.startswith('/'):
        return f"{render_url}{image_url}"
    return f"{render_url}/{image_url}"

@api_view(['GET'])
@csrf_exempt
@login_required
def api_customer_products(request):
    """Get products for customer interface"""
    try:
        products = Product.objects.filter(is_active=True).select_related('category', 'supplier')
        
        # Search functionality
        search = request.GET.get('search')
        if search:
            from django.db.models import Q
            products = products.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        
        # Category filter
        category_id = request.GET.get('category')
        if category_id:
            products = products.filter(category_id=category_id)
        
        # Price range filter
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        if min_price:
            products = products.filter(price_toman__gte=min_price)
        if max_price:
            products = products.filter(price_toman__lte=max_price)
        
        # Pagination
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        start = (page - 1) * limit
        end = start + limit
        
        products_page = products[start:end]
        
        # Serialize products
        products_data = []
        for product in products_page:
            product_data = {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price_toman': int(product.price_toman),
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'category': product.category.id if product.category else None,
                'supplier': product.supplier.id if product.supplier else None,
                'is_active': product.is_active,
                'created_at': product.created_at.isoformat(),
                'images': [
                    {
                        'id': img.id,
                        'image': request.build_absolute_uri(img.image.url) if img.image and img.image.url else '',
                        'is_primary': img.is_primary,
                        'display_order': img.order
                    } for img in product.images.all()
                ],
                'variants': [
                    {
                        'id': variant.id,
                        'sku': variant.sku,
                        'variant_name': str(variant),  # Use the __str__ method
                        'attributes': variant.attributes,
                        'price_toman': int(variant.price_toman),
                        'price_usd': None,  # Your model doesn't have price_usd
                        'stock_quantity': variant.stock_quantity,
                        'is_active': variant.is_active
                    } for variant in product.variants.filter(is_active=True)
                ]
            }
            products_data.append(product_data)
        
        return Response({
            'results': products_data,
            'count': products.count(),
            'page': page,
            'limit': limit
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Utility function to get cart for user (authenticated or guest)
def get_or_create_cart(request):
    """
    Get or create cart for authenticated user or guest.
    Includes device ID validation and access control.
    Returns: (cart, is_authenticated, error_response)
    """
    from .models import Cart
    from .rate_limiting import validate_device_id, enforce_cart_access_control
    
    # Check if user is authenticated
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(customer=request.user, defaults={'session_key': ''})
        return cart, True, None
    
    # For guest users, validate and use device ID from header
    device_id = request.headers.get('X-Device-ID', '').strip()
    if not device_id:
        return None, False, Response({
            'detail': 'Device ID required for guest users. Send X-Device-ID header.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate device ID format (must be valid UUID)
    is_valid, normalized_device_id = validate_device_id(device_id)
    if not is_valid:
        return None, False, Response({
            'detail': 'Invalid device ID format'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get or create cart for guest using normalized device ID
    cart, created = Cart.objects.get_or_create(
        customer=None,
        session_key=normalized_device_id,
        defaults={'customer': None, 'session_key': normalized_device_id}
    )
    
    # Enforce access control: ensure device ID matches cart's session_key
    access_error = enforce_cart_access_control(cart, request, normalized_device_id)
    if access_error:
        return None, False, access_error
    
    return cart, False, None


@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@csrf_exempt
def api_customer_cart(request):
    """Customer cart management using database storage (persistent across sessions) - Supports authenticated and guest users"""
    from .rate_limiting import check_rate_limit
    
    try:
        # Apply rate limiting (50 requests per minute for cart endpoints)
        rate_limit_error = check_rate_limit(request, max_requests_per_minute=50, window_seconds=60)
        if rate_limit_error:
            return rate_limit_error
        
        if request.method == 'GET':
            # Get or create cart (works for authenticated and guest users)
            cart, is_authenticated, error_response = get_or_create_cart(request)
            
            if error_response:
                return error_response
            
            if cart is None:
                return Response({
                    'detail': 'Device ID required for guest users. Send X-Device-ID header.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user_info = request.user.email if is_authenticated else f"Guest ({cart.session_key[:8]}...)"
            print(f"🛒 Cart API Debug for: {user_info}")
            print(f"📦 Database cart: Found cart ID {cart.id}")
            
            from .models import CartItem
            
            cart_items = []
            total_items = 0
            total_price = 0
            total_original_price = 0
            
            for item in cart.items.all():
                try:
                    # Prepare variant data in the desired format
                    variant_data = None
                    if item.variant:
                        # Transform attributes from dict to array format
                        attributes_array = []
                        if isinstance(item.variant.attributes, dict):
                            # Get category for lookup of attribute display names
                            category = item.product.category if item.product.category else None
                            for key, value in item.variant.attributes.items():
                                # Try to get display_name from CategoryAttribute
                                display_name = None
                                if category:
                                    try:
                                        cat_attr = category.category_attributes.get(key=key)
                                        display_name = cat_attr.label_fa
                                    except:
                                        # If CategoryAttribute doesn't exist, use key as fallback
                                        pass
                                
                                attr_dict = {
                                    'key': key,
                                    'value': value,
                                    'isDistinctive': getattr(item.variant, 'isDistinctive', False)
                                }
                                # Only include display_name if it exists
                                if display_name:
                                    attr_dict['display_name'] = display_name
                                
                                attributes_array.append(attr_dict)
                        
                        # Get variant images
                        variant_images = []
                        if hasattr(item.variant, 'images'):
                            variant_images = [
                                {
                                    'id': img.id,
                                    'image': _build_image_url(request, img.image.url) if img.image and img.image.url else '',
                                    'is_primary': img.is_primary,
                                    'display_order': img.order
                                } for img in item.variant.images.all()
                            ]
                        
                        variant_data = {
                            'id': item.variant.id,
                            'sku': item.variant.sku,
                            'attributes': attributes_array,
                            'price_toman': float(item.variant.price_toman),
                            'is_active': item.variant.is_active,
                            'images': variant_images
                        }
                    
                    # Get attributes marked for basket display (max 2)
                    product_attributes = []
                    try:
                        # Get category attributes marked for basket display
                        basket_attributes = item.product.category.category_attributes.filter(
                            display_in_basket=True
                        ).order_by('display_order')[:2]
                        
                        # Get product attribute values for these attributes
                        for cat_attr in basket_attributes:
                            # Try to find the attribute value for this product
                            attr_value = None
                            
                            # Check in new system (attribute_values)
                            if hasattr(item.product, 'attribute_values'):
                                for av in item.product.attribute_values.all():
                                    if av.attribute.key == cat_attr.key:
                                        attr_value = av.get_display_value()
                                        break
                            
                            # Check in legacy system (legacy_attribute_set)
                            if not attr_value and hasattr(item.product, 'legacy_attribute_set'):
                                for legacy in item.product.legacy_attribute_set.all():
                                    if legacy.key == cat_attr.key:
                                        attr_value = legacy.value
                                        break
                            
                            # Add to display attributes if value exists
                            if attr_value and str(attr_value).strip():
                                product_attributes.append({
                                    'key': cat_attr.key,
                                    'value': str(attr_value),
                                    'display_name': cat_attr.label_fa
                                })
                        
                    except Exception as e:
                        print(f"❌ Error getting product attributes for {item.product.id}: {e}")
                        product_attributes = []
                    
                    # Determine final price (use reduced price if available, otherwise original price)
                    final_price_toman = float(item.product.reduced_price_toman) if item.product.reduced_price_toman else (float(item.product.price_toman) if item.product.price_toman else 0)
                    original_price_toman = float(item.product.price_toman) if item.product.price_toman else 0
                    
                    # Calculate original total price for this item (using original price, not reduced)
                    if item.variant and item.variant.price_toman:
                        original_item_price = float(item.variant.price_toman) * item.quantity
                    else:
                        original_item_price = original_price_toman * item.quantity
                    
                    cart_items.append({
                        'id': item.id,  # Use actual CartItem database ID
                        'product': {
                            'id': item.product.id,
                            'name': item.product.name,
                            'description': item.product.description,
                            'price_toman': final_price_toman,  # Final price (discounted if available)
                            'original_price_toman': original_price_toman if item.product.reduced_price_toman else None,  # Original price (only if discount exists)
                            'discount_percentage': float(item.product.discount_percentage) if item.product.discount_percentage else None,
                            'sku': item.product.sku,
                            'model': item.product.model,
                            'brand': getattr(item.product.brand, 'name', None) if hasattr(item.product, 'brand') and item.product.brand else None,
                            'category': {
                                'id': item.product.category.id if item.product.category else None,
                                'name': item.product.category.name if item.product.category else None
                            },
                            'attributes': product_attributes,
                            'images': [
                                {
                                    'id': img.id,
                                    'image': _build_image_url(request, img.image.url) if img.image and img.image.url else '',
                                    'is_primary': img.is_primary,
                                    'display_order': img.order
                                } for img in item.product.images.all()
                            ]
                        },
                    'variant': variant_data,
                        'quantity': item.quantity,
                        'total_price_toman': float(item.get_total_price()),
                        'total_price_usd': None,
                        'added_at': item.created_at.isoformat()
                    })
                    
                    total_items += item.quantity
                    total_price += float(item.get_total_price())
                    total_original_price += original_item_price
                except Exception as e:
                    print(f"❌ Error processing cart item {item.id}: {e}")
                    continue
            
            print(f"📊 Database cart items count: {len(cart_items)}")
            
            return Response({
                'id': cart.id,
                'items': cart_items,
                'total_items': total_items,
                'total_price_toman': total_price,
                'total_original_price_toman': total_original_price,
                'total_price_usd': None,
                'created_at': cart.created_at.isoformat(),
                'updated_at': cart.updated_at.isoformat()
            })
        
        elif request.method == 'POST':
            # Add to cart
            data = request.data
            product_id = data.get('product_id')
            variant_id = data.get('variant_id')
            quantity = int(data.get('quantity', 1))
            
            # Import models needed for POST
            from .models import CartItem, Product, ProductVariant
            
            # CONSTANTS: Cart limits (recommended values)
            MAX_QUANTITY_PER_ITEM = 100  # Maximum quantity for a single item
            MAX_TOTAL_ITEMS = 50  # Maximum number of different products in cart
            MAX_TOTAL_QUANTITY = 200  # Maximum total items in cart (e.g., 50 unique products × 4 quantity each)
            
            if not product_id:
                return Response({'error': 'Product ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate quantity
            if quantity <= 0:
                return Response({'error': 'Quantity must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)
            
            if quantity > MAX_QUANTITY_PER_ITEM:
                return Response({
                    'error': f'Maximum quantity per item is {MAX_QUANTITY_PER_ITEM}',
                    'max_quantity': MAX_QUANTITY_PER_ITEM
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                product = Product.objects.get(id=product_id, is_active=True)
            except Product.DoesNotExist:
                return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Check if product has variants and require variant_id
            if hasattr(product, 'has_variants') and product.has_variants():
                if not variant_id:
                    return Response({
                        'error': 'This product has variants. variant_id is required.',
                        'product_id': product_id,
                        'available_variants': list(product.variants.filter(is_active=True).values('id', 'sku', 'price_toman'))
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Use database transaction with locking to prevent race conditions
            # This ensures only one request can check and add stock at a time
            with transaction.atomic():
                # Get or create cart (works for authenticated and guest users)
                cart, is_authenticated, error_response = get_or_create_cart(request)
                
                if error_response:
                    return error_response
                
                if cart is None:
                    return Response({
                        'detail': 'Device ID required for guest users. Send X-Device-ID header.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                print(f"📦 Add to cart - Database cart: Found cart ID {cart.id}")
                
                # Check if variant exists - WITH LOCK to prevent race conditions
                variant = None
                if variant_id:
                    try:
                        # Lock the variant row to prevent concurrent access
                        variant = ProductVariant.objects.select_for_update().get(
                            id=variant_id, 
                            product=product, 
                            is_active=True
                        )
                    except ProductVariant.DoesNotExist:
                        return Response({'error': 'Variant not found'}, status=status.HTTP_404_NOT_FOUND)
                
                # Check stock availability WITH LOCK held (prevents race condition)
                if variant and hasattr(variant, 'stock_quantity'):
                    available_stock = variant.stock_quantity
                    if available_stock <= 0:
                        return Response({
                            'error': 'This variant is out of stock',
                            'variant_id': variant_id
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Check if adding quantity would exceed available stock
                    if quantity > available_stock:
                        return Response({
                            'error': f'Only {available_stock} items available in stock',
                            'available_stock': available_stock,
                            'requested_quantity': quantity
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Check cart limits
                total_unique_items = cart.items.count()
                
                # Check if adding a new unique product would exceed limit
                if CartItem.objects.filter(cart=cart, product=product, variant=variant).count() == 0:
                    if total_unique_items >= MAX_TOTAL_ITEMS:
                        return Response({
                            'error': f'Cart cannot contain more than {MAX_TOTAL_ITEMS} different products',
                            'max_unique_items': MAX_TOTAL_ITEMS,
                            'current_unique_items': total_unique_items
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Calculate price
                unit_price = float(variant.price_toman if variant else product.price_toman)
                
                # Add or update item (within transaction)
                cart_item, item_created = CartItem.objects.get_or_create(
                    cart=cart,
                    product=product,
                    variant=variant,
                    defaults={
                        'quantity': quantity,
                        'unit_price': unit_price
                    }
                )
                
                if not item_created:
                    # Update existing item - check if new quantity exceeds limits
                    new_total_quantity = cart_item.quantity + quantity
                    
                    if new_total_quantity > MAX_QUANTITY_PER_ITEM:
                        return Response({
                            'error': f'Total quantity cannot exceed {MAX_QUANTITY_PER_ITEM} for this item',
                            'current_quantity': cart_item.quantity,
                            'requested_additional': quantity,
                            'would_be_total': new_total_quantity,
                            'max_quantity_per_item': MAX_QUANTITY_PER_ITEM
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Check stock again for variants (with lock still held)
                    if variant and hasattr(variant, 'stock_quantity'):
                        # Re-read variant with lock to ensure we have latest stock
                        variant.refresh_from_db()
                        if new_total_quantity > variant.stock_quantity:
                            return Response({
                                'error': f'Cannot add more items. Available stock: {variant.stock_quantity}',
                                'current_in_cart': cart_item.quantity,
                                'available_stock': variant.stock_quantity
                            }, status=status.HTTP_400_BAD_REQUEST)
                    
                    cart_item.quantity = new_total_quantity
                    cart_item.save()
                    print(f"🔄 Updated existing cart item: {cart_item}")
                else:
                    print(f"➕ Created new cart item: {cart_item}")
            
            # Return success response
            return Response({
                'message': 'Item added to cart successfully',
                'cart': {
                    'id': cart.id,
                    'items': cart.items.count(),
                    'total_items': cart.get_total_items(),
                    'total_price_toman': float(cart.get_total_price()),
                    'total_price_usd': None,
                    'created_at': cart.created_at.isoformat(),
                    'updated_at': cart.updated_at.isoformat()
                }
            })
        
        elif request.method == 'PUT':
            # Update cart item
            data = request.data
            item_id = data.get('item_id')
            quantity = int(data.get('quantity', 1))
            
            # Get cart (works for authenticated and guest users)
            cart, is_authenticated, error_response = get_or_create_cart(request)
            
            if error_response:
                return error_response
            
            if cart is None:
                return Response({
                    'detail': 'Device ID required for guest users. Send X-Device-ID header.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            from .models import CartItem
            
            try:
                cart_item = CartItem.objects.get(id=item_id, cart=cart)
                cart_item.quantity = quantity
                cart_item.save()
                
                return Response({'message': 'Cart item updated successfully'})
            except CartItem.DoesNotExist:
                return Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)
        
        elif request.method == 'DELETE':
            # Remove from cart
            data = request.data
            item_id = data.get('item_id')
            
            # Get cart (works for authenticated and guest users)
            cart, is_authenticated, error_response = get_or_create_cart(request)
            
            if error_response:
                return error_response
            
            if cart is None:
                return Response({
                    'detail': 'Device ID required for guest users. Send X-Device-ID header.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            from .models import CartItem
            
            try:
                cart_item = CartItem.objects.get(id=item_id, cart=cart)
                cart_item.delete()
                
                return Response({'message': 'Cart item removed successfully'})
            except CartItem.DoesNotExist:
                return Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_customer_cart_add(request):
    """Add item to cart"""
    return api_customer_cart(request)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_customer_cart_update(request):
    """Update cart item"""
    return api_customer_cart(request)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_customer_cart_remove(request):
    """Remove item from cart or decrease quantity"""
    # Handle deletion directly to avoid re-wrapping DRF Request into HttpRequest
    data = request.data
    item_id = data.get('item_id')
    quantity = data.get('quantity')  # Optional: if provided, decrease quantity instead of deleting

    from .models import CartItem

    try:
        cart_item = CartItem.objects.get(id=item_id, cart__customer=request.user)
        
        # If quantity is provided, decrease the count instead of deleting
        if quantity is not None:
            decrease_by = int(quantity)
            new_quantity = cart_item.quantity - decrease_by
            
            # If quantity would be 0 or less, delete the item
            if new_quantity <= 0:
                cart_item.delete()
                return Response({'message': 'Cart item removed successfully'})
            else:
                # Update quantity
                cart_item.quantity = new_quantity
                cart_item.save()
                return Response({
                    'message': 'Cart item quantity decreased successfully',
                    'new_quantity': new_quantity
                })
        else:
            # No quantity provided, delete entirely (backward compatible)
            cart_item.delete()
            return Response({'message': 'Cart item removed successfully'})
            
    except CartItem.DoesNotExist:
        return Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@csrf_exempt
def api_customer_checkout(request):
    """Process checkout using database cart - Supports authenticated and guest users"""
    from .rate_limiting import check_rate_limit
    
    try:
        # Apply rate limiting (30 requests per minute for checkout - more restrictive)
        rate_limit_error = check_rate_limit(request, max_requests_per_minute=30, window_seconds=60)
        if rate_limit_error:
            return rate_limit_error
        
        from .models import Cart, CartItem, Order, OrderItem
        from accounts.models import Address
        from decimal import InvalidOperation
        
        # Get cart (works for authenticated and guest users)
        cart, is_authenticated, error_response = get_or_create_cart(request)
        
        if error_response:
            return error_response
        
        if cart is None:
            return Response({
                'detail': 'Device ID required for guest users. Send X-Device-ID header.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not cart.items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        data = request.data
        
        # For guest users, collect email and address info from request
        # For authenticated users, use user info or provided address
        if is_authenticated:
            user = request.user
            default_first_name = user.first_name or user.username.split('@')[0] if '@' in user.username else user.username
            default_last_name = user.last_name or ''
            default_email = user.email
        else:
            # Guest user - require email
            default_email = data.get('email', '').strip()
            if not default_email:
                return Response({
                    'error': 'Email is required for guest checkout'
                }, status=status.HTTP_400_BAD_REQUEST)
            default_first_name = data.get('first_name', '').strip()
            default_last_name = data.get('last_name', '').strip()
        
        # Handle address - either address_id (for authenticated users) or full address details
        address = None
        address_id = data.get('address_id')
        
        if address_id and is_authenticated:
            # Use existing address (only for authenticated users)
            try:
                address = Address.objects.get(id=address_id, customer=request.user)
            except Address.DoesNotExist:
                return Response({'error': 'Address not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Create address from provided details (works for both authenticated and guest)
            receiver_name = data.get('receiver_name', f"{default_first_name} {default_last_name}".strip())
            street_address = data.get('street_address', data.get('delivery_address', ''))
            city = data.get('city', 'Unknown')
            phone = data.get('phone', data.get('phone_number', ''))
            country = data.get('country', 'Iran')
            postal_code = data.get('postal_code', '00000')
            
            # Validate required fields
            if not receiver_name or not street_address or not city or not phone:
                return Response({
                    'error': 'Missing required address fields: receiver_name, street_address, city, and phone are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # For authenticated users, save address to database
            if is_authenticated:
                address_data = {
                    'customer': request.user,
                    'receiver_name': receiver_name,
                    'street_address': street_address,
                    'city': city,
                    'province': data.get('province', ''),
                    'vahed': data.get('unit', data.get('vahed', '')),
                    'phone': phone,
                    'country': country,
                    'postal_code': postal_code,
                    'label': data.get('address_label', 'Home'),
                }
                address = Address.objects.create(**address_data)
            else:
                # For guest users, just store address as string (no Address model)
                pass
        
        # Get delivery and payment options
        delivery_option = data.get('delivery_option', 'standard')
        payment_method = data.get('payment_method', 'cod')
        discount_code = data.get('discount_code', '')
        delivery_notes = data.get('delivery_notes', '')
        
        # Calculate totals safely
        try:
            subtotal_toman = cart.get_total_price()
        except (TypeError, ValueError, AttributeError, InvalidOperation) as e:
            print(f"⚠️ Error calculating cart total: {e}")
            subtotal_toman = 0
            for item in cart.items.all():
                try:
                    subtotal_toman += item.get_total_price()
                except:
                    continue
        
        # Calculate shipping cost based on delivery option
        shipping_cost_toman = 0
        if delivery_option == 'express':
            shipping_cost_toman = 50000
        elif delivery_option == 'standard':
            shipping_cost_toman = 30000
        
        # Calculate discount
        discount_amount_toman = 0
        if discount_code:
            # TODO: Implement discount code validation
            pass
        
        total_toman = subtotal_toman + shipping_cost_toman - discount_amount_toman
        
        # Get address details for order
        if address:
            delivery_address_str = address.full_address if hasattr(address, 'full_address') else address.street_address
            postal_code = address.postal_code or '00000'
            city = address.city or 'Unknown'
        else:
            # Guest user - use provided address details
            delivery_address_str = data.get('street_address', data.get('delivery_address', ''))
            postal_code = data.get('postal_code', '00000')
            city = data.get('city', 'Unknown')
        
        # Determine payment status
        is_paid = False
        if payment_method == 'cod':
            is_paid = True  # COD is marked as paid since payment is on delivery
        
        # Create order (Order model already supports guest orders - no customer field required)
        order = Order.objects.create(
            first_name=default_first_name or receiver_name.split()[0] if receiver_name else 'Guest',
            last_name=default_last_name or ' '.join(receiver_name.split()[1:]) if receiver_name and len(receiver_name.split()) > 1 else '',
            email=default_email,
            address=delivery_address_str,
            postal_code=postal_code,
            city=city,
            paid=is_paid
        )
        
        # Create order items from cart items
        for cart_item in cart.items.all():
            try:
                unit_price = cart_item.get_unit_price_toman()
                
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    price=unit_price,
                    quantity=cart_item.quantity
                )
            except Exception as e:
                print(f"⚠️ Error creating order item: {e}")
                continue
        
        # Clear cart after successful order creation
        cart.items.all().delete()
        
        return Response({
            'success': True,
            'order': {
                'id': order.id,
                'order_number': f"ORD-{order.id:06d}",
                'status': 'paid' if order.paid else 'pending',
                'total_toman': float(order.get_total_cost()),
                'created_at': order.created.isoformat()
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        import traceback
        print(f"❌ Checkout error: {e}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@csrf_exempt
@login_required
def api_customer_orders(request):
    """Get customer orders"""
    try:
        from .models import Order
        
        print(f"🔍 Getting orders for user: {request.user.email}")
        
        # Get orders for the current user
        orders = Order.objects.filter(email=request.user.email).order_by('-created')
        print(f"📋 Found {orders.count()} orders")
        
        orders_data = []
        for order in orders:
            try:
                order_data = {
                    'id': order.id,
                    'order_number': f"ORD-{order.id:06d}",
                    'first_name': order.first_name,
                    'last_name': order.last_name,
                    'email': order.email,
                    'address': order.address,
                    'postal_code': order.postal_code,
                    'city': order.city,
                    'total_amount': float(order.get_total_cost()),
                    'status': 'paid' if order.paid else 'pending',
                    'payment_method': 'COD' if order.paid else 'PENDING',  # Default based on status
                    'created_at': order.created.isoformat(),
                    'updated_at': order.updated.isoformat(),
                    'items': [
                        {
                            'id': item.id,
                            'product_name': item.product.name,
                            'product_id': item.product.id,
                            'price': float(item.price),
                            'quantity': item.quantity,
                            'total': float(item.get_cost())
                        } for item in order.items.all()
                    ]
                }
                orders_data.append(order_data)
                print(f"✅ Processed order {order.id}")
            except Exception as e:
                print(f"❌ Error processing order {order.id}: {str(e)}")
                continue
        
        print(f"📊 Returning {len(orders_data)} orders")
        return Response({
            'results': orders_data,
            'count': len(orders_data)
        })
        
    except Exception as e:
        print(f"❌ Error in api_customer_orders: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@csrf_exempt
@login_required
def api_customer_order_detail(request, order_id):
    """Get detailed information about a specific order"""
    try:
        from .models import Order
        
        print(f"🔍 Getting order details for order ID: {order_id}, user: {request.user.email}")
        
        # Get the specific order for the current user
        try:
            order = Order.objects.get(id=order_id, email=request.user.email)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        print(f"✅ Found order {order.id}")
        
        # Build detailed order data
        order_data = {
            'id': order.id,
            'order_number': f"ORD-{order.id:06d}",
            'first_name': order.first_name,
            'last_name': order.last_name,
            'email': order.email,
            'address': order.address,
            'postal_code': order.postal_code,
            'city': order.city,
            'total_amount': float(order.get_total_cost()),
            'status': 'paid' if order.paid else 'pending',
            'payment_method': 'COD' if order.paid else 'PENDING',
            'created_at': order.created.isoformat(),
            'updated_at': order.updated.isoformat(),
            'items': [
                {
                    'id': item.id,
                    'product_name': item.product.name,
                    'product_id': item.product.id,
                    'product_description': item.product.description,
                    'product_image': item.product.images.filter(is_primary=True).first().image.url if item.product.images.filter(is_primary=True).exists() else None,
                    'price': float(item.price),
                    'quantity': item.quantity,
                    'total': float(item.get_cost())
                } for item in order.items.all()
            ],
            'order_summary': {
                'subtotal': float(order.get_total_cost()),
                'delivery_fee': 0.0,  # Could be calculated based on delivery option
                'total': float(order.get_total_cost()),
                'item_count': order.items.count()
            }
        }
        
        print(f"📊 Returning detailed order data for order {order.id}")
        return Response(order_data)
        
    except Exception as e:
        print(f"❌ Error in api_customer_order_detail: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@csrf_exempt
@login_required
def api_customer_order_cancel(request, order_id):
    """Cancel a specific order"""
    try:
        from .models import Order
        
        print(f"🚫 Attempting to cancel order ID: {order_id}, user: {request.user.email}")
        
        # Get the specific order for the current user
        try:
            order = Order.objects.get(id=order_id, email=request.user.email)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if order can be cancelled
        if order.paid:
            # In a real system, you'd check if order is still cancellable
            # For now, we'll allow cancellation of paid orders
            pass
        
        # Get cancellation reason from request
        data = request.data
        reason = data.get('reason', 'Customer requested cancellation')
        comment = data.get('comment', '')
        
        print(f"📝 Cancellation reason: {reason}")
        print(f"💬 Comment: {comment}")
        
        # In a real system, you would:
        # 1. Update order status to 'cancelled'
        # 2. Process refund if payment was made
        # 3. Restore inventory
        # 4. Send cancellation notification
        
        # For now, we'll just return success
        # You could add a 'status' field to Order model to track cancellation
        
        return Response({
            'message': 'Order cancellation request submitted successfully',
            'order_id': order.id,
            'order_number': f"ORD-{order.id:06d}",
            'status': 'cancellation_requested',
            'reason': reason,
            'comment': comment,
            'cancelled_at': timezone.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error in api_customer_order_cancel: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@csrf_exempt
@login_required
def api_customer_order_track(request, order_id):
    """Track the status and location of a specific order"""
    try:
        from .models import Order
        
        print(f"📦 Tracking order ID: {order_id}, user: {request.user.email}")
        
        # Get the specific order for the current user
        try:
            order = Order.objects.get(id=order_id, email=request.user.email)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        print(f"✅ Found order {order.id} for tracking")
        
        # Generate tracking number (in real system, this would be set during shipping)
        tracking_number = f"TRK{order.id:06d}"
        
        # Create timeline based on order status
        timeline = [
            {
                'status': 'pending',
                'timestamp': order.created.isoformat(),
                'description': 'Order placed',
                'location': 'Online Store'
            }
        ]
        
        if order.paid:
            timeline.append({
                'status': 'paid',
                'timestamp': order.created.isoformat(),  # In real system, this would be payment timestamp
                'description': 'Payment confirmed',
                'location': 'Payment Gateway'
            })
            
            # Add shipping timeline (simulated)
            timeline.append({
                'status': 'processing',
                'timestamp': (order.created + timezone.timedelta(hours=2)).isoformat(),
                'description': 'Order being prepared',
                'location': 'Warehouse'
            })
            
            timeline.append({
                'status': 'shipped',
                'timestamp': (order.created + timezone.timedelta(days=1)).isoformat(),
                'description': 'Order shipped',
                'location': 'Tehran Warehouse'
            })
            
            timeline.append({
                'status': 'in_transit',
                'timestamp': (order.created + timezone.timedelta(days=2)).isoformat(),
                'description': 'Out for delivery',
                'location': 'Local Delivery Center'
            })
        
        # Calculate estimated delivery
        estimated_delivery = order.created + timezone.timedelta(days=3)
        
        # Determine current status
        current_status = 'paid' if order.paid else 'pending'
        if order.paid:
            # In a real system, you'd have more statuses
            current_status = 'in_transit'
        
        tracking_data = {
            'order_id': order.id,
            'order_number': f"ORD-{order.id:06d}",
            'tracking_number': tracking_number,
            'status': current_status,
            'current_location': 'Local Delivery Center' if order.paid else 'Warehouse',
            'timeline': timeline,
            'estimated_delivery': estimated_delivery.isoformat(),
            'delivery_address': order.address,
            'contact_phone': 'Not available',  # Could be stored in order
            'courier_info': {
                'company': 'Iran Post',
                'service': 'Standard Delivery',
                'contact': '+98-21-1234-5678'
            }
        }
        
        print(f"📊 Returning tracking data for order {order.id}")
        return Response(tracking_data)
        
    except Exception as e:
        print(f"❌ Error in api_customer_order_track: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@csrf_exempt
@login_required
def api_customer_order_return(request, order_id):
    """Request order return (full or partial)"""
    from customer_platform_apis import OrderReturnRequestView
    view = OrderReturnRequestView()
    return view.post(request, order_id)


@api_view(['POST'])
@csrf_exempt
@login_required
def api_customer_order_item_return(request, order_id, item_id):
    """Request return for a specific order item"""
    from customer_platform_apis import OrderItemReturnRequestView
    view = OrderItemReturnRequestView()
    return view.post(request, order_id, item_id)


@api_view(['POST'])
@csrf_exempt
@login_required
def api_customer_order_reject(request, order_id):
    """Reject an order"""
    from customer_platform_apis import OrderRejectView
    view = OrderRejectView()
    return view.post(request, order_id)


@api_view(['POST'])
@csrf_exempt
@login_required
def api_customer_order_item_reject(request, order_id, item_id):
    """Reject a specific order item"""
    from customer_platform_apis import OrderItemRejectView
    view = OrderItemRejectView()
    return view.post(request, order_id, item_id)


@api_view(['GET'])
@csrf_exempt
@login_required
def api_customer_order_returns_list(request):
    """List all return requests for a user"""
    from customer_platform_apis import OrderReturnListView
    view = OrderReturnListView()
    return view.get(request)


@api_view(['GET'])
@csrf_exempt
@login_required
def api_customer_order_return_detail(request, return_id):
    """Get details of a specific return request"""
    from customer_platform_apis import OrderReturnDetailView
    view = OrderReturnDetailView()
    return view.get(request, return_id)


@api_view(['GET'])
@csrf_exempt
@login_required
def api_debug_session(request):
    """Debug session data for troubleshooting"""
    try:
        session_data = {
            'user_email': request.user.email,
            'session_keys': list(request.session.keys()),
            'session_data': dict(request.session),
            'basket_v1': request.session.get('basket_v1', 'Not found'),
            'session_id': request.session.session_key,
            'session_expiry': request.session.get_expiry_age(),
        }
        
        print(f"🔍 Debug session for user: {request.user.email}")
        print(f"📊 Session data: {session_data}")
        
        return Response(session_data)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@csrf_exempt
@login_required
def api_debug_add_to_cart(request):
    """Debug function to manually add item to cart"""
    try:
        data = request.data
        product_id = data.get('product_id', 1)  # Default to product ID 1
        quantity = int(data.get('quantity', 1))
        
        print(f"🧪 Debug: Adding product {product_id} with quantity {quantity} to cart for user {request.user.email}")
        
        # Get basket from session
        basket = request.session.get('basket_v1', {'items': {}, 'currency': 'toman'})
        basket.setdefault('items', {})
        
        # Create item key
        item_key = f"{product_id}_no_variant"
        
        # Get product
        try:
            product = Product.objects.get(id=product_id, is_active=True)
            unit_price = float(product.price_toman)
            total_price = unit_price * quantity
            
            # Add item
            basket['items'][item_key] = {
                'product_id': product_id,
                'variant_id': None,
                'quantity': quantity,
                'unit_price_toman': unit_price,
                'total_price_toman': total_price,
                'added_at': timezone.now().isoformat()
            }
            
            basket['updated_at'] = timezone.now().isoformat()
            request.session['basket_v1'] = basket
            request.session.modified = True
            
            print(f"✅ Debug: Added item to cart. Basket now has {len(basket['items'])} items")
            print(f"📦 Debug: Basket data: {basket}")
            
            return Response({
                'message': f'Debug: Added product {product_id} to cart',
                'basket': basket,
                'session_keys': list(request.session.keys())
            })
            
        except Product.DoesNotExist:
            return Response({'error': f'Product {product_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"❌ Error in api_debug_add_to_cart: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
