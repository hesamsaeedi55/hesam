from django.urls import path, register_converter
from . import views
from .api_views import (
    CategoryProductFilterView, ProductsFilterView, debug_category1_attributes, 
    debug_category_attributes_structure, cleanup_product_attributes, assign_sample_attributes,
    WishlistListCreateAPIView, WishlistDestroyAPIView, toggle_wishlist, wishlist_status,
    api_categories_with_gender, api_products_by_gender_category, api_unified_products,
    api_organized_categories, api_direct_categories, api_category_detail, api_category_products,
    api_subcategory_products, api_hierarchical_category_products, api_hierarchical_category_detail,
    api_improved_categories, api_group_products, api_genders_list, api_categories_by_gender,
    api_products_by_gender_table, api_gender_category_tree, api_gender_statistics,
    api_parent_categories_by_gender, api_child_categories_by_gender, api_child_categories_by_parent_and_gender, api_flattened_categories_by_gender,
    api_category_attribute_values_with_products, api_category_attribute_values, api_category_dynamic_attribute_values,
    api_category_categorization_key, api_leaf_categories, api_special_offer_categories, SpecialOffersAPIView, SpecialOfferDetailAPIView, SpecialOfferClickAPIView,
    SpecialOffersByTypeAPIView, FlashSalesAPIView, DiscountsAPIView, BundleDealsAPIView, FreeShippingAPIView, 
    SeasonalOffersAPIView, ClearanceOffersAPIView, CouponOffersAPIView, AdminSpecialOffersAPIView, 
    AdminSpecialOfferDetailAPIView, AdminSpecialOfferProductsAPIView, ProductsWithSaleInfoAPIView,
    # Order APIs
    api_orders_list, api_orders_detail, api_orders_update_paid, api_orders_export_csv,
    # Product Variants APIs
    api_products_with_variants, api_product_variants, api_variants_by_attributes
)

# Custom converter for hierarchical category paths
class CategoryPathConverter:
    regex = r'[\d/]+'
    
    def to_python(self, value):
        # Split by '/' and convert to integers
        return [int(x) for x in value.split('/') if x.isdigit()]
    
    def to_url(self, value):
        # Convert list of integers back to path
        return '/'.join(str(x) for x in value)

register_converter(CategoryPathConverter, 'categorypath')

app_name = 'shop'

urlpatterns = [
    path('reorder-images/', views.reorder_images, name='reorder_images'),
    path('product/<int:product_id>/sort-images/', views.sort_product_images, name='sort_product_images'),
    path('productimage/<int:image_id>/delete/', views.delete_product_image, name='delete_product_image'),
    path('productimage/<int:image_id>/update-order/', views.update_image_order, name='update_image_order'),
    path('admin/products/', views.ProductsExplorerAdminView.as_view(), name='admin_products_explorer'),
    path('product/<int:product_id>/detail/', views.product_detail, name='product_detail'),
    path('get-tags-for-category/', views.get_tags_for_category, name='get_tags_for_category'),
    path('product/<int:product_id>/similar-by-tags/', views.get_similar_products_by_tags, name='similar_products_by_tags'),
    path('product/<int:product_id>/similar-by-attributes/', views.get_similar_products_by_attributes, name='similar_products_by_attributes'),
    path('api/products/by-tags/', views.get_products_by_tags, name='products_by_tags'),
    path('api/tags/popular/', views.get_popular_tags, name='popular_tags'),
    path('api/tags/suggest/', views.get_tag_suggestions, name='tag_suggestions'),
    path('product/<int:product_id>/delete/', views.delete_product, name='delete_product'),
    path('api/products/', views.api_products, name='api_products'),
    path('api/products/advanced-search/', views.api_advanced_search, name='api_advanced_search'),
    path('api/products/search/', views.api_simple_search, name='api_products_search'),
    path('admin/backup-logs/', views.backup_logs, name='backup_logs'),
    path('admin/backup-download/<str:filename>/', views.download_backup, name='download_backup'),
    path('admin/backup-delete/<str:filename>/', views.delete_backup, name='delete_backup'),
    path('admin/backup-trigger/', views.trigger_backup, name='trigger_backup'),
    path('admin/backup-status/', views.get_backup_status, name='backup_status'),
    path('api/categories/simple/', views.api_categories, name='api_categories'),
    path('api/category/<int:category_id>/attributes/', views.api_category_attributes, name='api_category_attributes'),
    path('test/category/<int:category_id>/', views.test_simple_view, name='test_simple_view'),
    path('manage/category/<int:category_id>/attributes/', views.manage_category_attributes, name='manage_category_attributes'),
    path('manage/attribute/<int:attribute_id>/values/', views.manage_attribute_values, name='manage_attribute_values'),
    path('api/category/<int:category_id>/attribute/<str:attribute_key>/values-with-products/', api_category_attribute_values_with_products, name='api_category_attribute_values_with_products'),
    path('api/category/<int:category_id>/attribute/<str:attribute_key>/values/', api_category_attribute_values, name='api_category_attribute_values'),
    path('api/category/<int:category_id>/dynamic-attribute-values/', api_category_dynamic_attribute_values, name='api_category_dynamic_attribute_values'),
    path('api/category/<int:category_id>/categorization-key/', api_category_categorization_key, name='api_category_categorization_key'),
    path('api/category/<int:category_id>/filter/', CategoryProductFilterView.as_view(), name='category-product-filter'),
    path('api/products/filter/', ProductsFilterView.as_view(), name='products-filter'),
    path('api/debug/category1-attributes/', debug_category1_attributes),
    path('api/debug/category/<int:category_id>/attributes-structure/', debug_category_attributes_structure),
    path('api/cleanup-product-attributes/<int:product_id>/', cleanup_product_attributes),
    path('api/assign-sample-attributes/', assign_sample_attributes, name='assign_sample_attributes'),
    path('search/', views.search_page, name='search'),
    
    # New Arrivals URLs
    path('new-arrivals/', views.new_arrivals, name='new_arrivals'),
    path('api/new-arrivals/', views.api_new_arrivals, name='api_new_arrivals'),
    path('admin/new-arrivals/', views.admin_new_arrivals, name='admin_new_arrivals'),
    
    # Wishlist URLs
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('api/wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    path('api/wishlist/remove/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('api/wishlist/status/', views.get_wishlist_status, name='get_wishlist_status'),
    path('products-with-wishlist/', views.product_list_with_wishlist, name='product_list_with_wishlist'),
    
    # REST API Wishlist endpoints
    path('api/v1/wishlist/', WishlistListCreateAPIView.as_view(), name='api_wishlist_list_create'),
    path('api/v1/wishlist/product/<int:product_id>/', WishlistDestroyAPIView.as_view(), name='api_wishlist_destroy'),
    path('api/v1/wishlist/toggle/', toggle_wishlist, name='api_wishlist_toggle'),
    path('api/v1/wishlist/status/', wishlist_status, name='api_wishlist_status'),
    
    # Gender-based category and product API endpoints
    path('api/category/', api_categories_with_gender, name='api_categories_gender'),
    path('api/products/', api_products_by_gender_category, name='api_products_gender'),
    path('api/products/by-gender-category/', api_products_by_gender_category, name='api_products_by_gender_category'), 
    path('api/products/unified/', api_unified_products, name='api_unified_products'),
    path('api/organized-categories/', api_organized_categories, name='api_organized_categories'),
    path('api/categories/direct/', api_direct_categories, name='api_direct_categories'),
    
    # New Gender Table-based API endpoints
    path('api/genders/', api_genders_list, name='api_genders_list'),
    path('api/categories/by-gender/', api_categories_by_gender, name='api_categories_by_gender'),
    path('api/categories/parents/by-gender/', api_parent_categories_by_gender, name='api_parent_categories_by_gender'),
    path('api/categories/children/by-gender/', api_child_categories_by_gender, name='api_child_categories_by_gender'),
    path('api/categories/parent/<int:parent_id>/children/by-gender/', api_child_categories_by_parent_and_gender, name='api_child_categories_by_parent_and_gender'),
    path('api/categories/parent/<int:parent_id>/flattened-by-gender/', api_flattened_categories_by_gender, name='api_flattened_categories_by_gender'),
    path('api/products/by-gender-table/', api_products_by_gender_table, name='api_products_by_gender_table'),
    path('api/gender-category-tree/', api_gender_category_tree, name='api_gender_category_tree'),
    path('api/gender-statistics/', api_gender_statistics, name='api_gender_statistics'),
    
    # Hierarchical category access endpoints (must come before single category endpoints)
    path('api/category/<path:category_path>/products/', api_hierarchical_category_products, name='api_hierarchical_category_products'),
    path('api/category/<path:category_path>/', api_hierarchical_category_detail, name='api_hierarchical_category_detail'),
    
    # Dynamic category access endpoints
    path('api/category/<int:category_id>/', api_category_detail, name='api_category_detail'),
    path('api/category/<int:category_id>/products/', api_category_products, name='api_category_products'),
    path('api/category/<int:parent_category_id>/subcategories/products/', api_subcategory_products, name='api_subcategory_products'),
    
    # Improved category system endpoints
    path('api/improved-categories/', api_improved_categories, name='api_improved_categories'),
    path('api/groups/<int:group_id>/products/', api_group_products, name='api_group_products'),
    
    # New Leaf Categories Endpoint
    path('api/categories/leaf/', api_leaf_categories, name='api_leaf_categories'),
    
    # Special Offers API endpoints
    path('api/special-offers/', SpecialOffersAPIView.as_view(), name='api_special_offers'),
    path('api/special-offers/<int:offer_id>/', SpecialOfferDetailAPIView.as_view(), name='api_special_offer_detail'),
    path('api/special-offers/<int:offer_id>/click/', SpecialOfferClickAPIView.as_view(), name='api_special_offer_click'),
    path('api/special-offers/<int:offer_id>/categories/', api_special_offer_categories, name='api_special_offer_categories'),
    
    # Special Offers by Type API
    path('api/special-offers/type/<str:offer_type>/', SpecialOffersByTypeAPIView.as_view(), name='api_special_offers_by_type'),
    path('api/flash-sales/', FlashSalesAPIView.as_view(), name='api_flash_sales'),
    path('api/discounts/', DiscountsAPIView.as_view(), name='api_discounts'),
    path('api/bundle-deals/', BundleDealsAPIView.as_view(), name='api_bundle_deals'),
    path('api/free-shipping/', FreeShippingAPIView.as_view(), name='api_free_shipping'),
    path('api/seasonal-offers/', SeasonalOffersAPIView.as_view(), name='api_seasonal_offers'),
    path('api/clearance/', ClearanceOffersAPIView.as_view(), name='api_clearance'),
    path('api/coupons/', CouponOffersAPIView.as_view(), name='api_coupons'),
    
    # Product detail endpoint
    path('api/product/<int:product_id>/detail/', views.public_product_detail, name='public_product_detail'),
    
    # Modern Special Offers UI
    path('offers/modern/', views.modern_special_offers_view, name='modern_special_offers'),
    
    # Admin Special Offers APIs
    path('api/admin/special-offers/', AdminSpecialOffersAPIView.as_view(), name='admin_special_offers'),
    path('api/admin/special-offers/<int:offer_id>/', AdminSpecialOfferDetailAPIView.as_view(), name='admin_special_offer_detail'),
    path('api/admin/special-offers/<int:offer_id>/products/', AdminSpecialOfferProductsAPIView.as_view(), name='admin_special_offer_products'),
    
    # Admin Special Offers UI
    path('admin/offers/', views.admin_special_offers_view, name='admin_special_offers'),
    
    # Products with Sale Info API
    path('api/products/with-sale-info/', ProductsWithSaleInfoAPIView.as_view(), name='api_products_with_sale_info'),
    
    # Order APIs
    path('api/orders/', api_orders_list, name='api_orders_list'),
    path('api/orders/export/csv/', api_orders_export_csv, name='api_orders_export_csv'),
    path('api/orders/<int:order_id>/', api_orders_detail, name='api_orders_detail'),
    path('api/orders/<int:order_id>/paid/', api_orders_update_paid, name='api_orders_update_paid'),
    
    # Product Variants APIs
    path('api/products-with-variants/', api_products_with_variants, name='api_products_with_variants'),
    path('api/products/<int:product_id>/variants/', api_product_variants, name='api_product_variants'),
    path('api/variants/', api_variants_by_attributes, name='api_variants_by_attributes'),
    
    # Customer API endpoints
    path('api/customer/products/', views.api_customer_products, name='api_customer_products'),
    path('api/customer/cart/', views.api_customer_cart, name='api_customer_cart'),
    path('api/customer/cart/add/', views.api_customer_cart_add, name='api_customer_cart_add'),
    path('api/customer/cart/update/', views.api_customer_cart_update, name='api_customer_cart_update'),
    path('api/customer/cart/remove/', views.api_customer_cart_remove, name='api_customer_cart_remove'),
    path('api/customer/checkout/', views.api_customer_checkout, name='api_customer_checkout'),
    path('api/customer/orders/', views.api_customer_orders, name='api_customer_orders'),
    path('api/customer/orders/<int:order_id>/', views.api_customer_order_detail, name='api_customer_order_detail'),
    path('api/customer/orders/<int:order_id>/cancel/', views.api_customer_order_cancel, name='api_customer_order_cancel'),
    path('api/customer/orders/<int:order_id>/track/', views.api_customer_order_track, name='api_customer_order_track'),
    
    # Order Return/Rejection endpoints
    path('api/customer/orders/<int:order_id>/return/', views.api_customer_order_return, name='api_customer_order_return'),
    path('api/customer/orders/<int:order_id>/items/<int:item_id>/return/', views.api_customer_order_item_return, name='api_customer_order_item_return'),
    path('api/customer/orders/<int:order_id>/reject/', views.api_customer_order_reject, name='api_customer_order_reject'),
    path('api/customer/orders/<int:order_id>/items/<int:item_id>/reject/', views.api_customer_order_item_reject, name='api_customer_order_item_reject'),
    path('api/customer/orders/returns/', views.api_customer_order_returns_list, name='api_customer_order_returns_list'),
    path('api/customer/orders/returns/<int:return_id>/', views.api_customer_order_return_detail, name='api_customer_order_return_detail'),
    
    path('api/debug/session/', views.api_debug_session, name='api_debug_session'),
    path('api/debug/add-to-cart/', views.api_debug_add_to_cart, name='api_debug_add_to_cart'),
]