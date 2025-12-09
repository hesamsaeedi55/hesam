from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from suppliers.models import SupplierAdmin

class SupplierAuthenticationBackend(ModelBackend):
    """
    Custom authentication backend that allows Customer users to access supplier portal
    if they have a SupplierAdmin record.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Get the default user model (Customer)
        UserModel = get_user_model()
        
        if username is None or password is None:
            return None
        
        try:
            # Try to find user by email
            user = UserModel.objects.get(email=username)
        except UserModel.DoesNotExist:
            return None
        
        # Check password
        if user.check_password(password) and self.user_can_authenticate(user):
            # Check if user has supplier access (either via SupplierAdmin or direct email match)
            try:
                supplier_admin = SupplierAdmin.objects.get(user=user)
                if supplier_admin.is_active:
                    return user
            except SupplierAdmin.DoesNotExist:
                # If no SupplierAdmin record, check if user has a supplier by email
                try:
                    supplier = Supplier.objects.get(email=user.email)
                    if supplier.is_active:
                        return user
                except Supplier.DoesNotExist:
                    pass
        
        return None
    
    def user_can_authenticate(self, user):
        """
        Reject users with is_active=False. Custom user models that don't have
        is_active field are allowed.
        """
        is_active = getattr(user, 'is_active', None)
        return is_active or is_active is None
