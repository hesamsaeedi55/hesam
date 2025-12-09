from django.http import JsonResponse
from django.db.models import Q
from django.db import models
from django.shortcuts import get_object_or_404
from .models import Product, Attribute, NewAttributeValue, Category, ProductAttributeValue, CategoryGroup, CategoryGender, SpecialOffer, SpecialOfferProduct, ProductVariant
from decimal import InvalidOperation
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import ProductSerializer, SpecialOfferSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from django.core.paginator import Paginator
from rest_framework.generics import ListCreateAPIView, DestroyAPIView
from rest_framework import serializers
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed


# Remove the filter_products_by_attributes function and any related code


def get_attribute_values_for_category(request, category_id, attribute_key):
    """
    Get all possible values for a specific attribute in a category
    Useful for populating filter dropdowns
    """
    try:
        category = Category.objects.get(id=category_id)
        attribute = Attribute.objects.get(key=attribute_key)
        
        # Check if this attribute is assigned to this category
        # This part of the code is no longer relevant as SubcategoryAttribute model is removed.
        # The attributes are now directly linked to the category.
        # For now, we'll return an error.
        # In a real scenario, you would check if the attribute is directly linked to the category.
        if not category.attributes.filter(key=attribute_key).exists():
            return JsonResponse({
                'error': f'Attribute {attribute_key} is not available for category {category.name}'
            }, status=400)
        
        # Get all values for this attribute
        values = NewAttributeValue.objects.filter(attribute=attribute).order_by('display_order')
        
        values_data = []
        for value in values:
            value_data = {
                'id': value.id,
                'value': value.value,
                'persian_label': value.persian_label,
                'display_order': value.display_order
            }
            if value.color_code:
                value_data['color_code'] = value.color_code
            values_data.append(value_data)
        
        return JsonResponse({
            'attribute': {
                'id': attribute.id,
                'name': attribute.name,
                'key': attribute.key,
                'type': attribute.type
            },
            'category': {
                'id': category.id,
                'name': category.name
            },
            'values': values_data
        })
        
    except (Category.DoesNotExist, Attribute.DoesNotExist) as e:
        return JsonResponse({'error': str(e)}, status=404) 


# Deleted api_swiss_watches view as requested 

class ProductPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'per_page'
    max_page_size = 100

class CategoryProductFilterView(APIView):
    def get(self, request, category_id):
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)

        # Get valid attribute keys for this category - handle case where attributes might not exist
        try:
            valid_attribute_keys = set(
                category.category_attributes.values_list('key', flat=True)
            )
        except:
            # If category_attributes doesn't exist or is empty, use an empty set
            valid_attribute_keys = set()
        
        # Also include attribute keys that actually exist in products of this category
        # This ensures we can filter by any attribute that exists in the products
        products_in_category = Product.objects.filter(category=category, is_active=True)
        legacy_keys = set(products_in_category.values_list('legacy_attribute_set__key', flat=True).distinct())
        new_keys = set(products_in_category.values_list('attribute_values__attribute__key', flat=True).distinct())
        product_attribute_keys = legacy_keys | new_keys
        product_attribute_keys = {k for k in product_attribute_keys if k}  # Remove None values
        
        # Combine category attributes with product attributes
        valid_attribute_keys = valid_attribute_keys | product_attribute_keys
        
        # Collect multi-value filters using getlist
        multi_value_filters = {}
        price_filters = {}
        sort_params = {}
        
        # Handle both DRF request.query_params and Django request.GET
        query_params = getattr(request, 'query_params', request.GET)
        
        for key in query_params.keys():
            if key in valid_attribute_keys:
                values = query_params.getlist(key)
                # Remove empty values
                values = [v for v in values if v.strip()]
                if values:
                    multi_value_filters[key] = values
            elif key in ['price__gte', 'price__lte', 'price_toman__gte', 'price_toman__lte', 'price_usd__gte', 'price_usd__lte']:
                # Handle price range filtering
                value = query_params.get(key)
                if value and value.strip():
                    price_filters[key] = value
            elif key in ['sort_by', 'sort_order']:
                # Handle sorting parameters
                value = query_params.get(key)
                if value and value.strip():
                    sort_params[key] = value

        # Return empty result if no valid filters
        if query_params and not multi_value_filters and not price_filters and not sort_params:
            return Response({
                "products": [], 
                "pagination": {"current_page": 1, "total_pages": 1, "total_items": 0, "has_next": False, "has_previous": False}
            }, status=status.HTTP_200_OK)

        # Start with category products
        products = Product.objects.filter(category=category, is_active=True)
        
        # Apply price filters
        for price_key, price_value in price_filters.items():
            try:
                price_value = float(price_value)
                products = products.filter(**{price_key: price_value})
            except (ValueError, TypeError):
                continue
        
        # Apply attribute filters only if we have valid attributes
        if multi_value_filters:
            for attr_key, values in multi_value_filters.items():
                if len(values) == 1:
                    # Single value - case insensitive match
                    matching_ids_legacy = Product.objects.filter(
                        category=category,
                        legacy_attribute_set__key=attr_key,
                        legacy_attribute_set__value__iexact=values[0]
                    ).values_list('id', flat=True)
                    
                    matching_ids_new = Product.objects.filter(
                        category=category,
                        attribute_values__attribute__key=attr_key,
                        attribute_values__attribute_value__value__iexact=values[0]
                    ).values_list('id', flat=True)
                    
                    matching_ids_custom = Product.objects.filter(
                        category=category,
                        attribute_values__attribute__key=attr_key,
                        attribute_values__custom_value__iexact=values[0]
                    ).values_list('id', flat=True)
                    
                    # Combine all matching IDs
                    all_matching_ids = set(matching_ids_legacy) | set(matching_ids_new) | set(matching_ids_custom)
                    products = products.filter(id__in=all_matching_ids)
                else:
                    # Multiple values - use case insensitive __in filtering
                    # Fix: Use Q objects to combine multiple OR conditions
                    from django.db.models import Q
                    
                    # Build OR conditions for each value
                    legacy_conditions = Q()
                    new_conditions = Q()
                    custom_conditions = Q()
                    
                    for value in values:
                        legacy_conditions |= Q(
                            category=category,
                            legacy_attribute_set__key=attr_key,
                            legacy_attribute_set__value__iexact=value
                        )
                        new_conditions |= Q(
                            category=category,
                            attribute_values__attribute__key=attr_key,
                            attribute_values__attribute_value__value__iexact=value
                        )
                        custom_conditions |= Q(
                            category=category,
                            attribute_values__attribute__key=attr_key,
                            attribute_values__custom_value__iexact=value
                        )
                    
                    # Get matching IDs for each system
                    matching_ids_legacy = Product.objects.filter(legacy_conditions).values_list('id', flat=True)
                    matching_ids_new = Product.objects.filter(new_conditions).values_list('id', flat=True)
                    matching_ids_custom = Product.objects.filter(custom_conditions).values_list('id', flat=True)
                    
                    # Combine all matching IDs
                    all_matching_ids = set(matching_ids_legacy) | set(matching_ids_new) | set(matching_ids_custom)
                    products = products.filter(id__in=all_matching_ids)
        
        products = products.distinct()
        
        # Apply sorting
        sort_by = sort_params.get('sort_by', 'created_at')
        sort_order = sort_params.get('sort_order', 'desc')
        
        # Validate sort_by parameter
        valid_sort_fields = ['created_at', 'price_toman', 'price_usd', 'name']
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'  # Default to created_at if invalid
        
        # Apply sorting
        if sort_by == 'created_at':
            if sort_order == 'asc':
                products = products.order_by('created_at')
            else:
                products = products.order_by('-created_at')
        elif sort_by == 'price_toman':
            if sort_order == 'asc':
                products = products.order_by('price_toman')
            else:
                products = products.order_by('-price_toman')
        elif sort_by == 'price_usd':
            if sort_order == 'asc':
                products = products.order_by('price_usd')
            else:
                products = products.order_by('-price_usd')
        elif sort_by == 'name':
            if sort_order == 'asc':
                products = products.order_by('name')
            else:
                products = products.order_by('-name')
        else:
            # Default sorting by created_at desc
            products = products.order_by('-created_at')

        paginator = ProductPagination()
        paginated_qs = paginator.paginate_queryset(products, request)
        serializer = ProductSerializer(paginated_qs, many=True, context={'request': request})

        pagination = {
            "current_page": paginator.page.number,
            "total_pages": paginator.page.paginator.num_pages,
            "total_items": paginator.page.paginator.count,
            "has_next": paginator.page.has_next(),
            "has_previous": paginator.page.has_previous(),
        }

        return Response({
            "products": serializer.data,
            "pagination": pagination,
            "filters_applied": multi_value_filters,
            "price_filters_applied": price_filters,
            "sorting_applied": {
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        })


class ProductsFilterView(APIView):
    """
    General products filter API that supports:
    - Multi-value filtering using getlist() (e.g., ?brand=Nike&brand=Adidas)
    - Price range filtering (price__gte, price__lte, price_toman__gte, etc.)
    - Category filtering
    - Text search
    - All existing attribute filtering with both legacy and new systems
    """
    
    def get(self, request):
        # Start with all active products
        products = Product.objects.filter(is_active=True)
        
        # Collect filters
        multi_value_filters = {}
        price_filters = {}
        special_filters = {}
        
        # Get all possible attribute keys from both systems
        legacy_keys = set(products.values_list('legacy_attribute_set__key', flat=True).distinct())
        new_keys = set(products.values_list('attribute_values__attribute__key', flat=True).distinct())
        all_attribute_keys = legacy_keys | new_keys
        # Remove None values
        all_attribute_keys = {key for key in all_attribute_keys if key}
        
        # Handle both DRF request.query_params and Django request.GET
        query_params = getattr(request, 'query_params', request.GET)
        
        for key in query_params.keys():
            if key in all_attribute_keys:
                # Attribute filtering
                values = query_params.getlist(key)
                values = [v for v in values if v.strip()]
                if values:
                    multi_value_filters[key] = values
            elif key.startswith('price') and ('__gte' in key or '__lte' in key):
                # Price range filtering
                value = query_params.get(key)
                if value and value.strip():
                    price_filters[key] = value
            elif key in ['category', 'q', 'search', 'page', 'per_page', 'is_new_arrival', 'is_active', 'sort_by', 'sort_order']:
                # Special filters
                value = query_params.get(key)
                if value and value.strip():
                    special_filters[key] = value
        
        # Apply special filters
        if 'category' in special_filters:
            try:
                category_id = int(special_filters['category'])
                products = products.filter(category_id=category_id)
            except (ValueError, TypeError):
                pass
        
        # Apply text search
        search_query = special_filters.get('q') or special_filters.get('search')
        if search_query:
            products = products.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(model__icontains=search_query)
            )
        
        # Apply new arrivals filter
        is_new_arrival = special_filters.get('is_new_arrival')
        if is_new_arrival:
            if is_new_arrival.lower() in ['true', '1', 'yes']:
                products = products.filter(is_new_arrival=True)
            elif is_new_arrival.lower() in ['false', '0', 'no']:
                products = products.filter(is_new_arrival=False)
        
        # Apply active status filter (override default is_active=True)
        is_active = special_filters.get('is_active')
        if is_active:
            if is_active.lower() in ['false', '0', 'no']:
                # Start over without the is_active=True filter
                products = Product.objects.filter(is_active=False)
                # Re-apply other filters if needed
                if 'category' in special_filters:
                    try:
                        category_id = int(special_filters['category'])
                        products = products.filter(category_id=category_id)
                    except (ValueError, TypeError):
                        pass
        
        # Apply price filters
        for price_key, price_value in price_filters.items():
            try:
                price_value = float(price_value)
                products = products.filter(**{price_key: price_value})
            except (ValueError, TypeError):
                continue
        
        # Apply attribute filters
        for attr_key, values in multi_value_filters.items():
            if len(values) == 1:
                # Single value - case insensitive match
                matching_ids_legacy = Product.objects.filter(
                    legacy_attribute_set__key=attr_key,
                    legacy_attribute_set__value__iexact=values[0]
                ).values_list('id', flat=True)
                
                matching_ids_new = Product.objects.filter(
                    attribute_values__attribute__key=attr_key,
                    attribute_values__attribute_value__value__iexact=values[0]
                ).values_list('id', flat=True)
                
                matching_ids_custom = Product.objects.filter(
                    attribute_values__attribute__key=attr_key,
                    attribute_values__custom_value__iexact=values[0]
                ).values_list('id', flat=True)
                
                # Combine all matching IDs
                all_matching_ids = set(matching_ids_legacy) | set(matching_ids_new) | set(matching_ids_custom)
                products = products.filter(id__in=all_matching_ids)
            else:
                # Multiple values - use case insensitive __in filtering
                matching_ids_legacy = Product.objects.filter(
                    legacy_attribute_set__key=attr_key,
                    legacy_attribute_set__value__iexact__in=values
                ).values_list('id', flat=True)
                
                matching_ids_new = Product.objects.filter(
                    attribute_values__attribute__key=attr_key,
                    attribute_values__attribute_value__value__iexact__in=values
                ).values_list('id', flat=True)
                
                matching_ids_custom = Product.objects.filter(
                    attribute_values__attribute__key=attr_key,
                    attribute_values__custom_value__iexact__in=values
                ).values_list('id', flat=True)
                
                # Combine all matching IDs
                all_matching_ids = set(matching_ids_legacy) | set(matching_ids_new) | set(matching_ids_custom)
                products = products.filter(id__in=all_matching_ids)
        
        # Apply ordering and distinct
        products = products.distinct()
        
        # Apply sorting
        sort_by = special_filters.get('sort_by', 'created_at')
        sort_order = special_filters.get('sort_order', 'desc')
        
        # Validate sort_by parameter
        valid_sort_fields = ['created_at', 'price_toman', 'price_usd', 'name']
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'  # Default to created_at if invalid
        
        # Apply sorting
        if sort_by == 'created_at':
            if sort_order == 'asc':
                products = products.order_by('created_at')
            else:
                products = products.order_by('-created_at')
        elif sort_by == 'price_toman':
            if sort_order == 'asc':
                products = products.order_by('price_toman')
            else:
                products = products.order_by('-price_toman')
        elif sort_by == 'price_usd':
            if sort_order == 'asc':
                products = products.order_by('price_usd')
            else:
                products = products.order_by('-price_usd')
        elif sort_by == 'name':
            if sort_order == 'asc':
                products = products.order_by('name')
            else:
                products = products.order_by('-name')
        else:
            # Default sorting by created_at desc
            products = products.order_by('-created_at')
        
        # Pagination
        paginator = ProductPagination()
        paginated_qs = paginator.paginate_queryset(products, request)
        serializer = ProductSerializer(paginated_qs, many=True, context={'request': request})

        pagination = {
            "current_page": paginator.page.number,
            "total_pages": paginator.page.paginator.num_pages,
            "total_items": paginator.page.paginator.count,
            "has_next": paginator.page.has_next(),
            "has_previous": paginator.page.has_previous(),
        }

        return Response({
            "products": serializer.data,
            "pagination": pagination,
            "filters_applied": {
                "attributes": multi_value_filters,
                "price": price_filters,
                "special": special_filters
            },
            "sorting_applied": {
                "sort_by": sort_by,
                "sort_order": sort_order
            },
            "available_attributes": list(all_attribute_keys)
        })


@api_view(['GET'])
def debug_category1_attributes(request):
    from .models import Product
    products = Product.objects.filter(category_id=1)
    result = []
    for p in products:
        attrs = []
        for pav in p.attribute_values.all():
            attrs.append({
                'attribute_key': pav.attribute.key,
                'custom_value': pav.custom_value,
                'attribute_value': getattr(pav.attribute_value, 'value', None)
            })
        result.append({
            'id': p.id,
            'name': p.name,
            'attributes': attrs
        })
    return Response(result) 


@api_view(['GET'])
def debug_category_attributes_structure(request, category_id):
    """Debug endpoint to show CategoryAttribute structure and product relationships"""
    try:
        category = Category.objects.get(id=category_id)
        
        # Get CategoryAttribute definitions for this category
        category_attrs = category.category_attributes.all()
        category_attrs_data = []
        for ca in category_attrs:
            category_attrs_data.append({
                'id': ca.id,
                'key': ca.key,
                'type': ca.type,
                'required': ca.required,
                'label_fa': ca.label_fa
            })
        
        # Get products in this category with their legacy attributes
        products = Product.objects.filter(category=category)
        products_data = []
        for p in products:
            legacy_attrs = []
            for pa in p.legacy_attribute_set.all():
                legacy_attrs.append({
                    'key': pa.key,
                    'value': pa.value
                })
            products_data.append({
                'id': p.id,
                'name': p.name,
                'legacy_attributes': legacy_attrs
            })
        
        return Response({
            'category': {
                'id': category.id,
                'name': category.name
            },
            'category_attributes': category_attrs_data,
            'products': products_data
        })
        
    except Category.DoesNotExist:
        return Response({'error': 'Category not found'}, status=404) 


@api_view(['POST'])
def cleanup_product_attributes(request, product_id):
    """Clean up product attributes to only include valid ones for the product's category"""
    try:
        from .models import Product, ProductAttribute
        
        product = Product.objects.get(id=product_id)
        category = product.category
        
        # Get valid attribute keys for this category
        valid_keys = set(category.category_attributes.values_list('key', flat=True))
        
        # Get all current attributes for this product
        current_attributes = product.legacy_attribute_set.all()
        
        # Find attributes to remove (not in valid keys)
        attributes_to_remove = []
        attributes_to_keep = []
        
        for attr in current_attributes:
            if attr.key in valid_keys:
                attributes_to_keep.append(attr)
            else:
                attributes_to_remove.append(attr)
        
        # Remove invalid attributes
        removed_count = 0
        for attr in attributes_to_remove:
            attr.delete()
            removed_count += 1
        
        # Get updated attributes
        updated_attributes = []
        for attr in product.legacy_attribute_set.all():
            updated_attributes.append({
                'key': attr.key,
                'value': attr.value
            })
        
        return Response({
            'success': True,
            'message': f'Cleaned up attributes for product {product.name}',
            'removed_count': removed_count,
            'removed_attributes': [{'key': attr.key, 'value': attr.value} for attr in attributes_to_remove],
            'kept_attributes': [{'key': attr.key, 'value': attr.value} for attr in attributes_to_keep],
            'current_attributes': updated_attributes
        })
        
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400) 


@csrf_exempt
def assign_sample_attributes(request):
    """
    Development endpoint: Assigns sample attributes (brand, color) to every product if missing.
    """
    from .models import Product, Attribute, NewAttributeValue, ProductAttributeValue
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    brand_attr, _ = Attribute.objects.get_or_create(key='brand', defaults={'name': 'Brand'})
    color_attr, _ = Attribute.objects.get_or_create(key='color', defaults={'name': 'Color'})
    brand_value, _ = NewAttributeValue.objects.get_or_create(attribute=brand_attr, value='SampleBrand')
    color_value, _ = NewAttributeValue.objects.get_or_create(attribute=color_attr, value='Black')
    
    count = 0
    for product in Product.objects.all():
        # Brand
        if not ProductAttributeValue.objects.filter(product=product, attribute=brand_attr).exists():
            ProductAttributeValue.objects.create(product=product, attribute=brand_attr, attribute_value=brand_value)
            count += 1
        # Color
        if not ProductAttributeValue.objects.filter(product=product, attribute=color_attr).exists():
            ProductAttributeValue.objects.create(product=product, attribute=color_attr, attribute_value=color_value)
            count += 1
    return JsonResponse({'status': 'ok', 'attributes_added': count})


# Wishlist API Views
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Wishlist
from .serializers import WishlistSerializer, WishlistCreateSerializer, WishlistSimpleSerializer, ProductSerializer
from rest_framework.generics import ListCreateAPIView, DestroyAPIView


class WishlistListCreateAPIView(ListCreateAPIView):
    """
    API view to list all wishlist items for authenticated user or create a new one
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Wishlist.objects.filter(customer=self.request.user).select_related(
            'product', 'product__category'
        ).prefetch_related('product__images')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return WishlistCreateSerializer
        return WishlistSerializer
    
    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Override create method to provide better error handling"""
        try:
            return super().create(request, *args, **kwargs)
        except serializers.ValidationError as e:
            # Handle validation errors (e.g., product already in wishlist)
            return Response({
                'success': False,
                'error': 'validation_error',
                'message': str(e.detail),
                'details': e.detail if hasattr(e, 'detail') else str(e),
                'timestamp': timezone.now().isoformat(),
                'status_code': 400
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Handle unexpected errors
            return Response({
                'success': False,
                'error': 'internal_error',
                'message': 'خطای داخلی سرور',
                'details': str(e),
                'timestamp': timezone.now().isoformat(),
                'status_code': 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def handle_exception(self, exc):
        """Custom exception handler for better error responses"""
        if isinstance(exc, PermissionDenied):
            return Response({
                'success': False,
                'error': 'permission_denied',
                'message': 'شما مجوز دسترسی به این عملیات را ندارید',
                'details': 'Authentication required',
                'timestamp': timezone.now().isoformat(),
                'status_code': 403
            }, status=status.HTTP_403_FORBIDDEN)
        
        if isinstance(exc, AuthenticationFailed):
            return Response({
                'success': False,
                'error': 'authentication_failed',
                'message': 'احراز هویت ناموفق بود',
                'details': 'Please provide valid authentication credentials',
                'timestamp': timezone.now().isoformat(),
                'status_code': 401
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Call parent exception handler for other exceptions
        return super().handle_exception(exc)
    
    def list(self, request, *args, **kwargs):
        """Override list method to return products with pagination in desired format"""
        from rest_framework.response import Response
        from rest_framework.pagination import PageNumberPagination
        
        queryset = self.get_queryset()
        
        # Apply pagination
        paginator = ProductPagination()
        paginated_wishlist = paginator.paginate_queryset(queryset, request)
        
        # Extract products from wishlist items
        products = []
        for wishlist_item in paginated_wishlist:
            product_serializer = ProductSerializer(wishlist_item.product)
            products.append(product_serializer.data)
        
        # Get pagination info
        paginator_info = paginator.get_paginated_response(products)
        pagination_data = {
            'current_page': paginator.page.number,
            'total_pages': paginator.page.paginator.num_pages,
            'total_items': paginator.page.paginator.count,
            'has_next': paginator.page.has_next(),
            'has_previous': paginator.page.has_previous(),
        }
        
        return Response({
            'products': products,
            'pagination': pagination_data
        })


class WishlistDestroyAPIView(DestroyAPIView):
    """
    API view to remove a product from wishlist by product_id
    """
    permission_classes = [IsAuthenticated]
    serializer_class = WishlistSimpleSerializer
    lookup_field = 'product_id'
    
    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        if not product_id:
            return Wishlist.objects.none()
        return Wishlist.objects.filter(customer=self.request.user, product_id=product_id)
    
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except Exception as e:
            return Response({
                'error': 'Failed to remove item from wishlist',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_wishlist(request):
    """
    API endpoint to toggle product in/out of wishlist
    """
    product_id = request.data.get('product_id')
    
    if not product_id:
        return Response({'error': 'Product ID is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        product = Product.objects.get(id=product_id, is_active=True)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
    
    wishlist_item, created = Wishlist.objects.get_or_create(
        customer=request.user,
        product=product
    )
    
    if created:
        return Response({
            'success': True,
            'action': 'added',
            'message': 'محصول به لیست علاقه‌مندی اضافه شد'
        }, status=status.HTTP_201_CREATED)
    else:
        wishlist_item.delete()
        return Response({
            'success': True,
            'action': 'removed',
            'message': 'محصول از لیست علاقه‌مندی حذف شد'
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wishlist_status(request):
    """
    API endpoint to check if products are in wishlist
    """
    product_ids = request.GET.getlist('product_ids')
    
    if not product_ids:
        return Response({'error': 'Product IDs are required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        product_ids = [int(pid) for pid in product_ids if pid.isdigit()]
    except ValueError:
        return Response({'error': 'Invalid product IDs'}, status=status.HTTP_400_BAD_REQUEST)
    
    wishlist_items = Wishlist.objects.filter(
        customer=request.user,
        product_id__in=product_ids
    ).values_list('product_id', flat=True)
    
    wishlist_status = {
        str(pid): pid in wishlist_items 
        for pid in product_ids
    }
    
    return Response({
        'success': True,
        'wishlist_status': wishlist_status
    }, status=status.HTTP_200_OK) 


# Gender-based category and product API endpoints

@api_view(['GET'])
def api_categories_with_gender(request):
    """
    Enhanced category API that handles both container and direct categories
    URL: /api/categories/
    
    Returns:
    - Container categories: Categories with subcategories (like 'ساعت')
    - Direct categories: Categories with direct products (like 'کتاب')
    - Each category includes type information and product counts
    """
    try:
        # Get main categories (no parent) with prefetch for optimization
        main_categories = Category.objects.filter(parent=None, is_visible=True).prefetch_related(
            'subcategories',
            'product_set'
        )
        
        categories_data = []
        for category in main_categories:
            effective_type = category.get_effective_category_type()
            
            category_data = {
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'parent_id': None,
                'type': effective_type,  # 'container' or 'direct'
                'product_count': category.get_product_count(),
                'subcategories': []
            }
            
            if effective_type == 'container':
                # For container categories, include subcategory details recursively
                def get_subcategories_recursive(parent_category):
                    subcategories = []
                    for subcategory in parent_category.subcategories.filter(is_visible=True):
                        gender = subcategory.get_gender()
                        subcategory_data = {
                            'id': subcategory.id,
                            'name': subcategory.name,
                            'label': subcategory.get_display_name(),
                            'parent_id': parent_category.id,
                            'gender': gender,
                            'product_count': subcategory.get_product_count(),
                            'subcategories': get_subcategories_recursive(subcategory)
                        }
                        subcategories.append(subcategory_data)
                    return subcategories
                
                category_data['subcategories'] = get_subcategories_recursive(category)
            
            # Include all visible categories regardless of product count
            categories_data.append(category_data)
        
        return Response({
            'success': True,
            'categories': categories_data,
            'usage_guide': {
                'container_categories': 'Use subcategories for product loading',
                'direct_categories': 'Load products directly from main category'
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_products_by_gender_category(request):
    """
    Get products filtered by category and/or gender
    URL: /api/products/
    Parameters:
        - category: Category name (e.g., 'ساعت')
        - gender: Gender filter ('مردانه', 'زنانه', 'یونیسکس')
        - page: Page number for pagination
        - limit: Items per page (default: 20)
    """
    try:
        category_name = request.GET.get('category')
        gender = request.GET.get('gender')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        search_query = request.GET.get('search', '')
        
        # Start with active products
        products = Product.objects.filter(is_active=True)
        
        # Apply category filter
        if category_name:
            # Method 1: Try gender-specific category first
            if gender:
                gender_category_name = f"{category_name} {gender}"
                gender_category = Category.objects.filter(name=gender_category_name).first()
                if gender_category:
                    products = products.filter(category=gender_category)
                else:
                    # Fallback to attribute-based filtering
                    products = filter_by_category_and_gender_attribute(products, category_name, gender)
            else:
                # Get all products from main category and its subcategories
                main_category = Category.objects.filter(name=category_name).first()
                if main_category:
                    all_subcategories = [main_category] + main_category.get_all_subcategories()
                    products = products.filter(category__in=all_subcategories)
        
        # Apply search filter
        if search_query:
            products = products.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(model__icontains=search_query)
            )
        
        # Order by creation date (newest first)
        products = products.order_by('-created_at')
        
        # Paginate results
        paginator = Paginator(products, limit)
        page_obj = paginator.get_page(page)
        
        # Serialize products
        products_data = []
        for product in page_obj:
            # Get gender from attributes or category name
            product_gender = get_product_gender(product)
            
            product_data = {
                'id': product.id,
                'name': product.name,
                'price': float(product.price_toman),
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'description': product.description,
                'category_id': product.category.id,
                'category_name': product.category.name,
                'category_label': product.category.get_display_name(),
                'gender': product_gender,
                'image_url': get_product_image_url(product, request),
                'attributes': get_product_attributes(product),
                'created_at': get_unix_timestamp(product.created_at),
                'supplier': product.supplier.name if product.supplier else None
            }
            products_data.append(product_data)
        
        return Response({
            'success': True,
            'products': products_data,
            'pagination': {
                'page': page,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            },
            'filters': {
                'category': category_name,
                'gender': gender,
                'search': search_query
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

# Helper Functions
def extract_gender_from_category_name(category_name):
    """Extract gender from category name"""
    if 'مردانه' in category_name:
        return 'مردانه'
    elif 'زنانه' in category_name:
        return 'زنانه'
    elif 'یونیسکس' in category_name:
        return 'یونیسکس'
    return None

def get_product_gender(product):
    """Get product gender from attributes or category name"""
    # First try to get from attributes
    try:
        gender_attr = product.attribute_values.filter(
            attribute__key='gender'
        ).first()
        if gender_attr:
            if gender_attr.attribute_value:
                return gender_attr.attribute_value.value
            return gender_attr.custom_value
    except:
        pass
    
    # Fallback to category name
    return product.category.get_gender()

def get_product_image_url(product):
    """Get product image URL"""
    try:
        # Assuming you have a ProductImage model
        first_image = product.productimage_set.first()
        if first_image and first_image.image:
            return first_image.image.url
    except:
        pass
    return None

def get_product_attributes(product):
    """Get only the categorization attribute for the product's category"""
    attributes = []
    try:
        # Get the category's chosen categorization attribute key
        category = product.category
        categorization_key = category.get_categorization_attribute_key()
        
        if categorization_key:
            # Find the CategoryAttribute to get the label
            try:
                category_attr = category.category_attributes.get(key=categorization_key)
                
                # IMPORTANT: The brand attributes are stored in ProductAttribute model, not ProductAttributeValue!
                # Check if product has this attribute in ProductAttribute model
                try:
                    # First try to find by exact key match
                    product_attr = product.legacy_attribute_set.get(key=categorization_key)
                    attributes.append({
                        'key': categorization_key,
                        'value': product_attr.value,
                        'display_name': category_attr.label_fa
                    })
                except:
                    # If not found by exact key, try to find by similar keys
                    # This handles cases where CategoryAttribute.key="brand" but ProductAttribute.key="برند"
                    for attr in product.legacy_attribute_set.all():
                        if (attr.key == categorization_key or 
                            attr.key == category_attr.label_fa or
                            attr.key.lower() == categorization_key.lower()):
                            attributes.append({
                                'key': categorization_key,  # Use the category's key for consistency
                                'value': attr.value,
                                'display_name': category_attr.label_fa
                            })
                            break
                        
            except CategoryAttribute.DoesNotExist:
                # Category doesn't have this attribute defined
                pass
                
    except Exception as e:
        # Log the error for debugging
        pass
        
    return attributes

def get_unix_timestamp(datetime_obj):
    """Convert datetime to Unix timestamp (seconds since 1970)"""
    return int(datetime_obj.timestamp())

def filter_by_category_and_gender_attribute(products, category_name, gender):
    """Filter products by category and gender using attributes"""
    # Get main category
    main_category = Category.objects.filter(name=category_name).first()
    if not main_category:
        return products.none()
    
    # Get all subcategories
    all_subcategories = [main_category] + main_category.get_all_subcategories()
    
    # Filter by category and gender attribute
    return products.filter(
        category__in=all_subcategories,
        attribute_values__attribute__key='gender',
        attribute_values__attribute_value__value=gender
    ).distinct() 

@api_view(['GET'])
def api_unified_products(request):
    """
    Unified product loading endpoint that handles both category types seamlessly
    URL: /api/products/unified/
    
    Parameters:
        - category_id: Main category ID
        - subcategory_id: (Optional) Specific subcategory ID for container categories
        - gender: (Optional) Gender filter for container categories
        - search: (Optional) Search query
        - page: Page number for pagination
        - limit: Items per page (default: 20)
    
    This eliminates the need for nested loops on frontend:
    - For container categories: Automatically loads from appropriate subcategory
    - For direct categories: Loads directly from main category
    """
    try:
        category_id = request.GET.get('category_id')
        subcategory_id = request.GET.get('subcategory_id')
        gender = request.GET.get('gender')
        search_query = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        # Handle both limit and per_page parameters (per_page takes precedence)
        per_page = request.GET.get('per_page')
        limit_param = request.GET.get('limit')
        
        if per_page:
            limit = int(per_page)
        elif limit_param:
            limit = int(limit_param)
        else:
            limit = 20
        
        if not category_id:
            return Response({
                'success': False,
                'error': 'category_id is required'
            }, status=400)
        
        # Get the main category
        try:
            main_category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Category not found'
            }, status=404)
        
        # Determine how to load products based on category type
        category_type = main_category.get_effective_category_type()
        
        if category_type == 'container':
            # Container category: load from subcategories
            if subcategory_id:
                # Specific subcategory requested
                try:
                    subcategory = Category.objects.get(id=subcategory_id, parent=main_category)
                    products = subcategory.get_all_products()
                    used_category = subcategory
                except Category.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': 'Subcategory not found'
                    }, status=404)
            elif gender:
                # Gender-based filtering for container categories
                gender_subcategory = main_category.subcategories.filter(
                    name__icontains=gender
                ).first()
                
                if gender_subcategory:
                    products = gender_subcategory.get_all_products()
                    used_category = gender_subcategory
                else:
                    # No specific gender subcategory found, load all
                    products = main_category.get_all_products()
                    used_category = main_category
            else:
                # Load all products from all subcategories
                products = main_category.get_all_products()
                used_category = main_category
        else:
            # Direct category: load products directly
            products = main_category.get_all_products()
            used_category = main_category
        
        # Apply search filter
        if search_query:
            products = products.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(model__icontains=search_query) |
                Q(sku__icontains=search_query)
            )
        
        # Order by creation date (newest first)
        products = products.order_by('-created_at')
        
        # Pagination
        from django.core.paginator import Paginator
        paginator = Paginator(products, limit)
        
        try:
            page_obj = paginator.page(page)
        except:
            page_obj = paginator.page(1)
        
        # Serialize products
        products_data = []
        for product in page_obj:
            product_data = {
                'id': product.id,
                'name': product.name,
                'price_toman': float(product.price_toman) if product.price_toman else None,
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'description': product.description,
                'category_id': product.category.id,
                'category_name': product.category.name,
                'is_active': product.is_active,
                'is_new_arrival': product.is_new_arrival,
                'created_at': get_unix_timestamp(product.created_at),
                'images': [
                    {
                        'url': request.build_absolute_uri(img.image.url),
                        'is_primary': img.is_primary
                    } for img in product.images.all()
                ] if hasattr(product, 'images') else [],
                'attributes': get_product_attributes(product),
                'supplier': product.supplier.name if product.supplier else None
            }
            products_data.append(product_data)
        
        return Response({
            'success': True,
            'products': products_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'items_per_page': limit
            },
            'category_info': {
                'main_category': {
                    'id': main_category.id,
                    'name': main_category.name,
                    'type': category_type
                },
                'used_category': {
                    'id': used_category.id,
                    'name': used_category.name
                },
                'available_subcategories': [
                    {
                        'id': sub.id,
                        'name': sub.name,
                        'gender': sub.get_gender(),
                        'product_count': sub.get_product_count()
                    }
                    for sub in main_category.subcategories.all()
                ] if category_type == 'container' else []
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500) 

@api_view(['GET'])
def api_organized_categories(request):
    """
    Returns pre-organized categories ready for mobile app UI
    URL: /api/categories/organized/
    
    Returns:
    - men: Array of men's categories (leaf categories only)
    - women: Array of women's categories (leaf categories only)  
    - general: Array of general categories (books, etc.)
    - unisex: Array of unisex categories
    
    This eliminates client-side processing and provides optimal performance.
    """
    try:
        # Get only visible leaf categories (categories with products, no subcategories)
        visible_categories = Category.objects.filter(
            is_visible=True
        ).prefetch_related('parent', 'product_set')
        
        organized = {
            'men': [],
            'women': [],
            'unisex': [],
            'general': []
        }
        
        for category in visible_categories:
            # Skip container categories (they should not be visible directly)
            if category.is_container_category():
                continue
                
            # Get display section (auto-detect if not set)
            section = category.get_display_section()
            
            category_data = {
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'product_count': category.get_product_count(),
                'parent_name': category.parent.name if category.parent else None,
                'parent_id': category.parent.id if category.parent else None,
                'gender': category.get_gender(),
                'section': section
            }
            
            organized[section].append(category_data)
        
        # Sort each section by product count (most popular first)
        for section in organized:
            organized[section].sort(key=lambda x: x['product_count'], reverse=True)
        
        return Response({
            'success': True,
            'categories': organized,
            'summary': {
                'men_count': len(organized['men']),
                'women_count': len(organized['women']),
                'unisex_count': len(organized['unisex']),
                'general_count': len(organized['general']),
                'total_categories': sum(len(organized[section]) for section in organized)
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500) 

@api_view(['GET'])
def api_direct_categories(request):
    """
    Returns only direct categories (non-container categories) where is_container_category() returns False.
    These are categories that have products directly, not through subcategories.
    """
    try:
        all_categories = Category.objects.filter(is_visible=True).order_by('name')
        direct_categories = []
        
        for category in all_categories:
            if not category.is_container_category():
                category_data = {
                    'id': category.id,
                    'name': category.name,
                    'label': category.get_display_name(),
                    'parent_id': category.parent.id if category.parent else None,
                    'parent_name': category.parent.name if category.parent else None,
                    'product_count': category.get_product_count(),
                    'display_section': category.get_display_section(),
                    'gender': category.get_gender(),
                    'is_container': False,
                    'category_type': category.get_effective_category_type()
                }
                direct_categories.append(category_data)
        
        return Response({
            'success': True,
            'count': len(direct_categories),
            'categories': direct_categories,
            'description': 'Direct categories that contain products directly (not through subcategories)'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 

@api_view(['GET'])
def api_category_detail(request, category_id):
    """
    Get detailed information about a specific category and its subcategories
    URL: /api/category/<category_id>/
    
    Returns:
    - Category details
    - All subcategories (recursive)
    - Product count
    - Category type and hierarchy information
    """
    try:
        category = Category.objects.filter(id=category_id, is_visible=True).first()
        
        if not category:
            return Response({
                'success': False,
                'error': 'Category not found or not visible'
            }, status=404)
        
        def get_subcategories_recursive(parent_category):
            subcategories = []
            for subcategory in parent_category.subcategories.filter(is_visible=True):
                gender = subcategory.get_gender()
                subcategory_data = {
                    'id': subcategory.id,
                    'name': subcategory.name,
                    'label': subcategory.get_display_name(),
                    'parent_id': parent_category.id,
                    'parent_name': parent_category.name,
                    'gender': gender,
                    'product_count': subcategory.get_product_count(),
                    'type': subcategory.get_effective_category_type(),
                    'is_visible': subcategory.is_visible,
                    'subcategories': get_subcategories_recursive(subcategory)
                }
                subcategories.append(subcategory_data)
            return subcategories
        
        # Get category hierarchy
        hierarchy = []
        current = category
        while current:
            hierarchy.insert(0, {
                'id': current.id,
                'name': current.name,
                'label': current.get_display_name()
            })
            current = current.parent
        
        category_data = {
            'id': category.id,
            'name': category.name,
            'label': category.get_display_name(),
            'parent_id': category.parent.id if category.parent else None,
            'parent_name': category.parent.name if category.parent else None,
            'type': category.get_effective_category_type(),
            'product_count': category.get_product_count(),
            'gender': category.get_gender(),
            'is_visible': category.is_visible,
            'hierarchy': hierarchy,
            'subcategories': get_subcategories_recursive(category),
            'total_subcategories': len(category.get_all_subcategories())
        }
        
        return Response({
            'success': True,
            'category': category_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_category_products(request, category_id):
    """
    Get products for a specific category (including subcategories)
    URL: /api/category/<category_id>/products/
    
    Parameters:
    - page: Page number for pagination
    - limit: Items per page (default: 20)
    - include_subcategories: Include products from subcategories (default: true)
    """
    try:
        category = Category.objects.filter(id=category_id, is_visible=True).first()
        
        if not category:
            return Response({
                'success': False,
                'error': 'Category not found or not visible'
            }, status=404)
        
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        include_subcategories = request.GET.get('include_subcategories', 'true').lower() == 'true'
        
        # Get products
        if include_subcategories:
            # Get all products from this category and all its subcategories
            all_subcategories = [category] + list(category.get_all_subcategories())
            products = Product.objects.filter(
                category__in=all_subcategories,
                is_active=True
            )
        else:
            # Get only products directly assigned to this category
            products = category.product_set.filter(is_active=True)
        
        # Order by creation date (newest first)
        products = products.order_by('-created_at')
        
        # Paginate results
        paginator = Paginator(products, limit)
        page_obj = paginator.get_page(page)
        
        # Serialize products
        products_data = []
        for product in page_obj:
            product_gender = get_product_gender(product)
            
            product_data = {
                'id': product.id,
                'name': product.name,
                'price': float(product.price_toman),
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'description': product.description,
                'category_id': product.category.id,
                'category_name': product.category.name,
                'category_label': product.category.get_display_name(),
                'gender': product_gender,
                'image_url': get_product_image_url(product, request),
                'attributes': get_product_attributes(product),
                'created_at': get_unix_timestamp(product.created_at),
                'supplier': product.supplier.name if product.supplier else None
            }
            products_data.append(product_data)
        
        return Response({
            'success': True,
            'category': {
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'type': category.get_effective_category_type(),
                'product_count': category.get_product_count()
            },
            'products': products_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': page_obj.paginator.num_pages,
                'total_products': page_obj.paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500) 

@api_view(['GET'])
def api_subcategory_products(request, parent_category_id):
    """
    Get products from subcategories of a specific parent category
    URL: /api/category/<parent_category_id>/subcategories/products/
    
    This endpoint is useful for getting products from sub-subcategories
    without including products from the parent category itself.
    
    Parameters:
    - page: Page number for pagination
    - limit: Items per page (default: 20)
    - subcategory_id: Specific subcategory ID to filter (optional)
    """
    try:
        parent_category = Category.objects.filter(id=parent_category_id, is_visible=True).first()
        
        if not parent_category:
            return Response({
                'success': False,
                'error': 'Parent category not found or not visible'
            }, status=404)
        
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        subcategory_id = request.GET.get('subcategory_id')
        
        # Get all subcategories of the parent
        if subcategory_id:
            # Filter by specific subcategory
            subcategories = parent_category.subcategories.filter(
                id=subcategory_id, 
                is_visible=True
            )
        else:
            # Get all subcategories
            subcategories = parent_category.subcategories.filter(is_visible=True)
        
        # Get products from all subcategories (including their sub-subcategories)
        all_subcategory_ids = []
        for subcategory in subcategories:
            # Include the subcategory itself
            all_subcategory_ids.append(subcategory.id)
            # Include all its sub-subcategories
            sub_subcategories = subcategory.get_all_subcategories()
            all_subcategory_ids.extend([sub.id for sub in sub_subcategories])
        
        # Get products from all these categories
        products = Product.objects.filter(
            category_id__in=all_subcategory_ids,
            is_active=True
        ).order_by('-created_at')
        
        # Paginate results
        paginator = Paginator(products, limit)
        page_obj = paginator.get_page(page)
        
        # Serialize products
        products_data = []
        for product in page_obj:
            product_gender = get_product_gender(product)
            
            product_data = {
                'id': product.id,
                'name': product.name,
                'price': float(product.price_toman),
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'description': product.description,
                'category_id': product.category.id,
                'category_name': product.category.name,
                'category_label': product.category.get_display_name(),
                'category_parent_id': product.category.parent.id if product.category.parent else None,
                'category_parent_name': product.category.parent.name if product.category.parent else None,
                'gender': product_gender,
                'image_url': get_product_image_url(product, request),
                'attributes': get_product_attributes(product),
                'created_at': get_unix_timestamp(product.created_at),
                'supplier': product.supplier.name if product.supplier else None
            }
            products_data.append(product_data)
        
        # Get subcategory information
        subcategories_info = []
        for subcategory in subcategories:
            subcategories_info.append({
                'id': subcategory.id,
                'name': subcategory.name,
                'label': subcategory.get_display_name(),
                'product_count': subcategory.get_product_count(),
                'gender': subcategory.get_gender(),
                'type': subcategory.get_effective_category_type()
            })
        
        return Response({
            'success': True,
            'parent_category': {
                'id': parent_category.id,
                'name': parent_category.name,
                'label': parent_category.get_display_name(),
                'type': parent_category.get_effective_category_type()
            },
            'subcategories': subcategories_info,
            'products': products_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': page_obj.paginator.num_pages,
                'total_products': page_obj.paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500) 

@api_view(['GET'])
def api_hierarchical_category_products(request, category_path):
    """
    Get products from a specific category in a hierarchical path
    URL: /api/category/{category_id1}/{category_id2}/{category_id3}/.../products/
    
    Example: /api/category/1005/1006/1016/products/
    This gets products from category 1016, which is a subcategory of 1006, 
    which is a subcategory of 1005.
    
    Parameters:
    - page: Page number for pagination
    - limit: Items per page (default: 20)
    - include_subcategories: Include products from subcategories (default: false)
    """
    try:
        if not category_path:
            return Response({
                'success': False,
                'error': 'No category path provided'
            }, status=400)
        
        # Convert category_path to list of integers
        try:
            category_id_list = [int(cid) for cid in category_path.split('/') if cid.isdigit()]
        except ValueError:
            return Response({
                'success': False,
                'error': 'Invalid category ID format'
            }, status=400)
        
        # Validate the hierarchical path
        current_category = None
        hierarchy = []
        
        for i, category_id in enumerate(category_id_list):
            if current_category is None:
                # First category - should be a main category (no parent)
                category = Category.objects.filter(id=category_id, parent=None, is_visible=True).first()
            else:
                # Subsequent categories - should be subcategories of the previous one
                category = Category.objects.filter(
                    id=category_id, 
                    parent=current_category, 
                    is_visible=True
                ).first()
            
            if not category:
                return Response({
                    'success': False,
                    'error': f'Category {category_id} not found or invalid in hierarchy'
                }, status=404)
            
            hierarchy.append({
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'level': i + 1
            })
            
            current_category = category
        
        # Get the target category (last in the path)
        target_category = current_category
        
        # Get parameters
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        include_subcategories = request.GET.get('include_subcategories', 'false').lower() == 'true'
        
        # Get products
        if include_subcategories:
            # Get all products from this category and all its subcategories
            all_subcategories = [target_category] + list(target_category.get_all_subcategories())
            products = Product.objects.filter(
                category__in=all_subcategories,
                is_active=True
            )
        else:
            # Get only products directly assigned to this category
            products = target_category.product_set.filter(is_active=True)
        
        # Order by creation date (newest first)
        products = products.order_by('-created_at')
        
        # Paginate results
        paginator = Paginator(products, limit)
        page_obj = paginator.get_page(page)
        
        # Serialize products
        products_data = []
        for product in page_obj:
            product_gender = get_product_gender(product)
            
            product_data = {
                'id': product.id,
                'name': product.name,
                'price': float(product.price_toman),
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'description': product.description,
                'category_id': product.category.id,
                'category_name': product.category.name,
                'category_label': product.category.get_display_name(),
                'gender': product_gender,
                'image_url': get_product_image_url(product, request),
                'attributes': get_product_attributes(product),
                'created_at': get_unix_timestamp(product.created_at),
                'supplier': product.supplier.name if product.supplier else None
            }
            products_data.append(product_data)
        
        return Response({
            'success': True,
            'hierarchy': hierarchy,
            'target_category': {
                'id': target_category.id,
                'name': target_category.name,
                'label': target_category.get_display_name(),
                'type': target_category.get_effective_category_type(),
                'product_count': target_category.get_product_count(),
                'gender': target_category.get_gender()
            },
            'products': products_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': page_obj.paginator.num_pages,
                'total_products': page_obj.paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_hierarchical_category_detail(request, category_path):
    """
    Get detailed information about a category in a hierarchical path
    URL: /api/category/{category_id1}/{category_id2}/{category_id3}/.../
    
    Example: /api/category/1005/1006/1016/
    This gets details about category 1016, which is a subcategory of 1006, 
    which is a subcategory of 1005.
    """
    try:
        if not category_path:
            return Response({
                'success': False,
                'error': 'No category path provided'
            }, status=400)
        
        # Convert category_path to list of integers
        try:
            category_id_list = [int(cid) for cid in category_path.split('/') if cid.isdigit()]
        except ValueError:
            return Response({
                'success': False,
                'error': 'Invalid category ID format'
            }, status=400)
        
        # Validate the hierarchical path
        current_category = None
        hierarchy = []
        
        for i, category_id in enumerate(category_id_list):
            if current_category is None:
                # First category - should be a main category (no parent)
                category = Category.objects.filter(id=category_id, parent=None, is_visible=True).first()
            else:
                # Subsequent categories - should be subcategories of the previous one
                category = Category.objects.filter(
                    id=category_id, 
                    parent=current_category, 
                    is_visible=True
                ).first()
            
            if not category:
                return Response({
                    'success': False,
                    'error': f'Category {category_id} not found or invalid in hierarchy'
                }, status=404)
            
            hierarchy.append({
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'level': i + 1
            })
            
            current_category = category
        
        # Get the target category (last in the path)
        target_category = current_category
        
        def get_subcategories_recursive(parent_category):
            subcategories = []
            for subcategory in parent_category.subcategories.filter(is_visible=True):
                gender = subcategory.get_gender()
                subcategory_data = {
                    'id': subcategory.id,
                    'name': subcategory.name,
                    'label': subcategory.get_display_name(),
                    'parent_id': parent_category.id,
                    'parent_name': parent_category.name,
                    'gender': gender,
                    'product_count': subcategory.get_product_count(),
                    'type': subcategory.get_effective_category_type(),
                    'is_visible': subcategory.is_visible,
                    'subcategories': get_subcategories_recursive(subcategory)
                }
                subcategories.append(subcategory_data)
            return subcategories
        
        category_data = {
            'id': target_category.id,
            'name': target_category.name,
            'label': target_category.get_display_name(),
            'parent_id': target_category.parent.id if target_category.parent else None,
            'parent_name': target_category.parent.name if target_category.parent else None,
            'type': target_category.get_effective_category_type(),
            'product_count': target_category.get_product_count(),
            'gender': target_category.get_gender(),
            'is_visible': target_category.is_visible,
            'hierarchy': hierarchy,
            'subcategories': get_subcategories_recursive(target_category),
            'total_subcategories': len(target_category.get_all_subcategories())
        }
        
        return Response({
            'success': True,
            'category': category_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500) 


# New improved category system API endpoints
@api_view(['GET'])
def api_improved_categories(request):
    """
    New improved category API with better structure
    URL: /api/improved-categories/
    
    Returns a cleaner, more organized category structure:
    - Groups (e.g., ساعت, کتاب, پوشاک)
    - Subgroups within groups (e.g., تی‌شرت, شلوار)
    - Gender variants for each subgroup
    - Product counts at each level
    """
    try:
        # Get all active category groups
        groups = CategoryGroup.objects.filter(is_active=True).prefetch_related(
            'subgroups__categories__product_set',
            'subgroups__children__categories__product_set'
        ).order_by('display_order', 'name')
        
        groups_data = []
        for group in groups:
            group_data = {
                'id': group.id,
                'name': group.name,
                'label': group.get_display_name(),
                'description': group.description,
                'icon': group.icon,
                'supports_gender': group.supports_gender,
                'product_count': group.get_product_count(),
                'subgroups': []
            }
            
            # Get subgroups for this group
            subgroups = group.subgroups.filter(is_active=True).order_by('display_order', 'name')
            for subgroup in subgroups:
                subgroup_data = {
                    'id': subgroup.id,
                    'name': subgroup.name,
                    'label': subgroup.get_display_name(),
                    'product_count': subgroup.get_product_count(),
                    'categories': []
                }
                
                # Get categories for this subgroup
                categories = subgroup.categories.filter(is_visible=True).select_related('gender')
                
                if group.supports_gender:
                    # Group by gender
                    gender_categories = {}
                    for category in categories:
                        gender_name = category.get_gender() or 'عمومی'
                        if gender_name not in gender_categories:
                            gender_categories[gender_name] = {
                                'gender': gender_name,
                                'category_id': category.id,
                                'product_count': category.get_product_count()
                            }
                    
                    # Add gender categories to subgroup
                    for gender_data in gender_categories.values():
                        subgroup_data['categories'].append(gender_data)
                else:
                    # No gender support, just add the category directly
                    if categories.exists():
                        category = categories.first()
                        subgroup_data['categories'].append({
                            'gender': None,
                            'category_id': category.id,
                            'product_count': category.get_product_count()
                        })
                
                # Add children subgroups if any
                children = subgroup.children.filter(is_active=True).order_by('display_order', 'name')
                if children.exists():
                    subgroup_data['children'] = []
                    for child in children:
                        child_data = {
                            'id': child.id,
                            'name': child.name,
                            'label': child.get_display_name(),
                            'product_count': child.get_product_count(),
                            'categories': []
                        }
                        
                        # Get categories for child subgroup
                        child_categories = child.categories.filter(is_visible=True).select_related('gender')
                        if group.supports_gender:
                            child_gender_categories = {}
                            for category in child_categories:
                                gender_name = category.get_gender() or 'عمومی'
                                if gender_name not in child_gender_categories:
                                    child_gender_categories[gender_name] = {
                                        'gender': gender_name,
                                        'category_id': category.id,
                                        'product_count': category.get_product_count()
                                    }
                            
                            for gender_data in child_gender_categories.values():
                                child_data['categories'].append(gender_data)
                        else:
                            if child_categories.exists():
                                category = child_categories.first()
                                child_data['categories'].append({
                                    'gender': None,
                                    'category_id': category.id,
                                    'product_count': category.get_product_count()
                                })
                        
                        subgroup_data['children'].append(child_data)
                
                group_data['subgroups'].append(subgroup_data)
            
            groups_data.append(group_data)
        
        return Response({
            'success': True,
            'groups': groups_data,
            'usage_guide': {
                'groups': 'Main category groups (e.g., ساعت, کتاب)',
                'subgroups': 'Subcategories within groups (e.g., تی‌شرت, شلوار)',
                'categories': 'Gender-specific categories for product loading',
                'category_id': 'Use this ID to load products from /api/category/{id}/products/'
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
def api_group_products(request, group_id):
    """
    Get products for a specific category group
    URL: /api/groups/{group_id}/products/
    Parameters:
        - gender: Filter by gender ('مردانه', 'زنانه', 'یونیسکس')
        - subgroup: Filter by subgroup ID
        - page: Page number
        - limit: Items per page
    """
    try:
        group = CategoryGroup.objects.get(id=group_id, is_active=True)
        gender = request.GET.get('gender')
        subgroup_id = request.GET.get('subgroup')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        
        # Get all categories in this group
        categories = group.categories.filter(is_visible=True)
        
        # Apply filters
        if gender:
            categories = categories.filter(gender__display_name=gender)
        
        if subgroup_id:
            categories = categories.filter(subgroup_id=subgroup_id)
        
        # Get products from filtered categories
        category_ids = categories.values_list('id', flat=True)
        products = Product.objects.filter(
            category_id__in=category_ids,
            is_active=True
        ).select_related('category', 'supplier').prefetch_related('images')
        
        # Paginate results
        paginator = Paginator(products, limit)
        page_obj = paginator.get_page(page)
        
        products_data = []
        for product in page_obj:
            product_data = {
                'id': product.id,
                'name': product.name,
                'price_toman': float(product.price_toman),
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'description': product.description,
                'category': {
                    'id': product.category.id,
                    'name': product.category.get_clean_name(),
                    'gender': product.category.get_gender()
                },
                'images': [get_product_image_url(product, request)],
                'is_new_arrival': product.is_new_arrival,
                'stock_quantity': product.stock_quantity
            }
            products_data.append(product_data)
        
        return Response({
            'success': True,
            'group': {
                'id': group.id,
                'name': group.name,
                'label': group.get_display_name()
            },
            'products': products_data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })
        
    except CategoryGroup.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Category group not found'
        }, status=404)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_genders_list(request):
    """
    Get all available genders from CategoryGender table
    URL: /api/genders/
    
    Returns:
    - List of all active genders with their display names
    """
    try:
        genders = CategoryGender.objects.filter(is_active=True).order_by('display_order', 'name')
        
        genders_data = []
        for gender in genders:
            gender_data = {
                'id': gender.id,
                'name': gender.name,
                'display_name': gender.display_name,
                'display_order': gender.display_order
            }
            genders_data.append(gender_data)
        
        return Response({
            'success': True,
            'genders': genders_data,
            'total_count': len(genders_data)
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_categories_by_gender(request):
    """
    Get categories filtered by gender using the CategoryGender table
    URL: /api/categories/by-gender/
    
    Parameters:
        - gender_id: ID of the gender from CategoryGender table
        - gender_name: Name of the gender (men, women, unisex, general)
        - include_products: Whether to include product counts (default: true)
        - include_unassigned: Whether to include categories without gender assignment (default: false)
    
    Returns:
    - Categories that have the specified gender assigned
    """
    try:
        gender_id = request.GET.get('gender_id')
        gender_name = request.GET.get('gender_name')
        include_products = request.GET.get('include_products', 'true').lower() == 'true'
        include_unassigned = request.GET.get('include_unassigned', 'false').lower() == 'true'
        
        # Get the gender object
        gender = None
        if gender_id:
            gender = CategoryGender.objects.filter(id=gender_id, is_active=True).first()
        elif gender_name:
            gender = CategoryGender.objects.filter(name=gender_name, is_active=True).first()
        else:
            return Response({
                'success': False,
                'error': 'Either gender_id or gender_name parameter is required'
            }, status=400)
        
        if not gender:
            return Response({
                'success': False,
                'error': 'Gender not found'
            }, status=404)
        
        # Get categories with this gender
        if include_unassigned:
            # Include categories with this gender OR no gender assigned
            categories = Category.objects.filter(
                models.Q(gender=gender) | models.Q(gender__isnull=True),
                is_visible=True
            ).prefetch_related('product_set')
        else:
            # Only categories with this specific gender
            categories = Category.objects.filter(
                gender=gender,
                is_visible=True
            ).prefetch_related('product_set')
        
        categories_data = []
        unassigned_count = 0
        
        for category in categories:
            category_data = {
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'parent_id': category.parent.id if category.parent else None,
                'has_gender_assignment': category.gender is not None,
            }
            
            if category.gender:
                category_data['gender'] = {
                    'id': category.gender.id,
                    'name': category.gender.name,
                    'display_name': category.gender.display_name
                }
            else:
                category_data['gender'] = None
                unassigned_count += 1
            
            if include_products:
                category_data['product_count'] = category.get_product_count()
            
            categories_data.append(category_data)
        
        # Get statistics about gender assignments
        total_categories = Category.objects.filter(is_visible=True).count()
        assigned_categories = Category.objects.filter(gender__isnull=False, is_visible=True).count()
        
        return Response({
            'success': True,
            'gender': {
                'id': gender.id,
                'name': gender.name,
                'display_name': gender.display_name
            },
            'categories': categories_data,
            'total_count': len(categories_data),
            'statistics': {
                'total_categories': total_categories,
                'assigned_categories': assigned_categories,
                'unassigned_categories': total_categories - assigned_categories,
                'unassigned_in_results': unassigned_count
            },
            'message': f"Found {len(categories_data)} categories for gender '{gender.display_name}'"
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_parent_categories_by_gender(request):
    """
    Get parent categories (no parent) filtered by gender
    URL: /api/categories/parents/by-gender/
    
    Parameters:
        - gender_id: ID of the gender from CategoryGender table
        - gender_name: Name of the gender (men, women, unisex, general)
        - include_products: Whether to include product counts (default: true)
        - include_unassigned: Whether to include categories without gender assignment (default: false)
        - include_neutral: Whether to include neutral categories (general/unisex) (default: false)
    
    Returns:
    - Parent categories that have the specified gender assigned
    - Plus neutral categories when include_neutral=true
    """
    try:
        gender_id = request.GET.get('gender_id')
        gender_name = request.GET.get('gender_name')
        include_products = request.GET.get('include_products', 'true').lower() == 'true'
        include_unassigned = request.GET.get('include_unassigned', 'false').lower() == 'true'
        include_neutral = request.GET.get('include_neutral', 'false').lower() == 'true'
        
        # Get the gender object
        gender = None
        if gender_id:
            gender = CategoryGender.objects.filter(id=gender_id, is_active=True).first()
        elif gender_name:
            gender = CategoryGender.objects.filter(name=gender_name, is_active=True).first()
        else:
            return Response({
                'success': False,
                'error': 'Either gender_id or gender_name parameter is required'
            }, status=400)
        
        if not gender:
            return Response({
                'success': False,
                'error': 'Gender not found'
            }, status=404)
        
        # Build the query based on parameters
        if include_neutral:
            # Include categories with:
            # 1. The specified gender
            # 2. Neutral gender (general/unisex)
            # 3. No gender assigned (when include_unassigned=True)
            neutral_genders = CategoryGender.objects.filter(
                models.Q(name='general') | models.Q(name='unisex'),
                is_active=True
            )
            
            if include_unassigned:
                categories = Category.objects.filter(
                    models.Q(gender=gender) |
                    models.Q(gender__in=neutral_genders) |
                    models.Q(gender__isnull=True),
                    parent=None,  # Only parent categories
                    is_visible=True
                ).prefetch_related('product_set', 'subcategories')
            else:
                categories = Category.objects.filter(
                    models.Q(gender=gender) |
                    models.Q(gender__in=neutral_genders),
                    parent=None,  # Only parent categories
                    is_visible=True
                ).prefetch_related('product_set', 'subcategories')
        elif include_unassigned:
            # Include parent categories with this gender OR no gender assigned
            categories = Category.objects.filter(
                models.Q(gender=gender) | models.Q(gender__isnull=True),
                parent=None,  # Only parent categories
                is_visible=True
            ).prefetch_related('product_set', 'subcategories')
        else:
            # Only parent categories with this specific gender
            categories = Category.objects.filter(
                gender=gender,
                parent=None,  # Only parent categories
                is_visible=True
            ).prefetch_related('product_set', 'subcategories')
        
        categories_data = []
        unassigned_count = 0
        
        for category in categories:
            category_data = {
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'parent_id': None,  # Always None for parent categories
                'has_gender_assignment': category.gender is not None,
                'subcategory_count': category.subcategories.count(),
                'category_type': category.get_effective_category_type(),
            }
            
            if category.gender:
                category_data['gender'] = {
                    'id': category.gender.id,
                    'name': category.gender.name,
                    'display_name': category.gender.display_name
                }
            else:
                category_data['gender'] = None
                unassigned_count += 1
            
            if include_products:
                category_data['product_count'] = category.get_product_count()
            
            categories_data.append(category_data)
        
        # Get statistics about parent categories
        total_parent_categories = Category.objects.filter(parent=None, is_visible=True).count()
        assigned_parent_categories = Category.objects.filter(gender__isnull=False, parent=None, is_visible=True).count()
        
        # Count neutral categories if include_neutral is enabled
        neutral_count = 0
        if include_neutral:
            neutral_genders = CategoryGender.objects.filter(
                models.Q(name='general') | models.Q(name='unisex'),
                is_active=True
            )
            neutral_count = Category.objects.filter(
                gender__in=neutral_genders,
                parent=None,
                is_visible=True
            ).count()
        
        return Response({
            'success': True,
            'gender': {
                'id': gender.id,
                'name': gender.name,
                'display_name': gender.display_name
            },
            'categories': categories_data,
            'total_count': len(categories_data),
            'statistics': {
                'total_parent_categories': total_parent_categories,
                'assigned_parent_categories': assigned_parent_categories,
                'neutral_categories_included': neutral_count if include_neutral else 0,
                'unassigned_parent_categories': total_parent_categories - assigned_parent_categories,
                'unassigned_in_results': unassigned_count
            },
            'message': f"Found {len(categories_data)} parent categories for gender '{gender.display_name}'" + 
                      (f" (including {neutral_count} neutral categories)" if include_neutral else "")
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_child_categories_by_gender(request):
    """
    Get child categories (has parent) filtered by gender
    URL: /api/categories/children/by-gender/
    
    Parameters:
        - gender_id: ID of the gender from CategoryGender table
        - gender_name: Name of the gender (men, women, unisex, general)
        - include_products: Whether to include product counts (default: true)
        - include_unassigned: Whether to include categories without gender assignment (default: false)
    
    Returns:
    - Child categories that have the specified gender assigned
    """
    try:
        gender_id = request.GET.get('gender_id')
        gender_name = request.GET.get('gender_name')
        include_products = request.GET.get('include_products', 'true').lower() == 'true'
        include_unassigned = request.GET.get('include_unassigned', 'false').lower() == 'true'
        
        # Get the gender object
        gender = None
        if gender_id:
            gender = CategoryGender.objects.filter(id=gender_id, is_active=True).first()
        elif gender_name:
            gender = CategoryGender.objects.filter(name=gender_name, is_active=True).first()
        else:
            return Response({
                'success': False,
                'error': 'Either gender_id or gender_name parameter is required'
            }, status=400)
        
        if not gender:
            return Response({
                'success': False,
                'error': 'Gender not found'
            }, status=404)
        
        # Get child categories (has parent) with this gender
        if include_unassigned:
            # Include child categories with this gender OR no gender assigned
            categories = Category.objects.filter(
                models.Q(gender=gender) | models.Q(gender__isnull=True),
                parent__isnull=False,  # Only child categories
                is_visible=True
            ).prefetch_related('product_set', 'parent')
        else:
            # Only child categories with this specific gender
            categories = Category.objects.filter(
                gender=gender,
                parent__isnull=False,  # Only child categories
                is_visible=True
            ).prefetch_related('product_set', 'parent')
        
        categories_data = []
        unassigned_count = 0
        
        for category in categories:
            category_data = {
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'parent_id': category.parent.id,
                'parent_name': category.parent.name,
                'parent_label': category.parent.get_display_name(),
                'has_gender_assignment': category.gender is not None,
            }
            
            if category.gender:
                category_data['gender'] = {
                    'id': category.gender.id,
                    'name': category.gender.name,
                    'display_name': category.gender.display_name
                }
            else:
                category_data['gender'] = None
                unassigned_count += 1
            
            if include_products:
                category_data['product_count'] = category.get_product_count()
            
            categories_data.append(category_data)
        
        # Get statistics about child categories
        total_child_categories = Category.objects.filter(parent__isnull=False, is_visible=True).count()
        assigned_child_categories = Category.objects.filter(gender__isnull=False, parent__isnull=False, is_visible=True).count()
        
        return Response({
            'success': True,
            'gender': {
                'id': gender.id,
                'name': gender.name,
                'display_name': gender.display_name
            },
            'categories': categories_data,
            'total_count': len(categories_data),
            'statistics': {
                'total_child_categories': total_child_categories,
                'assigned_child_categories': assigned_child_categories,
                'unassigned_child_categories': total_child_categories - assigned_child_categories,
                'unassigned_in_results': unassigned_count
            },
            'message': f"Found {len(categories_data)} child categories for gender '{gender.display_name}'"
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_child_categories_by_parent_and_gender(request, parent_id):
    """
    Get child categories of a specific parent filtered by gender
    URL: /api/categories/parent/{parent_id}/children/by-gender/
    
    Parameters:
        - parent_id: ID of the parent category
        - gender_id: ID of the gender from CategoryGender table
        - gender_name: Name of the gender (men, women, unisex, general)
        - include_products: Whether to include product counts (default: true)
        - include_unassigned: Whether to include categories without gender assignment (default: false)
        - include_neutral: Whether to include neutral categories (general/unisex) (default: false)
    
    Returns:
    - Child categories of the specified parent that have the specified gender assigned
    - Plus neutral categories when include_neutral=true
    """
    try:
        gender_id = request.GET.get('gender_id')
        gender_name = request.GET.get('gender_name')
        include_products = request.GET.get('include_products', 'true').lower() == 'true'
        include_unassigned = request.GET.get('include_unassigned', 'false').lower() == 'true'
        include_neutral = request.GET.get('include_neutral', 'false').lower() == 'true'
        
        # Get the parent category
        parent_category = Category.objects.filter(id=parent_id, is_visible=True).first()
        if not parent_category:
            return Response({
                'success': False,
                'error': 'Parent category not found'
            }, status=404)
        
        # Get the gender object
        gender = None
        if gender_id:
            gender = CategoryGender.objects.filter(id=gender_id, is_active=True).first()
        elif gender_name:
            gender = CategoryGender.objects.filter(name=gender_name, is_active=True).first()
        else:
            return Response({
                'success': False,
                'error': 'Either gender_id or gender_name parameter is required'
            }, status=400)
        
        if not gender:
            return Response({
                'success': False,
                'error': 'Gender not found'
            }, status=404)
        
        # Build the query based on parameters
        if include_neutral:
            # Include categories with:
            # 1. The specified gender
            # 2. Neutral gender (general/unisex)
            # 3. No gender assigned (when include_unassigned=True)
            neutral_genders = CategoryGender.objects.filter(
                models.Q(name='general') | models.Q(name='unisex'),
                is_active=True
            )
            
            if include_unassigned:
                categories = Category.objects.filter(
                    models.Q(gender=gender) |
                    models.Q(gender__in=neutral_genders) |
                    models.Q(gender__isnull=True),
                    parent=parent_category,
                    is_visible=True
                ).prefetch_related('product_set')
            else:
                categories = Category.objects.filter(
                    models.Q(gender=gender) |
                    models.Q(gender__in=neutral_genders),
                    parent=parent_category,
                    is_visible=True
                ).prefetch_related('product_set')
        elif include_unassigned:
            # Include child categories with this gender OR no gender assigned
            categories = Category.objects.filter(
                models.Q(gender=gender) | models.Q(gender__isnull=True),
                parent=parent_category,
                is_visible=True
            ).prefetch_related('product_set')
        else:
            # Only child categories with this specific gender
            categories = Category.objects.filter(
                gender=gender,
                parent=parent_category,
                is_visible=True
            ).prefetch_related('product_set')
        
        categories_data = []
        unassigned_count = 0
        
        for category in categories:
            category_data = {
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'parent_id': parent_category.id,
                'parent_name': parent_category.name,
                'parent_label': parent_category.get_display_name(),
                'has_gender_assignment': category.gender is not None,
            }
            
            if category.gender:
                category_data['gender'] = {
                    'id': category.gender.id,
                    'name': category.gender.name,
                    'display_name': category.gender.display_name
                }
            else:
                category_data['gender'] = None
                unassigned_count += 1
            
            if include_products:
                category_data['product_count'] = category.get_product_count()
            
            categories_data.append(category_data)
        
        # Get statistics about this parent's child categories
        total_child_categories = Category.objects.filter(parent=parent_category, is_visible=True).count()
        assigned_child_categories = Category.objects.filter(gender__isnull=False, parent=parent_category, is_visible=True).count()
        
        # Count neutral categories if include_neutral is enabled
        neutral_count = 0
        if include_neutral:
            neutral_genders = CategoryGender.objects.filter(
                models.Q(name='general') | models.Q(name='unisex'),
                is_active=True
            )
            neutral_count = Category.objects.filter(
                gender__in=neutral_genders,
                parent=parent_category,
                is_visible=True
            ).count()
        
        return Response({
            'success': True,
            'parent_category': {
                'id': parent_category.id,
                'name': parent_category.name,
                'label': parent_category.get_display_name(),
            },
            'gender': {
                'id': gender.id,
                'name': gender.name,
                'display_name': gender.display_name
            },
            'categories': categories_data,
            'total_count': len(categories_data),
            'statistics': {
                'total_child_categories': total_child_categories,
                'assigned_child_categories': assigned_child_categories,
                'unassigned_child_categories': total_child_categories - assigned_child_categories,
                'unassigned_in_results': unassigned_count,
                'neutral_categories_included': neutral_count if include_neutral else 0
            },
            'message': f"Found {len(categories_data)} child categories of '{parent_category.name}' for gender '{gender.display_name}'" + 
                      (f" (including {neutral_count} neutral categories)" if include_neutral else "")
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_flattened_categories_by_gender(request, parent_id):
    """
    Get all gender-specific categories under a parent, including nested ones
    URL: /api/categories/parent/{parent_id}/flattened-by-gender/
    
    Parameters:
        - parent_id: ID of the parent category
        - gender_id: ID of the gender from CategoryGender table
        - gender_name: Name of the gender (men, women, unisex, general)
        - include_products: Whether to include product counts (default: true)
    
    Returns:
    - Direct children with the specified gender
    - Plus gender-specific subcategories of neutral children
    - All in a flat list for easy navigation
    """
    try:
        gender_id = request.GET.get('gender_id')
        gender_name = request.GET.get('gender_name')
        include_products = request.GET.get('include_products', 'true').lower() == 'true'
        
        # Get the parent category
        parent_category = Category.objects.filter(id=parent_id, is_visible=True).first()
        if not parent_category:
            return Response({
                'success': False,
                'error': 'Parent category not found'
            }, status=404)
        
        # Get the gender object
        gender = None
        if gender_id:
            gender = CategoryGender.objects.filter(id=gender_id, is_active=True).first()
        elif gender_name:
            gender = CategoryGender.objects.filter(name=gender_name, is_active=True).first()
        else:
            return Response({
                'success': False,
                'error': 'Either gender_id or gender_name parameter is required'
            }, status=400)
        
        if not gender:
            return Response({
                'success': False,
                'error': 'Gender not found'
            }, status=404)
        
        # Get direct children with this gender
        direct_children = Category.objects.filter(
            gender=gender,
            parent=parent_category,
            is_visible=True
        ).prefetch_related('product_set')
        
        # Get neutral children (general/unisex) and unassigned children, plus their gender-specific subcategories
        neutral_genders = CategoryGender.objects.filter(
            models.Q(name='general') | models.Q(name='unisex'),
            is_active=True
        )
        
        neutral_children = Category.objects.filter(
            models.Q(gender__in=neutral_genders) | models.Q(gender__isnull=True),
            parent=parent_category,
            is_visible=True
        ).prefetch_related('product_set')
        
        # Get gender-specific subcategories of neutral children
        nested_gender_categories = []
        for neutral_child in neutral_children:
            gender_specific = Category.objects.filter(
                gender=gender,
                parent=neutral_child,
                is_visible=True
            ).prefetch_related('product_set')
            nested_gender_categories.extend(gender_specific)
        
        # Combine both lists
        all_categories = list(direct_children) + nested_gender_categories
        
        # Prepare response data
        categories_data = []
        direct_count = 0
        nested_count = 0
        
        for category in all_categories:
            category_data = {
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'parent_id': category.parent.id,
                'parent_name': category.parent.name,
                'parent_label': category.parent.get_display_name(),
                'has_gender_assignment': category.gender is not None,
                'category_type': 'direct_child' if category.parent == parent_category else 'nested_gender_specific'
            }
            
            if category.parent != parent_category:
                # This is a nested category, include info about its neutral parent
                category_data['neutral_parent'] = {
                    'id': category.parent.id,
                    'name': category.parent.name,
                    'label': category.parent.get_display_name()
                }
                nested_count += 1
            else:
                direct_count += 1
            
            if category.gender:
                category_data['gender'] = {
                    'id': category.gender.id,
                    'name': category.gender.name,
                    'display_name': category.gender.display_name
                }
            
            if include_products:
                category_data['product_count'] = category.get_product_count()
            
            categories_data.append(category_data)
        
        # Get statistics
        total_direct_children = Category.objects.filter(parent=parent_category, is_visible=True).count()
        total_neutral_children = neutral_children.count()
        total_unassigned_children = Category.objects.filter(
            gender__isnull=True,
            parent=parent_category,
            is_visible=True
        ).count()
        
        return Response({
            'success': True,
            'parent_category': {
                'id': parent_category.id,
                'name': parent_category.name,
                'label': parent_category.get_display_name(),
            },
            'gender': {
                'id': gender.id,
                'name': gender.name,
                'display_name': gender.display_name
            },
            'categories': categories_data,
            'total_count': len(categories_data),
            'statistics': {
                'direct_children_count': direct_count,
                'nested_categories_count': nested_count,
                'total_direct_children': total_direct_children,
                'total_neutral_children': total_neutral_children,
                'total_unassigned_children': total_unassigned_children
            },
            'message': f"Found {len(categories_data)} categories for '{parent_category.name}' in gender '{gender.display_name}' " +
                      f"({direct_count} direct, {nested_count} nested from neutral/unassigned categories)"
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_products_by_gender_table(request):
    """
    Get products filtered by gender using the CategoryGender table
    URL: /api/products/by-gender-table/
    
    Parameters:
        - gender_id: ID of the gender from CategoryGender table
        - gender_name: Name of the gender (men, women, unisex, general)
        - category_id: Optional category ID to filter within
        - page: Page number for pagination
        - limit: Items per page (default: 20)
        - search: Search query
    
    Returns:
    - Products from categories that have the specified gender assigned
    """
    try:
        gender_id = request.GET.get('gender_id')
        gender_name = request.GET.get('gender_name')
        category_id = request.GET.get('category_id')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        search_query = request.GET.get('search', '')
        
        # Get the gender object
        gender = None
        if gender_id:
            gender = CategoryGender.objects.filter(id=gender_id, is_active=True).first()
        elif gender_name:
            gender = CategoryGender.objects.filter(name=gender_name, is_active=True).first()
        else:
            return Response({
                'success': False,
                'error': 'Either gender_id or gender_name parameter is required'
            }, status=400)
        
        if not gender:
            return Response({
                'success': False,
                'error': 'Gender not found'
            }, status=404)
        
        # Get categories with this gender
        categories_with_gender = Category.objects.filter(gender=gender, is_visible=True)
        
        # If category_id is specified, filter within that category's subcategories
        if category_id:
            try:
                parent_category = Category.objects.get(id=category_id)
                # Get all subcategories of the parent that have the specified gender
                categories_with_gender = categories_with_gender.filter(
                    models.Q(parent=parent_category) | models.Q(id=parent_category.id)
                )
            except Category.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Category not found'
                }, status=404)
        
        # Get products from these categories
        products = Product.objects.filter(
            category__in=categories_with_gender,
            is_active=True
        ).select_related('category', 'supplier').prefetch_related('images')
        
        # Apply search filter
        if search_query:
            products = products.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(model__icontains=search_query)
            )
        
        # Order by creation date (newest first)
        products = products.order_by('-created_at')
        
        # Pagination
        paginator = Paginator(products, limit)
        try:
            products_page = paginator.page(page)
        except:
            return Response({
                'success': False,
                'error': 'Invalid page number'
            }, status=400)
        
        # Serialize products
        products_data = []
        for product in products_page:
            product_data = {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price_toman': float(product.price_toman) if product.price_toman else None,
                'price_usd': float(product.price_usd) if product.price_usd else None,
                'category_id': product.category.id,
                'category_name': product.category.name,
                'category_gender': {
                    'id': product.category.gender.id,
                    'name': product.category.gender.name,
                    'display_name': product.category.gender.display_name
                } if product.category.gender else None,
                'is_active': product.is_active,
                'is_new_arrival': product.is_new_arrival,
                'created_at': get_unix_timestamp(product.created_at),
                'images': [get_product_image_url(product, request)],
                'attributes': get_product_attributes(product)
            }
            products_data.append(product_data)
        
        return Response({
            'success': True,
            'gender': {
                'id': gender.id,
                'name': gender.name,
                'display_name': gender.display_name
            },
            'products': products_data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': products_page.has_next(),
                'has_previous': products_page.has_previous()
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_gender_category_tree(request):
    """
    Get a hierarchical tree of categories organized by gender
    URL: /api/gender-category-tree/
    
    Returns:
    - Tree structure with genders as top level, then categories under each gender
    """
    try:
        # Get all active genders
        genders = CategoryGender.objects.filter(is_active=True).order_by('display_order', 'name')
        
        tree_data = []
        for gender in genders:
            # Get categories with this gender
            categories = Category.objects.filter(
                gender=gender,
                is_visible=True
            ).prefetch_related('product_set', 'subcategories')
            
            gender_data = {
                'gender': {
                    'id': gender.id,
                    'name': gender.name,
                    'display_name': gender.display_name
                },
                'categories': []
            }
            
            for category in categories:
                category_data = {
                    'id': category.id,
                    'name': category.name,
                    'label': category.get_display_name(),
                    'parent_id': category.parent.id if category.parent else None,
                    'product_count': category.get_product_count(),
                    'subcategories': []
                }
                
                # Get subcategories recursively
                def get_subcategories_recursive(parent_category):
                    subcategories = []
                    for subcategory in parent_category.subcategories.filter(is_visible=True):
                        subcategory_data = {
                            'id': subcategory.id,
                            'name': subcategory.name,
                            'label': subcategory.get_display_name(),
                            'parent_id': parent_category.id,
                            'product_count': subcategory.get_product_count(),
                            'subcategories': get_subcategories_recursive(subcategory)
                        }
                        subcategories.append(subcategory_data)
                    return subcategories
                
                category_data['subcategories'] = get_subcategories_recursive(category)
                gender_data['categories'].append(category_data)
            
            tree_data.append(gender_data)
        
        return Response({
            'success': True,
            'gender_category_tree': tree_data,
            'total_genders': len(tree_data)
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_gender_statistics(request):
    """
    Get statistics about gender assignments for categories
    URL: /api/gender-statistics/
    
    Returns:
    - Statistics about gender assignments
    - List of categories without gender assignments
    """
    try:
        # Get all active genders
        genders = CategoryGender.objects.filter(is_active=True)
        
        # Get statistics
        total_categories = Category.objects.filter(is_visible=True).count()
        assigned_categories = Category.objects.filter(gender__isnull=False, is_visible=True).count()
        unassigned_categories = total_categories - assigned_categories
        
        # Get breakdown by gender
        gender_breakdown = {}
        for gender in genders:
            count = Category.objects.filter(gender=gender, is_visible=True).count()
            gender_breakdown[gender.name] = {
                'id': gender.id,
                'display_name': gender.display_name,
                'count': count
            }
        
        # Get categories without gender assignment
        unassigned_categories_list = []
        if request.GET.get('include_unassigned_list', 'false').lower() == 'true':
            unassigned = Category.objects.filter(gender__isnull=True, is_visible=True)
            for category in unassigned:
                unassigned_categories_list.append({
                    'id': category.id,
                    'name': category.name,
                    'label': category.get_display_name(),
                    'parent_id': category.parent.id if category.parent else None,
                    'parent_name': category.parent.name if category.parent else None,
                })
        
        return Response({
            'success': True,
            'statistics': {
                'total_categories': total_categories,
                'assigned_categories': assigned_categories,
                'unassigned_categories': unassigned_categories,
                'assignment_rate': round((assigned_categories / total_categories * 100), 2) if total_categories > 0 else 0
            },
            'gender_breakdown': gender_breakdown,
            'unassigned_categories_list': unassigned_categories_list,
            'message': f"Gender assignment rate: {round((assigned_categories / total_categories * 100), 2) if total_categories > 0 else 0}%"
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_category_attribute_values_with_products(request, category_id, attribute_key):
    """
    Get attribute values and their associated products for a specific category and attribute key
    URL: /api/category/{category_id}/attribute/{attribute_key}/values-with-products/
    
    Parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20, max: 100)
    - value: Filter by specific attribute value (optional)
    
    Example: /api/category/1027/attribute/برند/values-with-products/?page=1&per_page=10
    Example: /api/category/1027/attribute/برند/values-with-products/?value=Rolex&page=1&per_page=5
    
    Returns:
    {
        "category": {"id": 1027, "name": "ساعت مردانه"},
        "attribute_key": "برند",
        "values_with_products": [...],
        "pagination": {
            "current_page": 1,
            "total_pages": 5,
            "total_items": 100,
            "has_next": true,
            "has_previous": false
        }
    }
    """
    try:
        category = Category.objects.get(id=category_id)
        
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 100)  # Max 100 per page
        filter_value = request.GET.get('value', None)
        
        # Prefer predefined CategoryAttribute values if present
        category_attribute = category.category_attributes.filter(key=attribute_key).first()
        if category_attribute:
            predefined_values = list(
                category_attribute.values.order_by('display_order', 'value').values_list('value', flat=True)
            )
            predefined_values = [v for v in predefined_values if v and v.strip()]
            # Values are already sorted by display_order from the query
            sorted_values = predefined_values
            total_values = len(sorted_values)
            total_pages = (total_values + per_page - 1) // per_page
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            paginated_values = sorted_values[start_index:end_index]
            return Response({
                'category': {
                    'id': category.id,
                    'name': category.name
                },
                'attribute_key': attribute_key,
                'values': paginated_values,
                'pagination': {
                    'current_page': page,
                    'total_pages': total_pages,
                    'total_items': total_values,
                    'has_next': page < total_pages,
                    'has_previous': page > 1
                }
            })

        # Else: Get all products in this category
        products = Product.objects.filter(category=category, is_active=True)
        
        # Get all unique values for this attribute key
        values_data = []
        
        # Check both legacy and new attribute systems
        legacy_values = set(products.filter(
            legacy_attribute_set__key=attribute_key
        ).values_list('legacy_attribute_set__value', flat=True).distinct())
        
        new_values = set(products.filter(
            attribute_values__attribute__key=attribute_key
        ).values_list('attribute_values__attribute_value__value', flat=True).distinct())
        
        custom_values = set(products.filter(
            attribute_values__attribute__key=attribute_key
        ).values_list('attribute_values__custom_value', flat=True).distinct())
        
        # Combine all unique values
        all_values = legacy_values | new_values | custom_values
        all_values = {v for v in all_values if v and v.strip()}  # Remove empty values
        
        # Fallback: if there are no product-derived values, use predefined
        # CategoryAttribute values configured for this category/key
        if not all_values:
            try:
                category_attribute = category.category_attributes.get(key=attribute_key)
                predefined_values = set(
                    category_attribute.values.values_list('value', flat=True)
                )
                all_values = {v for v in predefined_values if v and v.strip()}
            except Exception:
                # If the category attribute does not exist or has no values,
                # keep the list empty
                pass
        
        # Filter by specific value if requested
        if filter_value:
            all_values = {v for v in all_values if v.lower() == filter_value.lower()}
        
        # Sort values
        sorted_values = sorted(all_values)
        
        # Calculate pagination for values
        total_values = len(sorted_values)
        total_pages = (total_values + per_page - 1) // per_page
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_values = sorted_values[start_index:end_index]
        
        # For each paginated value, get the products
        for value in paginated_values:
            # Get products with this attribute value
            matching_products_legacy = products.filter(
                legacy_attribute_set__key=attribute_key,
                legacy_attribute_set__value__iexact=value
            )
            
            matching_products_new = products.filter(
                attribute_values__attribute__key=attribute_key,
                attribute_values__attribute_value__value__iexact=value
            )
            
            matching_products_custom = products.filter(
                attribute_values__attribute__key=attribute_key,
                attribute_values__custom_value__iexact=value
            )
            
            # Combine all matching products
            all_matching_products = set(matching_products_legacy) | set(matching_products_new) | set(matching_products_custom)
            
            # Serialize products
            products_data = []
            for product in all_matching_products:
                # Get product image
                image_url = None
                if product.images.exists():
                    image_url = product.images.first().image.url
                
                # Get product attributes
                attributes = {}
                
                # Legacy attributes
                for attr in product.legacy_attribute_set.all():
                    attributes[attr.key] = attr.value
                
                # New attributes
                for attr_value in product.attribute_values.all():
                    if attr_value.attribute_value:
                        attributes[attr_value.attribute.key] = attr_value.attribute_value.value
                    elif attr_value.custom_value:
                        attributes[attr_value.attribute.key] = attr_value.custom_value
                
                product_data = {
                    'id': product.id,
                    'name': product.name,
                    'price_toman': float(product.price_toman),
                    'price_usd': float(product.price_usd) if product.price_usd else None,
                    'description': product.description,
                    'sku': product.sku,
                    'model': product.model,
                    'image_url': image_url,
                    'attributes': attributes,
                    'created_at': product.created_at.isoformat()
                }
                products_data.append(product_data)
            
            value_data = {
                'value': value,
                'product_count': len(products_data),
                'products': products_data
            }
            values_data.append(value_data)
        
        return Response({
            'category': {
                'id': category.id,
                'name': category.name
            },
            'attribute_key': attribute_key,
            'values_with_products': values_data,
            'total_values': total_values,
            'total_products': sum(v['product_count'] for v in values_data),
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_items': total_values,
                'has_next': page < total_pages,
                'has_previous': page > 1
            },
            'filters_applied': {
                'value': filter_value
            } if filter_value else {}
        })
        
    except Category.DoesNotExist:
        return Response({
            'error': 'Category not found'
        }, status=404)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def api_category_attribute_values(request, category_id, attribute_key):
    """
    Get just the attribute values for a specific category and attribute key
    URL: /api/category/{category_id}/attribute/{attribute_key}/values/
    
    Parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 50, max: 200)
    
    Example: /api/category/1027/attribute/برند/values/
    Example: /api/category/1027/attribute/نوع%20حرکت/values/?page=1&per_page=20
    
    Returns:
    {
        "category": {"id": 1027, "name": "ساعت مردانه"},
        "attribute_key": "برند",
        "values": ["Rolex", "Omega", "Cartier", ...],
        "pagination": {
            "current_page": 1,
            "total_pages": 1,
            "total_items": 10,
            "has_next": false,
            "has_previous": false
        }
    }
    """

@api_view(['GET'])
@permission_classes([AllowAny])
def api_category_dynamic_attribute_values(request, category_id):
    """
    Get attribute values using the category's dynamic categorization attribute key
    URL: /api/category/{category_id}/dynamic-attribute-values/
    
    Parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 50, max: 200)
    
    Example: /api/category/1027/dynamic-attribute-values/
    Example: /api/category/1027/dynamic-attribute-values/?page=1&per_page=20
    """
    try:
        from django.db.models import Q
        from shop.models import (
            Category, CategoryAttribute, AttributeValue
        )

        # Get the category
        category = Category.objects.get(id=category_id)
        
        # Try to get the categorization attribute key
        attribute_key = category.get_categorization_attribute_key()
        
        # Find the corresponding CategoryAttribute
        category_attrs = CategoryAttribute.objects.filter(
            category=category
        )
        
        # If no attributes exist, return default response
        if not category_attrs.exists():
            return Response({
                'category': {
                    'id': category.id,
                    'name': category.name
                },
                'error': 'No attributes defined for this category',
                'available_attributes': [],
                'values': ['همه'],
                'pagination': {
                    'current_page': 1,
                    'total_pages': 1,
                    'total_items': 1,
                    'has_next': False,
                    'has_previous': False
                }
            })
        
        # If no specific categorization key is set, use the first attribute
        if not attribute_key:
            attribute_key = category_attrs.first().key
        
        # Find the specific attribute
        try:
            category_attr = category_attrs.get(key=attribute_key)
        except CategoryAttribute.DoesNotExist:
            # Fallback to the first attribute if the specified key doesn't exist
            category_attr = category_attrs.first()
        
        # Get attribute values with proper ordering
        attribute_values = AttributeValue.objects.filter(
            attribute=category_attr
        ).order_by('display_order', 'value').values_list('value', flat=True)
        
        # Remove empty values and convert to list to preserve order
        attribute_values = [v for v in attribute_values if v and v.strip()]
        
        # Values are already sorted by display_order from the query
        sorted_values = attribute_values
        
        # Add "همه" as the first value
        sorted_values = ['همه'] + sorted_values
        
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 50)), 200)  # Max 200 per page
        
        # Calculate pagination
        total_values = len(sorted_values)
        total_pages = (total_values + per_page - 1) // per_page
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_values = sorted_values[start_index:end_index]
        
        return Response({
            'category': {
                'id': category.id,
                'name': category.name
            },
            'attribute_key': category_attr.key,
            'values': paginated_values,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_items': total_values,
                'has_next': page < total_pages,
                'has_previous': page > 1
            }
        })
        
    except Category.DoesNotExist:
        return Response({
            'error': 'Category not found'
        }, status=404)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=500)


# Simple admin-lite API to get/set categorization key without navigating forms
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])  # adjust to IsAdminUser if needed
def api_category_categorization_key(request, category_id):
    """
    GET: returns current key and available keys
    POST: set categorization key: {"key": "برند"} or {"key": null/""} to clear
    """
    try:
        category = Category.objects.get(id=category_id)
        if request.method == 'GET':
            return Response({
                'category': {'id': category.id, 'name': category.name},
                'current_key': category.categorization_attribute_key,
                'effective_key': category.get_categorization_attribute_key(),
                'available_keys': category.get_available_attribute_keys()
            })
        # POST
        data = request.data or {}
        new_key = data.get('key')
        if not new_key:
            category.categorization_attribute_key = None
            category.save(update_fields=['categorization_attribute_key'])
            return Response({'status': 'cleared', 'effective_key': category.get_categorization_attribute_key()})
        # Validate key
        if not category.category_attributes.filter(key=new_key).exists():
            return Response({'error': 'Invalid key for this category'}, status=400)
        category.categorization_attribute_key = new_key
        category.save(update_fields=['categorization_attribute_key'])
        return Response({'status': 'updated', 'current_key': new_key})
    except Category.DoesNotExist:
        return Response({'error': 'Category not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def api_leaf_categories(request):
    """
    API endpoint to retrieve the deepest categories without child categories, 
    optionally filtered by gender.
    
    URL: /api/categories/leaf/
    
    Query Parameters:
    - gender: Optional. Filter categories by gender (e.g., 'men', 'women')
    """
    try:
        # Get gender filter from query params
        gender_name = request.GET.get('gender', 'men')
        
        # Find the gender object
        try:
            gender_obj = CategoryGender.objects.get(name=gender_name)
        except CategoryGender.DoesNotExist:
            return Response({
                'success': False,
                'error': f'Gender "{gender_name}" not found'
            }, status=400)
        
        # Find categories that have no subcategories
        # This will include both top-level and nested categories
        leaf_categories = Category.objects.filter(
            is_visible=True,
            gender=gender_obj,
            subcategories__isnull=True  # No subcategories
        )
        
        # Prepare categories data
        categories_data = []
        for category in leaf_categories:
            # Ensure this is truly a leaf category (no subcategories at any level)
            if not category.subcategories.exists():
                categories_data.append({
                    'id': category.id,
                    'name': category.name,
                    'label': category.get_display_name(),
                    'parent_id': category.parent.id if category.parent else None,
                    'has_gender_assignment': category.gender is not None,
                    'subcategory_count': 0,  # No subcategories
                    'category_type': category.category_type,
                    'gender': {
                        'id': gender_obj.id,
                        'name': gender_obj.name,
                        'display_name': gender_obj.display_name
                    },
                    'product_count': category.get_product_count()
                })
        
        # Compute statistics
        total_parent_categories = Category.objects.filter(parent=None, is_visible=True).count()
        assigned_parent_categories = Category.objects.filter(parent=None, is_visible=True, gender__isnull=False).count()
        
        return Response({
            'success': True,
            'gender': {
                'id': gender_obj.id,
                'name': gender_obj.name,
                'display_name': gender_obj.display_name
            },
            'categories': categories_data,
            'total_count': len(categories_data),
            'statistics': {
                'total_parent_categories': total_parent_categories,
                'assigned_parent_categories': assigned_parent_categories,
                'unassigned_parent_categories': total_parent_categories - assigned_parent_categories,
                'unassigned_in_results': 0  # Always 0 in this implementation
            },
            'message': f"Found {len(categories_data)} leaf categories for gender '{gender_obj.display_name}'"
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
def api_special_offer_categories(request, offer_id):
    """
    Get all leaf categories that have products in a specific special offer
    URL: /api/special-offers/<offer_id>/categories/
    
    Query Parameters:
    - gender: Filter categories by gender ('men', 'women', 'unisex', 'general')
    
    Returns only the child categories (leaf nodes) that contain products in this offer
    """
    try:
        # Get the special offer
        offer = SpecialOffer.objects.get(id=offer_id, enabled=True, is_active=True)
        
        # Get gender filter
        gender_filter = request.GET.get('gender')
        
        # Build filter criteria
        filter_kwargs = {
            'offer': offer, 
            'is_active': True
        }
        
        # Add gender filter if provided
        if gender_filter:
            valid_genders = ['men', 'women', 'unisex', 'general']
            if gender_filter not in valid_genders:
                return Response({
                    'success': False,
                    'error': f'Invalid gender. Must be one of: {", ".join(valid_genders)}'
                }, status=400)
            filter_kwargs['product__category__gender__name'] = gender_filter
        
        # Get all products in this offer (filtered by gender if specified)
        offer_products = SpecialOfferProduct.objects.filter(
            **filter_kwargs
        ).select_related('product', 'product__category', 'product__category__gender')
        
        if not offer_products.exists():
            return Response({
                'success': True,
                'offer': {
                    'id': offer.id,
                    'title': offer.title,
                    'offer_type': offer.offer_type
                },
                'categories': [],
                'total_categories': 0,
                'message': 'No products found in this offer'
            })
        
        # Extract unique categories from offer products
        categories_dict = {}
        
        for offer_product in offer_products:
            category = offer_product.product.category
            if category and category.is_visible:
                # Only include if it's a leaf category (no subcategories)
                if not category.subcategories.exists():
                    if category.id not in categories_dict:
                        categories_dict[category.id] = {
                            'category': category,
                            'products': [],
                            'max_discount': 0
                        }
                    
                    categories_dict[category.id]['products'].append(offer_product)
                    categories_dict[category.id]['max_discount'] = max(
                        categories_dict[category.id]['max_discount'],
                        offer_product.discount_percentage
                    )
        
        # Format response
        categories_data = []
        for cat_data in categories_dict.values():
            category = cat_data['category']
            categories_data.append({
                'id': category.id,
                'name': category.name,
                'label': category.get_display_name(),
                'parent_id': category.parent.id if category.parent else None,
                'gender': category.gender.name if category.gender else None,
                'product_count': len(cat_data['products']),
                'max_discount': cat_data['max_discount'],
                'has_discount': cat_data['max_discount'] > 0
            })
        
        # Sort by max discount (highest first), then by product count
        categories_data.sort(key=lambda x: (-x['max_discount'], -x['product_count']))
        
        return Response({
            'success': True,
            'offer': {
                'id': offer.id,
                'title': offer.title,
                'offer_type': offer.offer_type,
                'description': offer.description
            },
            'categories': categories_data,
            'total_categories': len(categories_data),
            'total_products': len(offer_products)
        })
        
    except SpecialOffer.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Special offer not found'
        }, status=404)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


class SpecialOffersAPIView(APIView):
    """API endpoint for retrieving active special offers"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get all currently active special offers"""
        try:
            # Get pagination parameters
            try:
                page = int(request.GET.get('page', 1))
                per_page = int(request.GET.get('per_page', 20))
                
                # Validate pagination parameters
                if page < 1:
                    page = 1
                if per_page < 1 or per_page > 100:  # Limit per_page to prevent abuse
                    per_page = 20
            except ValueError:
                page = 1
                per_page = 20
            
            # Get all enabled and currently valid offers
            offers = SpecialOffer.objects.filter(
                enabled=True,
                is_active=True
            ).prefetch_related('products__product__images', 'products__product__category')
            
            # Filter offers that are currently valid
            valid_offers = []
            for offer in offers:
                if offer.is_currently_valid():
                    # Increment view count for analytics
                    offer.increment_views()
                    valid_offers.append(offer)
            
            # Apply pagination
            total_count = len(valid_offers)
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            paginated_offers = valid_offers[start_index:end_index]
            
            # Serialize the offers
            serializer = SpecialOfferSerializer(
                paginated_offers, 
                many=True, 
                context={'request': request}
            )
            
            # Calculate pagination info
            total_pages = (total_count + per_page - 1) // per_page
            has_next = page < total_pages
            has_previous = page > 1
            
            # Analytics logging
            print(f"Special offers API called - {len(valid_offers)} active offers found, page {page}/{total_pages}")
            
            return Response({
                'success': True,
                'offers': serializer.data,
                'total_offers': total_count,
                'timestamp': timezone.now().timestamp(),
                'pagination': {
                    'current_page': page,
                    'per_page': per_page,
                    'total_pages': total_pages,
                    'has_next': has_next,
                    'has_previous': has_previous,
                    'next_page': page + 1 if has_next else None,
                    'previous_page': page - 1 if has_previous else None
                }
            })
            
        except Exception as e:
            print(f"Error in special offers API: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve special offers',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SpecialOfferDetailAPIView(APIView):
    """API endpoint for retrieving a specific special offer"""
    permission_classes = [AllowAny]
    
    def get(self, request, offer_id):
        """Get details of a specific special offer"""
        try:
            offer = SpecialOffer.objects.get(
                id=offer_id,
                enabled=True,
                is_active=True
            )
            
            # Check if offer is currently valid
            if not offer.is_currently_valid():
                return Response({
                    'success': False,
                    'error': 'Offer is not currently active'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Increment view count for analytics
            offer.increment_views()
            
            # Check if category or gender filtering is requested
            category_id = request.GET.get('category_id')
            gender_filter = request.GET.get('gender')  # 'men', 'women', 'unisex', 'general'
            
            # Get pagination parameters
            try:
                page = int(request.GET.get('page', 1))
                per_page = int(request.GET.get('per_page', 20))
                
                # Validate pagination parameters
                if page < 1:
                    page = 1
                if per_page < 1 or per_page > 100:  # Limit per_page to prevent abuse
                    per_page = 20
            except ValueError:
                page = 1
                per_page = 20
            # Collect attribute and price filters similar to CategoryProductFilterView
            # Handle both DRF request.query_params and Django request.GET
            query_params = getattr(request, 'query_params', request.GET)

            # Build valid attribute keys scope
            valid_attribute_keys = set()
            try:
                if category_id:
                    # If category provided, use its attribute keys
                    cat_obj = Category.objects.get(id=int(category_id))
                    valid_attribute_keys = set(cat_obj.category_attributes.values_list('key', flat=True))
                else:
                    # Otherwise, derive from products in this offer
                    base_keys_legacy = SpecialOfferProduct.objects.filter(
                        offer=offer,
                        is_active=True,
                        product__is_active=True
                    ).values_list('product__legacy_attribute_set__key', flat=True).distinct()
                    base_keys_new = SpecialOfferProduct.objects.filter(
                        offer=offer,
                        is_active=True,
                        product__is_active=True
                    ).values_list('product__attribute_values__attribute__key', flat=True).distinct()
                    valid_attribute_keys = {k for k in set(list(base_keys_legacy) + list(base_keys_new)) if k}
                    
                    # Also include category attributes from all categories that contain products in this offer
                    categories_in_offer = SpecialOfferProduct.objects.filter(
                        offer=offer,
                        is_active=True,
                        product__is_active=True
                    ).values_list('product__category_id', flat=True).distinct()
                    
                    for cat_id in categories_in_offer:
                        try:
                            cat_attrs = Category.objects.get(id=cat_id).category_attributes.values_list('key', flat=True)
                            valid_attribute_keys.update(cat_attrs)
                        except Category.DoesNotExist:
                            continue
            except Exception:
                valid_attribute_keys = set()

            multi_value_filters = {}
            price_filters = {}
            for key in query_params.keys():
                if key in valid_attribute_keys:
                    values = query_params.getlist(key)
                    values = [v for v in values if isinstance(v, str) and v.strip()]
                    if values:
                        multi_value_filters[key] = values
                elif key in ['price__gte', 'price__lte', 'price_toman__gte', 'price_toman__lte', 'price_usd__gte', 'price_usd__lte']:
                    value = query_params.get(key)
                    if value and str(value).strip():
                        price_filters[key] = value

            if category_id or gender_filter or multi_value_filters or price_filters:
                # Build filter criteria
                try:
                    filter_kwargs = {
                        'offer': offer,
                        'is_active': True,
                        'product__is_active': True
                    }
                    
                    # Add category filter if provided
                    if category_id:
                        category_id = int(category_id)
                        filter_kwargs['product__category_id'] = category_id
                    
                    # Add gender filter if provided
                    if gender_filter:
                        # Validate gender filter
                        valid_genders = ['men', 'women', 'unisex', 'general']
                        if gender_filter not in valid_genders:
                            return Response({
                                'success': False,
                                'error': f'Invalid gender. Must be one of: {", ".join(valid_genders)}'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        filter_kwargs['product__category__gender__name'] = gender_filter
                    
                    # Apply price filters (on product fields)
                    for price_key, price_value in price_filters.items():
                        try:
                            # validate numeric
                            _ = float(price_value)
                            filter_kwargs[f'product__{price_key}'] = price_value
                        except (ValueError, TypeError):
                            continue

                    # Start with base queryset after simple filters
                    base_qs = SpecialOfferProduct.objects.filter(
                        **filter_kwargs
                    ).select_related('product', 'product__category', 'product__category__gender')

                    # Apply attribute filters
                    if multi_value_filters:
                        from django.db.models import Q
                        # Compute matching product ids per attribute and intersect
                        matching_product_ids = None
                        for attr_key, values in multi_value_filters.items():
                            if len(values) == 1:
                                single_val = values[0]
                                ids_legacy = Product.objects.filter(
                                    legacy_attribute_set__key=attr_key,
                                    legacy_attribute_set__value__iexact=single_val
                                ).values_list('id', flat=True)
                                ids_new = Product.objects.filter(
                                    attribute_values__attribute__key=attr_key,
                                    attribute_values__attribute_value__value__iexact=single_val
                                ).values_list('id', flat=True)
                                ids_custom = Product.objects.filter(
                                    attribute_values__attribute__key=attr_key,
                                    attribute_values__custom_value__iexact=single_val
                                ).values_list('id', flat=True)
                                ids = set(ids_legacy) | set(ids_new) | set(ids_custom)
                            else:
                                legacy_q = Q()
                                new_q = Q()
                                custom_q = Q()
                                for v in values:
                                    legacy_q |= Q(
                                        legacy_attribute_set__key=attr_key,
                                        legacy_attribute_set__value__iexact=v
                                    )
                                    new_q |= Q(
                                        attribute_values__attribute__key=attr_key,
                                        attribute_values__attribute_value__value__iexact=v
                                    )
                                    custom_q |= Q(
                                        attribute_values__attribute__key=attr_key,
                                        attribute_values__custom_value__iexact=v
                                    )
                                ids_legacy = Product.objects.filter(legacy_q).values_list('id', flat=True)
                                ids_new = Product.objects.filter(new_q).values_list('id', flat=True)
                                ids_custom = Product.objects.filter(custom_q).values_list('id', flat=True)
                                ids = set(ids_legacy) | set(ids_new) | set(ids_custom)

                            if matching_product_ids is None:
                                matching_product_ids = set(ids)
                            else:
                                matching_product_ids &= set(ids)

                        if matching_product_ids is not None:
                            base_qs = base_qs.filter(product_id__in=list(matching_product_ids))

                    # Get sorting parameters
                    sort_by = request.GET.get('sort_by', 'display_order')
                    sort_order = request.GET.get('sort_order', 'asc')
                    
                    # Apply sorting
                    if sort_by == 'price_toman':
                        filtered_products = base_qs.order_by('product__price_toman' if sort_order == 'asc' else '-product__price_toman')
                    elif sort_by == 'price_usd':
                        filtered_products = base_qs.order_by('product__price_usd' if sort_order == 'asc' else '-product__price_usd')
                    elif sort_by == 'name':
                        filtered_products = base_qs.order_by('product__name' if sort_order == 'asc' else '-product__name')
                    elif sort_by == 'created_at':
                        filtered_products = base_qs.order_by('product__created_at' if sort_order == 'asc' else '-product__created_at')
                    else:
                        # Default to display_order
                        filtered_products = base_qs.order_by('display_order')
                    
                    # Apply pagination
                    total_count = filtered_products.count()
                    start_index = (page - 1) * per_page
                    end_index = start_index + per_page
                    paginated_products = filtered_products[start_index:end_index]
                    
                    # Build custom response with filtered products
                    from .serializers import SpecialOfferProductSerializer
                    
                    # Get filter summary for response
                    filter_summary = {}
                    if category_id:
                        filter_summary['category_id'] = category_id
                    if gender_filter:
                        filter_summary['gender'] = gender_filter
                    if multi_value_filters:
                        filter_summary['attributes'] = multi_value_filters
                    if price_filters:
                        filter_summary['price'] = price_filters
                    
                    # Calculate pagination info
                    total_pages = (total_count + per_page - 1) // per_page
                    has_next = page < total_pages
                    has_previous = page > 1
                    
                    return Response({
                        'success': True,
                        'offer': {
                            'id': offer.id,
                            'title': offer.title,
                            'description': offer.description,
                            'offer_type': offer.offer_type,
                            'display_style': offer.display_style,
                            'banner_image_url': request.build_absolute_uri(offer.banner_image.url) if offer.banner_image else None,
                            'banner_action_type': offer.banner_action_type,
                            'banner_action_target': offer.banner_action_target,
                            'banner_external_url': offer.banner_external_url,
                            'valid_from': offer.valid_from.isoformat(),
                            'valid_until': offer.valid_until.isoformat() if offer.valid_until else None,
                            'enabled': offer.enabled,
                            'is_active': offer.is_active,
                            'display_order': offer.display_order,
                            'products': SpecialOfferProductSerializer(paginated_products, many=True, context={'request': request}).data,
                            'remaining_time': offer.get_remaining_time(),
                            'is_currently_valid': offer.is_currently_valid(),
                            'applied_filters': filter_summary,
                            'total_filtered_products': total_count,
                            'sorting_applied': {
                                'sort_by': sort_by,
                                'sort_order': sort_order
                            },
                            'pagination': {
                                'current_page': page,
                                'per_page': per_page,
                                'total_pages': total_pages,
                                'total_products': total_count,
                                'has_next': has_next,
                                'has_previous': has_previous,
                                'next_page': page + 1 if has_next else None,
                                'previous_page': page - 1 if has_previous else None
                            }
                        }
                    })
                    
                except (ValueError, Category.DoesNotExist):
                    return Response({
                        'success': False,
                        'error': 'Invalid category_id or filter parameters'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Get sorting parameters
                sort_by = request.GET.get('sort_by', 'display_order')
                sort_order = request.GET.get('sort_order', 'asc')
                
                # Apply sorting
                if sort_by == 'price_toman':
                    if sort_order == 'asc':
                        all_products = SpecialOfferProduct.objects.filter(
                            offer=offer,
                            is_active=True,
                            product__is_active=True
                        ).select_related('product', 'product__category', 'product__category__gender').order_by('product__price_toman')
                    else:
                        all_products = SpecialOfferProduct.objects.filter(
                            offer=offer,
                            is_active=True,
                            product__is_active=True
                        ).select_related('product', 'product__category', 'product__category__gender').order_by('-product__price_toman')
                elif sort_by == 'price_usd':
                    if sort_order == 'asc':
                        all_products = SpecialOfferProduct.objects.filter(
                            offer=offer,
                            is_active=True,
                            product__is_active=True
                        ).select_related('product', 'product__category', 'product__category__gender').order_by('product__price_usd')
                    else:
                        all_products = SpecialOfferProduct.objects.filter(
                            offer=offer,
                            is_active=True,
                            product__is_active=True
                        ).select_related('product', 'product__category', 'product__category__gender').order_by('-product__price_usd')
                elif sort_by == 'name':
                    if sort_order == 'asc':
                        all_products = SpecialOfferProduct.objects.filter(
                            offer=offer,
                            is_active=True,
                            product__is_active=True
                        ).select_related('product', 'product__category', 'product__category__gender').order_by('product__name')
                    else:
                        all_products = SpecialOfferProduct.objects.filter(
                            offer=offer,
                            is_active=True,
                            product__is_active=True
                        ).select_related('product', 'product__category', 'product__category__gender').order_by('-product__name')
                elif sort_by == 'created_at':
                    if sort_order == 'asc':
                        all_products = SpecialOfferProduct.objects.filter(
                            offer=offer,
                            is_active=True,
                            product__is_active=True
                        ).select_related('product', 'product__category', 'product__category__gender').order_by('product__created_at')
                    else:
                        all_products = SpecialOfferProduct.objects.filter(
                            offer=offer,
                            is_active=True,
                            product__is_active=True
                        ).select_related('product', 'product__category', 'product__category__gender').order_by('-product__created_at')
                else:
                    # Default to display_order
                    all_products = SpecialOfferProduct.objects.filter(
                        offer=offer,
                        is_active=True,
                        product__is_active=True
                    ).select_related('product', 'product__category', 'product__category__gender').order_by('display_order')
                
                # Apply pagination
                total_count = all_products.count()
                start_index = (page - 1) * per_page
                end_index = start_index + per_page
                paginated_products = all_products[start_index:end_index]
                
                # Calculate pagination info
                total_pages = (total_count + per_page - 1) // per_page
                has_next = page < total_pages
                has_previous = page > 1
                
                serializer = SpecialOfferSerializer(offer, context={'request': request})
                offer_data = serializer.data
                
                # Update products with paginated data
                from .serializers import SpecialOfferProductSerializer
                offer_data['products'] = SpecialOfferProductSerializer(paginated_products, many=True, context={'request': request}).data
                offer_data['pagination'] = {
                    'current_page': page,
                    'per_page': per_page,
                    'total_pages': total_pages,
                    'total_products': total_count,
                    'has_next': has_next,
                    'has_previous': has_previous,
                    'next_page': page + 1 if has_next else None,
                    'previous_page': page - 1 if has_previous else None
                }
                
                # Add sorting info to response
                offer_data['sorting_applied'] = {
                    'sort_by': sort_by,
                    'sort_order': sort_order
                }
                
                return Response({
                    'success': True,
                    'offer': offer_data
                })
            
            # Analytics logging
            print(f"Special offer detail API called - Offer ID: {offer_id}, Title: {offer.title}, Category Filter: {category_id}")
            
        except SpecialOffer.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Special offer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error in special offer detail API: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve special offer',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SpecialOfferClickAPIView(APIView):
    """API endpoint for tracking special offer clicks"""
    permission_classes = [AllowAny]
    
    def post(self, request, offer_id):
        """Track a click on a special offer"""
        try:
            offer = SpecialOffer.objects.get(
                id=offer_id,
                enabled=True,
                is_active=True
            )
            
            # Check if offer is currently valid
            if not offer.is_currently_valid():
                return Response({
                    'success': False,
                    'error': 'Offer is not currently active'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Increment click count for analytics
            offer.increment_clicks()
            
            # Analytics logging
            print(f"Special offer clicked - Offer ID: {offer_id}, Title: {offer.title}")
            
            return Response({
                'success': True,
                'message': 'Click tracked successfully'
            })
            
        except SpecialOffer.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Special offer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error in special offer click API: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to track click',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SpecialOffersByTypeAPIView(APIView):
    """API endpoint for retrieving special offers by type"""
    permission_classes = [AllowAny]
    
    def get(self, request, offer_type):
        """Get special offers filtered by type"""
        try:
            # Get all enabled and currently valid offers of the specified type
            offers = SpecialOffer.objects.filter(
                enabled=True,
                is_active=True,
                offer_type=offer_type
            ).prefetch_related('products__product__images', 'products__product__category')
            
            # Filter offers that are currently valid
            valid_offers = []
            for offer in offers:
                if offer.is_currently_valid():
                    # Increment view count for analytics
                    offer.increment_views()
                    valid_offers.append(offer)
            
            # Serialize the offers
            serializer = SpecialOfferSerializer(
                valid_offers, 
                many=True, 
                context={'request': request}
            )
            
            # Analytics logging
            print(f"Special offers by type API called - Type: {offer_type}, Found: {len(valid_offers)} offers")
            
            return Response({
                'success': True,
                'offer_type': offer_type,
                'offers': serializer.data,
                'total_offers': len(valid_offers),
                'timestamp': timezone.now().timestamp()
            })
            
        except Exception as e:
            print(f"Error in special offers by type API: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve special offers',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FlashSalesAPIView(APIView):
    """API endpoint for flash sales specifically"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get flash sale offers"""
        view = SpecialOffersByTypeAPIView()
        view.request = request
        return view.get(request, 'flash_sale')


class DiscountsAPIView(APIView):
    """API endpoint for discount offers"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get discount offers"""
        view = SpecialOffersByTypeAPIView()
        view.request = request
        return view.get(request, 'discount')


class BundleDealsAPIView(APIView):
    """API endpoint for bundle deals"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get bundle deal offers"""
        view = SpecialOffersByTypeAPIView()
        view.request = request
        return view.get(request, 'bundle')


class FreeShippingAPIView(APIView):
    """API endpoint for free shipping offers"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get free shipping offers"""
        view = SpecialOffersByTypeAPIView()
        view.request = request
        return view.get(request, 'free_shipping')


class SeasonalOffersAPIView(APIView):
    """API endpoint for seasonal offers"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get seasonal offers"""
        view = SpecialOffersByTypeAPIView()
        view.request = request
        return view.get(request, 'seasonal')


class ClearanceOffersAPIView(APIView):
    """API endpoint for clearance offers"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get clearance offers"""
        view = SpecialOffersByTypeAPIView()
        view.request = request
        return view.get(request, 'clearance')


class CouponOffersAPIView(APIView):
    """API endpoint for coupon offers"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get coupon offers"""
        view = SpecialOffersByTypeAPIView()
        view.request = request
        return view.get(request, 'coupon')


class AdminSpecialOffersAPIView(APIView):
    """Admin API endpoint for CRUD operations on special offers"""
    permission_classes = [IsAdminUser]  # Only staff/admin can access
    
    def get(self, request):
        """Get all special offers for admin"""
        try:
            # Use raw SQL to avoid decimal conversion issues
            from django.db import connection
            
            offers = SpecialOffer.objects.all().order_by('-created_at')
            
            # Build offer data manually to avoid problematic prefetch
            offers_data = []
            for offer in offers:
                offer_data = {
                    'id': offer.id,
                    'title': offer.title,
                    'description': offer.description,
                    'offer_type': offer.offer_type,
                    'display_style': offer.display_style,
                    'banner_action_type': offer.banner_action_type,
                    'banner_action_target': offer.banner_action_target,
                    'banner_external_url': offer.banner_external_url,
                    'valid_from': offer.valid_from,
                    'valid_until': offer.valid_until,
                    'enabled': offer.enabled,
                    'is_active': offer.is_active,
                    'display_order': offer.display_order,
                    'remaining_time': offer.get_remaining_time(),
                    'is_currently_valid': offer.is_currently_valid(),
                    'banner_image_url': request.build_absolute_uri(offer.banner_image.url) if offer.banner_image else None,
                    'products': []  # We'll populate this separately
                }
                
                # Manually fetch products to avoid decimal conversion issues
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT sop.id, sop.discount_percentage, sop.discount_amount, 
                               sop.original_price, sop.discounted_price, sop.display_order,
                               p.id as product_id, p.name, p.price_toman, p.price_usd
                        FROM shop_specialofferproduct sop
                        JOIN shop_product p ON sop.product_id = p.id
                        WHERE sop.offer_id = %s
                        ORDER BY sop.display_order
                    """, [offer.id])
                    
                    for row in cursor.fetchall():
                        (sop_id, discount_percentage, discount_amount, original_price, 
                         discounted_price, display_order, product_id, product_name, 
                         price_toman, price_usd) = row
                        
                        # Safely convert decimal values
                        try:
                            safe_discount_amount = float(discount_amount) if discount_amount is not None else 0.0
                        except (ValueError, TypeError):
                            safe_discount_amount = 0.0
                            
                        try:
                            safe_original_price = float(original_price) if original_price is not None else 0.0
                        except (ValueError, TypeError):
                            safe_original_price = 0.0
                            
                        try:
                            safe_discounted_price = float(discounted_price) if discounted_price is not None else None
                        except (ValueError, TypeError):
                            safe_discounted_price = None
                            
                        try:
                            safe_price_toman = float(price_toman) if price_toman is not None else 0.0
                        except (ValueError, TypeError):
                            safe_price_toman = 0.0
                            
                        try:
                            safe_price_usd = float(price_usd) if price_usd is not None else None
                        except (ValueError, TypeError):
                            safe_price_usd = None
                        
                        product_data = {
                            'id': sop_id,
                            'discount_percentage': discount_percentage,
                            'discount_amount': safe_discount_amount,
                            'original_price': safe_original_price,
                            'discounted_price': safe_discounted_price,
                            'display_order': display_order,
                            'product': {
                                'id': product_id,
                                'name': product_name,
                                'price_toman': safe_price_toman,
                                'price_usd': safe_price_usd,
                                'images': [],  # We could populate this if needed
                                'category': None  # We could populate this if needed
                            }
                        }
                        offer_data['products'].append(product_data)
                
                offers_data.append(offer_data)
            
            return Response({
                'success': True,
                'offers': offers_data,
                'total_offers': len(offers_data),
                'timestamp': timezone.now().timestamp()
            })
            
        except Exception as e:
            import traceback
            print(f"Error in admin special offers API: {str(e)}")
            print("Full traceback:")
            traceback.print_exc()
            return Response({
                'success': False,
                'error': 'Failed to retrieve special offers',
                'details': str(e),
                'traceback': traceback.format_exc()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Create a new special offer"""
        try:
            from django.utils.dateparse import parse_datetime
            data = request.data.copy()
            
            # Parse datetime fields
            valid_from = data.get('valid_from')
            if valid_from:
                if isinstance(valid_from, str):
                    valid_from = parse_datetime(valid_from)
                    if valid_from and not timezone.is_aware(valid_from):
                        valid_from = timezone.make_aware(valid_from)
            
            valid_until = data.get('valid_until')
            if valid_until:
                if isinstance(valid_until, str):
                    valid_until = parse_datetime(valid_until)
                    if valid_until and not timezone.is_aware(valid_until):
                        valid_until = timezone.make_aware(valid_until)
            
            # Parse boolean fields
            enabled = data.get('enabled', True)
            if isinstance(enabled, str):
                enabled = enabled.lower() in ['true', '1', 'yes', 'on']
                
            is_active = data.get('is_active', True)  
            if isinstance(is_active, str):
                is_active = is_active.lower() in ['true', '1', 'yes', 'on']
            
            # Create the offer
            offer = SpecialOffer.objects.create(
                title=data.get('title'),
                description=data.get('description', ''),
                offer_type=data.get('offer_type'),
                display_style=data.get('display_style'),
                banner_image=data.get('banner_image') if data.get('banner_image') else None,
                banner_action_type=data.get('banner_action_type', 'none'),
                banner_action_target=data.get('banner_action_target', ''),
                banner_external_url=data.get('banner_external_url', ''),
                valid_from=valid_from,
                valid_until=valid_until,
                enabled=enabled,
                is_active=is_active,
                display_order=data.get('display_order', 1)
            )
            
            serializer = SpecialOfferSerializer(offer, context={'request': request})
            
            return Response({
                'success': True,
                'offer': serializer.data,
                'message': 'Special offer created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"Error creating special offer: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to create special offer',
                'details': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class AdminSpecialOfferDetailAPIView(APIView):
    """Admin API endpoint for individual special offer operations"""
    permission_classes = [IsAdminUser]  # Only staff/admin can access
    
    def get(self, request, offer_id):
        """Get a specific special offer for admin"""
        try:
            offer = get_object_or_404(SpecialOffer, id=offer_id)
            serializer = SpecialOfferSerializer(offer, context={'request': request})
            
            return Response({
                'success': True,
                'offer': serializer.data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'Special offer not found',
                'details': str(e)
            }, status=status.HTTP_404_NOT_FOUND)
    
    def put(self, request, offer_id):
        """Update a special offer"""
        try:
            from django.utils.dateparse import parse_datetime
            offer = get_object_or_404(SpecialOffer, id=offer_id)
            data = request.data.copy()
            
            # Update fields
            for field in ['title', 'description', 'offer_type', 'display_style', 
                         'banner_image', 'banner_action_type', 'banner_action_target', 'banner_external_url',
                         'valid_from', 'valid_until', 'enabled', 'is_active', 'display_order']:
                if field in data:
                    if field == 'valid_until' and not data[field]:
                        setattr(offer, field, None)
                    elif field in ['valid_from', 'valid_until'] and data[field]:
                        # Parse datetime fields
                        if isinstance(data[field], str):
                            parsed_datetime = parse_datetime(data[field])
                            if parsed_datetime and not timezone.is_aware(parsed_datetime):
                                parsed_datetime = timezone.make_aware(parsed_datetime)
                            setattr(offer, field, parsed_datetime)
                        else:
                            setattr(offer, field, data[field])
                    elif field in ['enabled', 'is_active']:
                        # Parse boolean fields
                        if isinstance(data[field], str):
                            setattr(offer, field, data[field].lower() in ['true', '1', 'yes', 'on'])
                        else:
                            setattr(offer, field, bool(data[field]))
                    else:
                        setattr(offer, field, data[field])
            
            offer.save()
            
            serializer = SpecialOfferSerializer(offer, context={'request': request})
            
            return Response({
                'success': True,
                'offer': serializer.data,
                'message': 'Special offer updated successfully'
            })
            
        except Exception as e:
            print(f"Error updating special offer: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to update special offer',
                'details': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, offer_id):
        """Partially update a special offer"""
        try:
            offer = get_object_or_404(SpecialOffer, id=offer_id)
            data = request.data.copy()
            
            # Update only provided fields
            for field, value in data.items():
                if hasattr(offer, field):
                    setattr(offer, field, value)
            
            offer.save()
            
            serializer = SpecialOfferSerializer(offer, context={'request': request})
            
            return Response({
                'success': True,
                'offer': serializer.data,
                'message': 'Special offer updated successfully'
            })
            
        except Exception as e:
            print(f"Error patching special offer: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to update special offer',
                'details': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, offer_id):
        """Delete a special offer"""
        try:
            offer = get_object_or_404(SpecialOffer, id=offer_id)
            offer_title = offer.title
            
            # Use raw SQL to avoid decimal conversion issues during cascading delete
            from django.db import connection
            
            with connection.cursor() as cursor:
                # First delete related SpecialOfferProduct records
                cursor.execute("DELETE FROM shop_specialofferproduct WHERE offer_id = %s", [offer_id])
                deleted_products = cursor.rowcount
                
                # Then delete the SpecialOffer record
                cursor.execute("DELETE FROM shop_specialoffer WHERE id = %s", [offer_id])
                deleted_offers = cursor.rowcount
            
            print(f"Deleted {deleted_products} products and {deleted_offers} offer(s) for offer ID {offer_id}")
            
            return Response({
                'success': True,
                'message': f'پیشنهاد ویژه "{offer_title}" با موفقیت حذف شد',
                'deleted_products': deleted_products,
                'deleted_offers': deleted_offers
            })
            
        except Exception as e:
            import traceback
            print(f"Error deleting special offer: {str(e)}")
            print("Full traceback:")
            traceback.print_exc()
            return Response({
                'success': False,
                'error': 'Failed to delete special offer',
                'details': str(e),
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class AdminSpecialOfferProductsAPIView(APIView):
    """Admin API endpoint for managing special offer products"""
    permission_classes = [AllowAny]  # Change to staff permissions in production
    
    def post(self, request, offer_id):
        """Update products for a special offer"""
        try:
            offer = get_object_or_404(SpecialOffer, id=offer_id)
            products_data = request.data.get('products', [])
            
            print(f"Updating products for offer {offer_id}: {products_data}")
            
            # Clear existing products using raw SQL to avoid decimal conversion issues
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM shop_specialofferproduct WHERE offer_id = %s", [offer_id])
            
            # Add new products with safe decimal handling
            created_products = []
            for index, product_data in enumerate(products_data, 1):
                product_id = product_data.get('product_id')
                discount_percentage = int(product_data.get('discount_percentage', 0))
                discount_amount = product_data.get('discount_amount', 0)
                
                # Safely convert discount_amount to decimal
                try:
                    from decimal import Decimal
                    discount_amount = Decimal(str(discount_amount)) if discount_amount else Decimal('0.00')
                    # Ensure it's within reasonable bounds
                    if discount_amount > Decimal('999999999.99'):
                        discount_amount = Decimal('0.00')
                except (ValueError, TypeError, InvalidOperation):
                    discount_amount = Decimal('0.00')
                
                try:
                    product = Product.objects.get(id=product_id, is_active=True)
                    
                    # Safely get original price
                    try:
                        original_price = Decimal(str(product.price_toman)) if product.price_toman else Decimal('0.00')
                        # Ensure it's within reasonable bounds
                        if original_price > Decimal('999999999.99'):
                            original_price = Decimal('0.00')
                    except (ValueError, TypeError, InvalidOperation):
                        original_price = Decimal('0.00')
                    
                    # Create using raw SQL to avoid model validation issues
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO shop_specialofferproduct 
                            (offer_id, product_id, discount_percentage, discount_amount, 
                             original_price, discounted_price, display_order, is_active, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, [
                            offer_id, product_id, discount_percentage, float(discount_amount),
                            float(original_price), None, index, True, 
                            timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                        ])
                    
                    created_products.append({
                        'product_id': product_id,
                        'product_name': product.name,
                        'discount_percentage': discount_percentage,
                        'discount_amount': float(discount_amount),
                        'original_price': float(original_price)
                    })
                    
                except Product.DoesNotExist:
                    print(f"Product {product_id} not found or inactive")
                    continue  # Skip invalid products
                except Exception as product_error:
                    print(f"Error adding product {product_id}: {product_error}")
                    continue
            
            print(f"Successfully created {len(created_products)} products for offer {offer_id}")
            
            return Response({
                'success': True,
                'message': f'تم تحديث {len(created_products)} منتج للعرض "{offer.title}"',
                'created_products': created_products,
                'total_products': len(created_products)
            })
            
        except Exception as e:
            import traceback
            print(f"Error updating special offer products: {str(e)}")
            print("Full traceback:")
            traceback.print_exc()
            return Response({
                'success': False,
                'error': 'Failed to update special offer products',
                'details': str(e),
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class ProductsWithSaleInfoAPIView(APIView):
    """API endpoint for products with sale information"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get products with sale information"""
        try:
            # Get all active products
            products = Product.objects.filter(is_active=True).prefetch_related(
                'specialofferproduct_set__offer',
                'images',
                'productattribute_set__attribute'
            )
            
            # Serialize with sale info
            serializer = ProductSerializer(products, many=True, context={'request': request})
            
            # Add sale statistics
            total_products = products.count()
            products_on_sale = sum(1 for product in products if product.is_on_sale)
            
            return Response({
                'success': True,
                'products': serializer.data,
                'statistics': {
                    'total_products': total_products,
                    'products_on_sale': products_on_sale,
                    'sale_percentage': round((products_on_sale / total_products) * 100, 2) if total_products > 0 else 0
                },
                'timestamp': timezone.now().timestamp()
            })
            
        except Exception as e:
            print(f"Error in products with sale info API: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to retrieve products with sale info',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# -----------------------------
# Session-based Basket APIs
# -----------------------------

BASKET_SESSION_KEY = 'basket_v1'


def _get_session_basket(request):
    """Return mutable basket dict from session; ensure structure exists."""
    basket = request.session.get(BASKET_SESSION_KEY)
    if not basket or not isinstance(basket, dict):
        basket = {'items': {}, 'currency': 'toman', 'updated_at': timezone.now().isoformat()}
        request.session[BASKET_SESSION_KEY] = basket
    basket.setdefault('items', {})
    basket['currency'] = 'toman'
    return basket


def _save_session_basket(request, basket):
    basket['updated_at'] = timezone.now().isoformat()
    request.session[BASKET_SESSION_KEY] = basket
    request.session.modified = True


def _serialize_basket(basket):
    """Compute totals from Product.price_toman and serialize basket."""
    items = []
    merchandise_subtotal = 0.0

    product_ids = [int(pid) for pid in basket.get('items', {}).keys()]
    products_by_id = {}
    if product_ids:
        for p in Product.objects.filter(id__in=product_ids, is_active=True):
            products_by_id[p.id] = p

    for pid_str, qty in basket.get('items', {}).items():
        try:
            pid = int(pid_str)
        except Exception:
            continue
        quantity = max(0, int(qty))
        if quantity == 0:
            continue
        product = products_by_id.get(pid)
        if not product:
            continue
        unit_price = float(product.price_toman or 0)
        line_subtotal = unit_price * quantity
        merchandise_subtotal += line_subtotal
        items.append({
            'product': {
                'id': product.id,
                'name': product.name,
                'price_toman': unit_price,
                'image_url': get_product_image_url(product),
            },
            'quantity': quantity,
            'item_subtotal': line_subtotal,
        })

    discount_total = 0.0
    shipping_total = 0.0
    tax_total = 0.0
    grand_total = merchandise_subtotal - discount_total + shipping_total + tax_total

    return {
        'currency': 'toman',
        'items': items,
        'summary': {
            'merchandise_subtotal': merchandise_subtotal,
            'discount_total': discount_total,
            'shipping_total': shipping_total,
            'tax_total': tax_total,
            'grand_total': grand_total,
            'item_count': sum(i['quantity'] for i in items),
        }
    }


def get_product_image_url(product):
    """Get product image URL"""
    try:
        first_image = product.images.first()
        if first_image and first_image.image:
            return first_image.image.url
    except:
        pass
    return None


# -----------------------------
# Orders API
# -----------------------------

def serialize_order(order):
    items = []
    subtotal = 0.0
    for it in order.items.select_related('product').all():
        line = float(it.price) * it.quantity
        subtotal += line
        items.append({
            'id': it.id,
            'product': {
                'id': it.product.id,
                'name': it.product.name,
                'image_url': get_product_image_url(it.product, request),
            },
            'price_toman': float(it.price),
            'quantity': it.quantity,
            'subtotal': line,
        })
    return {
        'id': order.id,
        'customer': {
            'first_name': order.first_name,
            'last_name': order.last_name,
            'email': order.email,
            'address': order.address,
            'postal_code': order.postal_code,
            'city': order.city,
        },
        'created': order.created.isoformat(),
        'updated': order.updated.isoformat(),
        'paid': order.paid,
        'totals': {
            'grand_total': subtotal,
            'item_count': sum(i['quantity'] for i in items),
        },
        'items': items,
    }


@api_view(['GET'])
def api_orders_list(request):
    """List orders with search, filters, sorting, pagination."""
    from .models import Order
    
    q = request.GET.get('q', '').strip()
    status_paid = request.GET.get('paid')  # 'true' | 'false' | None
    sort = request.GET.get('sort', '-created')  # '-created', 'created', '-total', 'total'
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 20))

    orders = Order.objects.all()
    if q:
        orders = orders.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q) | Q(id__icontains=q)
        )
    if status_paid in ['true', 'false']:
        orders = orders.filter(paid=(status_paid == 'true'))

    # Sorting
    if sort in ['created', '-created', 'updated', '-updated']:
        orders = orders.order_by(sort)
    elif sort in ['total', '-total']:
        # Annotate totals via Python after fetch; simple approach due to model simplicity
        orders = list(orders)
        orders.sort(key=lambda o: float(sum(i.price * i.quantity for i in o.items.all())), reverse=sort == '-total')
    else:
        orders = orders.order_by('-created')

    # Pagination
    paginator = Paginator(orders, limit)
    page_obj = paginator.get_page(page)

    data = [serialize_order(o) for o in page_obj]
    return Response({
        'success': True,
        'orders': data,
        'pagination': {
            'page': page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    })


@api_view(['GET'])
def api_orders_detail(request, order_id):
    from .models import Order
    
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({'success': False, 'error': 'Order not found'}, status=404)
    return Response({'success': True, 'order': serialize_order(order)})


@api_view(['POST'])
def api_orders_update_paid(request, order_id):
    from .models import Order
    
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({'success': False, 'error': 'Order not found'}, status=404)
    paid = request.data.get('paid')
    if paid is None:
        return Response({'success': False, 'error': 'paid is required'}, status=400)
    order.paid = bool(paid) if isinstance(paid, bool) else str(paid).lower() == 'true'
    order.save(update_fields=['paid', 'updated'])
    return Response({'success': True, 'order': serialize_order(order)})


@api_view(['GET'])
def api_orders_export_csv(request):
    from .models import Order
    import csv
    from io import StringIO
    
    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(['id','first_name','last_name','email','created','paid','item_count','grand_total'])
    for o in Order.objects.all().order_by('-created'):
        total = sum(i.price * i.quantity for i in o.items.all())
        writer.writerow([o.id, o.first_name, o.last_name, o.email, o.created.isoformat(), o.paid, o.items.count(), total])
    return Response({'success': True, 'content_type': 'text/csv', 'filename': 'orders.csv', 'data': sio.getvalue()})


# ========================================
# PRODUCT VARIANTS API ENDPOINTS
# ========================================

@api_view(['GET'])
def api_products_with_variants(request):
    """
    Get products with their variants
    URL: /api/products-with-variants/
    Parameters:
        - category: Category name (e.g., 'ساعت')
        - gender: Gender filter ('مردانه', 'زنانه', 'یونیسکس')
        - page: Page number for pagination
        - limit: Items per page (default: 20)
        - search: Search query
    """
    try:
        category_name = request.GET.get('category')
        gender = request.GET.get('gender')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        search_query = request.GET.get('search', '')
        
        # Start with active products that have variants
        products = Product.objects.filter(is_active=True, variants__isnull=False).distinct()
        
        # Apply category filter
        if category_name:
            if gender:
                gender_category_name = f"{category_name} {gender}"
                gender_category = Category.objects.filter(name=gender_category_name).first()
                if gender_category:
                    products = products.filter(category=gender_category)
                else:
                    # Fallback to attribute-based filtering
                    products = products.filter(
                        category__name__icontains=category_name,
                        attribute_values__attribute__key='جنسیت',
                        attribute_values__attribute_value__value=gender
                    ).distinct()
            else:
                main_category = Category.objects.filter(name=category_name).first()
                if main_category:
                    all_subcategories = [main_category] + list(main_category.get_all_subcategories())
                    products = products.filter(category__in=all_subcategories)
        
        # Apply search filter
        if search_query:
            products = products.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(model__icontains=search_query)
            )
        
        # Order by creation date (newest first)
        products = products.order_by('-created_at')
        
        # Paginate results
        paginator = Paginator(products, limit)
        page_obj = paginator.get_page(page)
        
        # Serialize products with variants
        products_data = []
        for product in page_obj:
            # Get all variants for this product
            variants_data = []
            for variant in product.variants.filter(is_active=True):
                variant_data = {
                    'id': variant.id,
                    'sku': variant.sku,
                    'price_toman': float(variant.price_toman),
                    'stock_quantity': variant.stock_quantity,
                    'is_active': variant.is_active,
                    'attributes': variant.attributes,  # JSONField
                    'created_at': variant.created_at.isoformat(),
                    'image_url': get_variant_image_url(variant, request)
                }
                variants_data.append(variant_data)
            
            product_data = {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'category_id': product.category.id,
                'category_name': product.category.name,
                'image_url': get_product_image_url(product),
                'attributes': get_product_attributes(product),
                'created_at': product.created_at.isoformat(),
                'supplier': product.supplier.name if product.supplier else None,
                'variants': variants_data,
                'variants_count': len(variants_data),
                'price_range': get_product_price_range(product),
                'total_stock': sum(v['stock_quantity'] for v in variants_data)
            }
            products_data.append(product_data)
        
        return Response({
            'success': True,
            'products': products_data,
            'pagination': {
                'page': page,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            },
            'filters': {
                'category': category_name,
                'gender': gender,
                'search': search_query
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
def api_product_variants(request, product_id):
    """
    Get all variants for a specific product
    URL: /api/products/{product_id}/variants/
    """
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        variants = product.variants.filter(is_active=True)
        
        variants_data = []
        for variant in variants:
            variant_data = {
                'id': variant.id,
                'sku': variant.sku,
                'price_toman': float(variant.price_toman),
                'stock_quantity': variant.stock_quantity,
                'is_active': variant.is_active,
                'is_default': variant.is_default,
                'attributes': variant.attributes,
                'created_at': variant.created_at.isoformat(),
                'image_url': get_variant_image_url(variant)
            }
            variants_data.append(variant_data)
        
        return Response({
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'category_name': product.category.name
            },
            'variants': variants_data,
            'variants_count': len(variants_data)
        })
        
    except Product.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Product not found'
        }, status=404)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
def api_variants_by_attributes(request):
    """
    Get variants filtered by attributes
    URL: /api/variants/
    Parameters:
        - product_id: Filter by specific product
        - attr_color: Filter by color attribute
        - attr_size: Filter by size attribute
        - page: Page number for pagination
        - limit: Items per page (default: 20)
    """
    try:
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        product_id = request.GET.get('product_id')
        
        # Start with active variants
        variants = ProductVariant.objects.filter(is_active=True)
        
        # Filter by product
        if product_id:
            variants = variants.filter(product_id=product_id)
        
        # Filter by attributes (dynamic filtering)
        for key, value in request.GET.items():
            if key.startswith('attr_'):
                attr_name = key[5:]  # Remove 'attr_' prefix
                # Use JSONField lookup for SQLite compatibility
                variants = variants.filter(**{f'attributes__{attr_name}': value})
        
        # Order by SKU
        variants = variants.order_by('sku')
        
        # Paginate results
        paginator = Paginator(variants, limit)
        page_obj = paginator.get_page(page)
        
        # Serialize variants
        variants_data = []
        for variant in page_obj:
            variant_data = {
                'id': variant.id,
                'sku': variant.sku,
                'price_toman': float(variant.price_toman),
                'stock_quantity': variant.stock_quantity,
                'is_active': variant.is_active,
                'is_default': variant.is_default,
                'attributes': variant.attributes,
                'created_at': variant.created_at.isoformat(),
                'image_url': get_variant_image_url(variant),
                'product': {
                    'id': variant.product.id,
                    'name': variant.product.name,
                    'category_name': variant.product.category.name,
                    'image_url': get_product_image_url(variant.product, request)
                }
            }
            variants_data.append(variant_data)
        
        return Response({
            'success': True,
            'variants': variants_data,
            'pagination': {
                'page': page,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


def get_product_image_url(product, request=None):
    """Get product image URL with full absolute URL"""
    try:
        first_image = product.images.filter(is_primary=True).first()
        if not first_image:
            first_image = product.images.first()
        if first_image and first_image.image:
            url = first_image.image.url
            if not url.startswith(('http://', 'https://')):
                if request:
                    url = request.build_absolute_uri(url)
                else:
                    # Fallback: use Render domain if available
                    import os
                    render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://myshop-backend-an7h.onrender.com')
                    if url.startswith('/'):
                        url = f"{render_url}{url}"
                    else:
                        url = f"{render_url}/{url}"
            return url
    except:
        pass
    return None


def get_variant_image_url(variant, request=None):
    """Get variant-specific image URL, fallback to product image"""
    try:
        # First try to get variant-specific images
        variant_image = variant.images.first()
        if variant_image and variant_image.image:
            url = variant_image.image.url
            if not url.startswith(('http://', 'https://')):
                if request:
                    url = request.build_absolute_uri(url)
                else:
                    # Fallback: use Render domain if available
                    import os
                    render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://myshop-backend-an7h.onrender.com')
                    if url.startswith('/'):
                        url = f"{render_url}{url}"
                    else:
                        url = f"{render_url}/{url}"
            return url
        
        # Fallback to product images
        return get_product_image_url(variant.product, request)
    except:
        # Final fallback to product images
        return get_product_image_url(variant.product, request)


def get_product_attributes(product):
    """Get product attributes as a list"""
    attributes = []
    try:
        for attr_value in product.attribute_values.all():
            attributes.append({
                'key': attr_value.attribute.key,
                'value': attr_value.get_display_value(),
                'display_name': attr_value.attribute.name
            })
    except:
        pass
    return attributes


def get_product_price_range(product):
    """Get price range for a product with variants"""
    try:
        variants = product.variants.filter(is_active=True)
        if not variants.exists():
            return None
        
        prices = [float(v.price_toman) for v in variants if v.price_toman]
        if not prices:
            return None
        
        min_price = min(prices)
        max_price = max(prices)
        
        if min_price == max_price:
            return f"{min_price:,.0f} تومان"
        else:
            return f"{min_price:,.0f} - {max_price:,.0f} تومان"
    except:
        return None