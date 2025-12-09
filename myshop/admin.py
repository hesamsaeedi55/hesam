from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth import get_user_model
from suppliers.models import Supplier, Store, SupplierAdmin, SupplierInvitation, BackupLog
from suppliers.admin import BackupLogAdmin
from shop.models import (
    Category, Product, ProductAttribute, ProductImage, Order, OrderItem, Tag, 
    Attribute, ProductAttributeValue, NewAttributeValue, CategoryAttribute, AttributeValue,
    DeletedProduct, Wishlist, CategoryGender, CategoryGroup, CategorySubgroup,
    SpecialOffer, SpecialOfferProduct, ProductVariant, Cart, CartItem
)
from shop.admin import (
    CategoryAdmin, ProductAdmin, ProductAttributeAdmin, ProductImageAdmin, TagAdmin, OrderAdmin,
    AttributeAdmin, NewAttributeValueAdmin, CategoryAttributeAdmin, AttributeValueAdmin,
    DeletedProductAdmin, WishlistAdmin, CategoryGenderAdmin, CategoryGroupAdmin, CategorySubgroupAdmin,
    SpecialOfferAdmin, SpecialOfferProductAdmin, ProductVariantAdmin, ProductVariantInline,
    CartAdmin, CartItemAdmin
)

SupplierUser = get_user_model()

class MyShopAdminSite(admin.AdminSite):
    def has_permission(self, request):
        """
        Allow access to the admin site if the user is:
        1. A staff member
        """
        if not request.user.is_active:
            return False
            
        if request.user.is_staff:
            return True
            
        return False

admin_site = MyShopAdminSite(name='admin')

# Register the default models
admin_site.register(Group, GroupAdmin)

# Register supplier models with the custom admin site
admin_site.register(Supplier)
admin_site.register(Store)
admin_site.register(SupplierAdmin)
admin_site.register(SupplierInvitation)
admin_site.register(BackupLog, BackupLogAdmin)

# Register shop models with the custom admin site
admin_site.register(Category, CategoryAdmin)
admin_site.register(Product, ProductAdmin)
admin_site.register(ProductAttribute, ProductAttributeAdmin)
admin_site.register(ProductImage, ProductImageAdmin)
admin_site.register(ProductVariant, ProductVariantAdmin)
admin_site.register(Order, OrderAdmin)
admin_site.register(Tag, TagAdmin)
admin_site.register(Wishlist, WishlistAdmin)

# Register new flexible attribute system models
admin_site.register(Attribute, AttributeAdmin)
admin_site.register(NewAttributeValue, NewAttributeValueAdmin)
admin_site.register(CategoryAttribute, CategoryAttributeAdmin)
admin_site.register(AttributeValue, AttributeValueAdmin)
admin_site.register(DeletedProduct, DeletedProductAdmin)

# Register improved category system models
admin_site.register(CategoryGender, CategoryGenderAdmin)
admin_site.register(CategoryGroup, CategoryGroupAdmin)
admin_site.register(CategorySubgroup, CategorySubgroupAdmin)

# Register special offers models with the custom admin site
admin_site.register(SpecialOffer, SpecialOfferAdmin)
admin_site.register(SpecialOfferProduct, SpecialOfferProductAdmin) 

# Register Cart and CartItem with the custom admin site
admin_site.register(Cart, CartAdmin)
admin_site.register(CartItem, CartItemAdmin) 