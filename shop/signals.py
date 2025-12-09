from typing import Iterable

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import Category, CategoryAttribute, AttributeValue, SpecialOfferProduct, Product, SpecialOffer


def _iter_descendant_categories(category: Category) -> Iterable[Category]:
    """Yield all descendant categories for the given category.

    Uses the model's helper method to gather all subcategories recursively.
    """
    # The Category model already provides a recursive method
    for descendant in category.get_all_subcategories():
        yield descendant


def _ensure_child_attribute(parent_attr: CategoryAttribute, child_category: Category) -> CategoryAttribute:
    """Get or create the mirrored attribute on a child category matching the parent's key.

    Also keeps core attribute fields in sync with the parent.
    """
    child_attr, created = CategoryAttribute.objects.get_or_create(
        category=child_category,
        key=parent_attr.key,
        defaults={
            'type': parent_attr.type,
            'required': parent_attr.required,
            'display_order': parent_attr.display_order,
            'label_fa': parent_attr.label_fa,
        },
    )

    # If already existed, update fields to match parent for consistency
    # Only update when there is a difference to avoid unnecessary saves
    if not created:
        fields_to_update = {}
        if child_attr.type != parent_attr.type:
            fields_to_update['type'] = parent_attr.type
        if child_attr.required != parent_attr.required:
            fields_to_update['required'] = parent_attr.required
        if child_attr.display_order != parent_attr.display_order:
            fields_to_update['display_order'] = parent_attr.display_order
        if child_attr.label_fa != parent_attr.label_fa:
            fields_to_update['label_fa'] = parent_attr.label_fa

        if fields_to_update:
            for name, value in fields_to_update.items():
                setattr(child_attr, name, value)
            child_attr.save(update_fields=list(fields_to_update.keys()))

    return child_attr


def _sync_attribute_values(parent_attr: CategoryAttribute, child_attr: CategoryAttribute) -> None:
    """Ensure all values from parent attribute exist on the child attribute with same ordering.

    This is an additive sync; it does not remove extra values on the child.
    """
    parent_values = AttributeValue.objects.filter(attribute=parent_attr)
    for pval in parent_values:
        cval, created = AttributeValue.objects.get_or_create(
            attribute=child_attr,
            value=pval.value,
            defaults={'display_order': pval.display_order},
        )
        if not created and cval.display_order != pval.display_order:
            cval.display_order = pval.display_order
            cval.save(update_fields=['display_order'])


@receiver(post_save, sender=CategoryAttribute)
def propagate_category_attribute_to_children(sender, instance: CategoryAttribute, created, **kwargs):
    """Propagate a parent category attribute to all descendant categories.

    - On create: create the same attribute for all descendants and copy its values.
    - On update: update the fields on descendants and sync values additively.
    """
    parent_category = instance.category
    for child_category in _iter_descendant_categories(parent_category):
        child_attr = _ensure_child_attribute(instance, child_category)
        _sync_attribute_values(instance, child_attr)


@receiver(post_save, sender=AttributeValue)
def propagate_attribute_value_to_children(sender, instance: AttributeValue, created, **kwargs):
    """Propagate a value addition/update from a parent attribute to all descendants' attributes.

    Keeps value records (by value text) present on all child attributes.
    """
    parent_attr = instance.attribute
    parent_category = parent_attr.category

    for child_category in _iter_descendant_categories(parent_category):
        try:
            child_attr = CategoryAttribute.objects.get(category=child_category, key=parent_attr.key)
        except CategoryAttribute.DoesNotExist:
            # Create the child attribute if missing, then sync
            child_attr = _ensure_child_attribute(parent_attr, child_category)

        cval, created_val = AttributeValue.objects.get_or_create(
            attribute=child_attr,
            value=instance.value,
            defaults={'display_order': instance.display_order},
        )
        if not created_val and cval.display_order != instance.display_order:
            cval.display_order = instance.display_order
            cval.save(update_fields=['display_order'])


@receiver(post_delete, sender=AttributeValue)
def delete_attribute_value_from_children(sender, instance: AttributeValue, **kwargs):
    """When a value is removed from a parent attribute, remove it from descendants as well.

    This keeps child attributes' allowed value sets aligned with the parent.
    """
    parent_attr = instance.attribute
    parent_category = parent_attr.category

    for child_category in _iter_descendant_categories(parent_category):
        try:
            child_attr = CategoryAttribute.objects.get(category=child_category, key=parent_attr.key)
        except CategoryAttribute.DoesNotExist:
            continue
        AttributeValue.objects.filter(attribute=child_attr, value=instance.value).delete()


@receiver(post_save, sender=Category)
def inherit_parent_attributes_for_new_category(sender, instance: Category, created, **kwargs):
    """When a new category with a parent is created, inherit all parent's attributes and values.

    This ensures immediate availability of attributes on categories like "ساعت مردانه" or "ساعت زنانه"
    when the parent "ساعت" already defines them.
    """
    if not created or not instance.parent:
        return

    parent_category = instance.parent
    parent_attrs = CategoryAttribute.objects.filter(category=parent_category)
    for parent_attr in parent_attrs:
        child_attr = _ensure_child_attribute(parent_attr, instance)
        _sync_attribute_values(parent_attr, child_attr)


def update_product_special_offer_status(product):
    """Update the is_in_special_offers status for a product based on active offers"""
    now = timezone.now()
    
    # Check if product has any active special offers
    has_active_offers = SpecialOfferProduct.objects.filter(
        product=product,
        offer__enabled=True,
        offer__is_active=True,
        offer__valid_from__lte=now,
        offer__valid_until__gte=now
    ).exists()
    
    # Update the boolean field if it's different
    if product.is_in_special_offers != has_active_offers:
        product.is_in_special_offers = has_active_offers
        product.save(update_fields=['is_in_special_offers'])


@receiver(post_save, sender=SpecialOfferProduct)
def update_product_on_offer_add(sender, instance: SpecialOfferProduct, created, **kwargs):
    """Update product's is_in_special_offers when added to or modified in a special offer"""
    update_product_special_offer_status(instance.product)


@receiver(post_delete, sender=SpecialOfferProduct)
def update_product_on_offer_remove(sender, instance: SpecialOfferProduct, **kwargs):
    """Update product's is_in_special_offers when removed from a special offer"""
    update_product_special_offer_status(instance.product)


@receiver(post_save, sender=SpecialOffer)
def update_products_on_offer_change(sender, instance: SpecialOffer, created, **kwargs):
    """Update all products when a special offer is modified (enabled/disabled, dates changed)"""
    # Get all products in this offer
    products = Product.objects.filter(specialofferproduct__offer=instance)
    
    # Update each product's status
    for product in products:
        update_product_special_offer_status(product)


