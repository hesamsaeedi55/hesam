from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import Supplier, Store, SupplierAdmin, SupplierInvitation
from suppliers.models import User  # Import the User model directly from suppliers app

class SupplierRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields readonly
        readonly_fields = ['username', 'email', 'first_name', 'last_name']
        for field in readonly_fields:
            if field in self.fields:
                self.fields[field].widget.attrs['readonly'] = True
                self.fields[field].widget.attrs['class'] = 'readonly-field'
                self.fields[field].help_text = "This field is pre-filled from your invitation."
        
        # Focus on password fields
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs['autofocus'] = True

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        # Note: is_supplier_admin is a property, not a field
        # The SupplierAdmin record will be created in the view
        if commit:
            user.save()
        return user

class SupplierLoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Username or Email',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your username or email'})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter your password'})
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            # Try to get user by username or email
            try:
                # First try to get by username
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                try:
                    # If not found by username, try email
                    user = User.objects.get(email=username)
                except User.DoesNotExist:
                    raise forms.ValidationError("Invalid username or email")
                except User.MultipleObjectsReturned:
                    # If multiple users found with same email, get the first one
                    users = User.objects.filter(email=username)
                    user = users[0]  # Take the first user
            except User.MultipleObjectsReturned:
                # If multiple users found with same username, get the first one
                users = User.objects.filter(username=username)
                user = users[0]  # Take the first user

            if not user.check_password(password):
                raise forms.ValidationError("Invalid password")

            # Allow superusers and users with supplier access
            has_supplier_access = False
            if user.is_superuser:
                has_supplier_access = True
            else:
                # Check if user has a supplier record by email
                try:
                    from suppliers.models import Supplier
                    supplier = Supplier.objects.get(email=user.email)
                    if supplier.is_active:
                        has_supplier_access = True
                except Supplier.DoesNotExist:
                    pass
            
            if not has_supplier_access:
                raise forms.ValidationError("This account is not authorized as a supplier")

            self.user_cache = user

        return self.cleaned_data 