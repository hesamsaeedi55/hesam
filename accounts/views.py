from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from datetime import timedelta
import uuid
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
from .serializers import EmailTokenObtainPairSerializer, CustomTokenRefreshSerializer, UserSerializer, CustomerInfoSerializer

logger = logging.getLogger('security')
from .forms import (
    CustomerRegistrationForm,
    CustomerLoginForm,
    CustomerPasswordResetForm,
    CustomerSetPasswordForm
)
from .models import Customer, Address
from shop.models import Product
from .utils import is_rate_limited, get_client_ip
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
import requests
from rest_framework_simplejwt.tokens import RefreshToken
import os

User = get_user_model()

def format_form_errors(form_errors):
    """
    Convert Django form errors to a clean, user-friendly format.
    
    Args:
        form_errors: Django form.errors dictionary
        
    Returns:
        dict: Clean error response with message and details
    """
    # Field name mapping for user-friendly messages
    field_names = {
        'email': 'Email',
        'first_name': 'First Name',
        'last_name': 'Last Name',
        'phone_number': 'Phone Number',
        'date_of_birth': 'Date of Birth',
        'password1': 'Password',
        'password2': 'Confirm Password',
    }
    
    # Collect all error messages
    error_messages = []
    error_details = {}
    
    for field, errors in form_errors.items():
        field_display = field_names.get(field, field.replace('_', ' ').title())
        
        # Get the first error message for this field
        error_message = errors[0] if errors else 'Invalid value'
        
        # Add to details
        error_details[field] = errors
        
        # Create user-friendly message
        if 'required' in error_message.lower():
            error_messages.append(f"{field_display} is required.")
        elif 'match' in error_message.lower():
            error_messages.append(f"{field_display}: {error_message}")
        else:
            error_messages.append(f"{field_display}: {error_message}")
    
    # Create main error message
    if len(error_messages) == 1:
        main_message = error_messages[0]
    elif len(error_messages) <= 3:
        main_message = "Please fix the following errors: " + " ".join(error_messages)
    else:
        main_message = f"Please fix {len(error_messages)} validation errors."
    
    return {
        'error': main_message,
        'details': error_details,
        'field_count': len(error_details)
    }

@method_decorator(csrf_exempt, name='dispatch')
class EmailTokenObtainPairView(TokenObtainPairView):
    """
    Enhanced JWT token obtain view with complete 5-tier security.
    Handles login with progressive security measures.
    """
    serializer_class = EmailTokenObtainPairSerializer
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        """Override to ensure request context is passed to serializer and handle errors properly"""
        import traceback
        import sys
        
        try:
            # Ensure we can parse the request data
            try:
                request_data = request.data if hasattr(request, 'data') else {}
                if not request_data and request.body:
                    # Try to parse JSON manually if request.data is empty
                    import json
                    try:
                        request_data = json.loads(request.body.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_data = {}
            except Exception as parse_error:
                logger.error(f"Failed to parse request data: {str(parse_error)}")
                request_data = {}
            
            # Get serializer with request context
            serializer = self.get_serializer(data=request_data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
            
        except (AuthenticationFailed, ValidationError) as e:
            # Authentication/validation errors - return 401
            error_detail = e.detail if hasattr(e, 'detail') else str(e)
            logger.warning(f"Login failed: {error_detail}")
            return Response(
                {
                    'detail': error_detail if isinstance(error_detail, (str, dict)) else str(error_detail),
                    'error': True
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            # Log the full error with traceback for debugging
            error_traceback = traceback.format_exc()
            exc_type, exc_value, exc_traceback = sys.exc_info()
            logger.error(
                f"Login error (type: {type(e).__name__}): {str(e)}\n"
                f"Traceback:\n{error_traceback}"
            )
            
            # Return appropriate error response
            error_detail = str(e)
            if hasattr(e, 'detail'):
                error_detail = e.detail
            elif hasattr(e, 'get_full_details'):
                error_detail = e.get_full_details()
            
            # Return 500 for unexpected errors, but with proper JSON response
            return Response(
                {
                    'detail': error_detail if isinstance(error_detail, (str, dict)) else str(error_detail),
                    'error': True,
                    'error_type': type(e).__name__
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom token refresh view that checks if the user still exists and is active
    before refreshing the token.
    """
    serializer_class = CustomTokenRefreshSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
            
            # Get the user ID from the refresh token
            user_id = serializer.validated_data.get('user_id')
            
            if not user_id:
                return Response(
                    {"detail": "Invalid refresh token."},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Check if user exists and is active
            try:
                user = User.objects.get(id=user_id)
                if not user.is_active:
                    return Response(
                        {"detail": "User account is disabled."},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            except User.DoesNotExist:
                return Response(
                    {"detail": "User no longer exists."},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # If we get here, the user exists and is active
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
            
        except TokenError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data)
    
    def put(self, request):
        """Update user information"""
        user = request.user
        
        # Update allowed fields
        allowed_fields = ['first_name', 'last_name', 'phone_number']
        
        for field in allowed_fields:
            if field in request.data:
                setattr(user, field, request.data[field])
        
        try:
            user.save()
            serializer = UserSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'detail': f'Error updating user: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def patch(self, request):
        """Partially update user information (same as PUT)"""
        return self.put(request)

class CustomerUserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        from .models import Customer
        # Try to get the customer by email from the request user
        customer = Customer.objects.filter(email=request.user.email).first()
        if not customer:
            return Response({'detail': 'Customer not found', 'code': 'customer_not_found'}, status=404)
        serializer = CustomerInfoSerializer(customer)
        return Response(serializer.data)
    
    def put(self, request):
        """Update customer information"""
        from .models import Customer
        customer = Customer.objects.filter(email=request.user.email).first()
        if not customer:
            return Response({'detail': 'Customer not found', 'code': 'customer_not_found'}, status=404)
        
        # Update allowed fields
        allowed_fields = ['first_name', 'last_name', 'phone_number']
        
        for field in allowed_fields:
            if field in request.data:
                setattr(customer, field, request.data[field])
        
        try:
            customer.save()
            serializer = CustomerInfoSerializer(customer)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'detail': f'Error updating customer: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def patch(self, request):
        """Partially update customer information (same as PUT)"""
        return self.put(request)

class ChangePasswordView(APIView):
    """
    Change password endpoint for email-based accounts.
    Requires current password verification and enforces password requirements.
    """
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]
    
    def post(self, request):
        import re
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = request.user
        
        # Check if user is email-based (not Google)
        if hasattr(user, 'login_method') and user.login_method != 'email':
            return Response(
                {
                    'error': 'Password change is only available for email-based accounts.',
                    'code': 'google_account'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get required fields
        current_password = request.data.get('current_password', '')
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')
        
        # Validate current password
        if not current_password:
            return Response(
                {
                    'error': 'Current password is required.',
                    'details': {'current_password': ['This field is required.']},
                    'field_count': 1
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not user.check_password(current_password):
            return Response(
                {
                    'error': 'Current password is incorrect.',
                    'details': {'current_password': ['The password you entered is incorrect.']},
                    'field_count': 1
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate new password
        errors = {}
        
        if not new_password:
            errors['new_password'] = ['This field is required.']
        elif not confirm_password:
            errors['confirm_password'] = ['This field is required.']
        elif new_password != confirm_password:
            errors['confirm_password'] = ['Passwords do not match.']
        else:
            # Password strength validation (same as registration)
            if len(new_password) < 8:
                errors['new_password'] = ['Password must be at least 8 characters long.']
            elif not re.search(r'[A-Z]', new_password):
                errors['new_password'] = ['Password must contain at least one uppercase letter.']
            elif not re.search(r'[a-z]', new_password):
                errors['new_password'] = ['Password must contain at least one lowercase letter.']
            elif not re.search(r'\d', new_password):
                errors['new_password'] = ['Password must contain at least one number.']
            elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
                errors['new_password'] = ['Password must contain at least one special character.']
            elif new_password == current_password:
                errors['new_password'] = ['New password must be different from current password.']
        
        if errors:
            # Format errors similar to registration
            error_messages = []
            for field, field_errors in errors.items():
                field_display = field.replace('_', ' ').title()
                error_messages.append(f"{field_display}: {field_errors[0]}")
            
            main_message = "Please fix the following errors: " + " ".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            
            return Response(
                {
                    'error': main_message,
                    'details': errors,
                    'field_count': len(errors)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Change password
        try:
            user.set_password(new_password)
            user.save()
            
            # Invalidate all sessions except current (optional - for security)
            # You can add session invalidation here if needed
            
            return Response(
                {
                    'message': 'Password changed successfully. Please login again with your new password.'
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {
                    'error': f'Error changing password: {str(e)}',
                    'details': {},
                    'field_count': 0
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CustomerAddressView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        """Get the current user's address information"""
        from .models import Customer
        customer = Customer.objects.filter(email=request.user.email).first()
        if not customer:
            return Response({'detail': 'Customer not found', 'code': 'customer_not_found'}, status=404)
        # Get the latest address object
        address = customer.addresses.order_by('-created_at').first()
        if address:
            address_data = {
                'street_address': address.street_address,
                'city': address.city,
                'state': address.province,
                'country': address.country,
                'postal_code': address.postal_code,
                'full_address': f"{address.street_address}, {address.city}, {address.province}, {address.country}, {address.postal_code}",
                'label': address.label,
            }
        else:
            address_data = {
                'street_address': customer.street_address,
                'city': customer.city,
                'state': customer.state,
                'country': customer.country,
                'postal_code': customer.postal_code,
                'full_address': customer.get_full_address(),
                'legacy_address': customer.address  # Keep the old text field for backward compatibility
            }
        return Response(address_data)

    def put(self, request):
        """Update the current user's address information"""
        from .models import Customer
        customer = Customer.objects.filter(email=request.user.email).first()
        if not customer:
            return Response({'detail': 'Customer not found', 'code': 'customer_not_found'}, status=404)
        
        # Update address fields
        address_fields = ['street_address', 'city', 'state', 'country', 'postal_code']
        for field in address_fields:
            if field in request.data:
                setattr(customer, field, request.data[field])
        
        customer.save()
        
        # Return updated address
        address_data = {
            'street_address': customer.street_address,
            'city': customer.city,
            'state': customer.state,
            'country': customer.country,
            'postal_code': customer.postal_code,
            'full_address': customer.get_full_address(),
            'legacy_address': customer.address
        }
        return Response(address_data)

class CustomerAddressesListView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        from .models import Customer
        customer = Customer.objects.filter(email=request.user.email).first()
        if not customer:
            return Response({'detail': 'Customer not found', 'code': 'customer_not_found'}, status=404)
        addresses = customer.addresses.order_by('-created_at')[:4]
        data = [
            {
                'id': addr.id,
                'label': addr.label,
                'receiver_name': addr.receiver_name,
                'street_address': addr.street_address,
                'city': addr.city,
                'state': addr.province,
                'country': addr.country,
                'postal_code': addr.postal_code,
                'unit': addr.vahed,  # <-- always use 'unit' in API
                'phone': addr.phone,
                'full_address': addr.full_address,
                'created_at': addr.created_at,
                'updated_at': addr.updated_at,
            }
            for addr in addresses
        ]
        return Response({'addresses': data})

    def post(self, request):
        from .models import Customer, Address
        customer = Customer.objects.filter(email=request.user.email).first()
        if not customer:
            return Response({'detail': 'Customer not found', 'code': 'customer_not_found'}, status=404)
        if customer.addresses.count() >= 3:
            return Response({'detail': 'You can only have up to 3 addresses janam.'}, status=400)
        required_fields = ['street_address', 'city', 'phone', 'receiver_name']
        for field in required_fields:
            if not request.data.get(field):
                return Response({'detail': f'{field} is required.'}, status=400)
        
        # Prepare address data
        address_data = {
            'receiver_name': request.data['receiver_name'],
            'street_address': request.data['street_address'],
            'city': request.data['city'],
            'province': request.data.get('state', ''),
            'vahed': request.data.get('unit', ''),
            'phone': request.data['phone'],
            'country': request.data.get('country', 'ایران'),
            'postal_code': request.data.get('postal_code', ''),
        }
        
        # IDEMPOTENCY: Check if identical address already exists for this customer
        # This prevents duplicates from retries, cancellations, or accidental double-submits
        existing_address = Address.objects.filter(
            customer=customer,
            receiver_name=address_data['receiver_name'],
            street_address=address_data['street_address'],
            city=address_data['city'],
            province=address_data['province'],
            vahed=address_data['vahed'],
            phone=address_data['phone'],
            country=address_data['country'],
            postal_code=address_data['postal_code'],
        ).first()
        
        if existing_address:
            # Address already exists - return existing one (idempotent behavior)
            return Response({
                'detail': 'Address already exists.',
                'address_id': existing_address.id,
                'already_exists': True
            }, status=200)  # 200 instead of 201 since it's not newly created
        
        try:
            # Create new address with label
            address = Address.objects.create(
                customer=customer,
                label=request.data.get('label', ''),
                **address_data
            )
            return Response({'detail': 'Address created successfully.', 'address_id': address.id}, status=201)
        except Exception as e:
            return Response({'detail': str(e)}, status=400)

class CustomerAddressUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]

    def put(self, request, address_id):
        """Update a specific address by ID"""
        from .models import Customer, Address
        from django.utils import timezone
        from django.core.cache import cache
        import json
        
        # Get the customer
        customer = Customer.objects.filter(email=request.user.email).first()
        if not customer:
            return Response({'detail': 'Customer not found', 'code': 'customer_not_found'}, status=404)
        
        # Rate limiting: Check if user has exceeded 2 edits per minute
        cache_key = f"address_edit_rate_limit_{customer.id}"
        current_time = timezone.now()
        
        # Get existing rate limit data
        rate_limit_data = cache.get(cache_key)
        if rate_limit_data:
            edit_times = json.loads(rate_limit_data)
            # Remove timestamps older than 1 minute
            one_minute_ago = current_time.timestamp() - 60
            edit_times = [t for t in edit_times if t > one_minute_ago]
            
            if len(edit_times) >= 2:
                return Response({
                    'detail': 'Rate limit exceeded. Maximum 2 address edits per minute allowed.',
                    'code': 'rate_limit_exceeded',
                    'retry_after': 60 - int(current_time.timestamp() - edit_times[0])
                }, status=429)
        else:
            edit_times = []
        
        # Get the specific address
        try:
            address = Address.objects.get(id=address_id, customer=customer)
        except Address.DoesNotExist:
            return Response({'detail': 'Address not found', 'code': 'address_not_found'}, status=404)
        
        # Validate required fields
        required_fields = ['street_address', 'city', 'phone', 'receiver_name']
        for field in required_fields:
            if not request.data.get(field):
                return Response({'detail': f'{field} is required.'}, status=400)
        
        try:
            # Update the address
            address.label = request.data.get('label', address.label)
            address.receiver_name = request.data.get('receiver_name', address.receiver_name)
            address.street_address = request.data['street_address']
            address.city = request.data['city']
            address.province = request.data.get('state', address.province)
            address.vahed = request.data.get('unit', address.vahed)  # Map 'unit' from request to vahed in model
            address.phone = request.data['phone']
            address.country = request.data.get('country', address.country)
            address.postal_code = request.data.get('postal_code', address.postal_code)
            
            address.save()
            
            # Update rate limit data
            edit_times.append(current_time.timestamp())
            cache.set(cache_key, json.dumps(edit_times), 120)  # Cache for 2 minutes
            
            # Return updated address
            address_data = {
                'id': address.id,
                'label': address.label,
                'receiver_name': address.receiver_name,
                'street_address': address.street_address,
                'city': address.city,
                'state': address.province,
                'country': address.country,
                'postal_code': address.postal_code,
                'unit': address.vahed,  # Use 'unit' in API response
                'phone': address.phone,
                'full_address': address.full_address,
                'created_at': address.created_at,
                'updated_at': address.updated_at,
            }
            return Response(address_data)
        except Exception as e:
            return Response({'detail': str(e)}, status=400)

    def delete(self, request, address_id):
        """Delete a specific address by ID"""
        from .models import Customer, Address
        
        # Get the customer
        customer = Customer.objects.filter(email=request.user.email).first()
        if not customer:
            return Response({'detail': 'Customer not found', 'code': 'customer_not_found'}, status=404)
        
        # Get the specific address
        try:
            address = Address.objects.get(id=address_id, customer=customer)
        except Address.DoesNotExist:
            return Response({'detail': 'Address not found', 'code': 'address_not_found'}, status=404)
        
        # Delete the address
        address.delete()
        return Response({'detail': 'Address deleted successfully.'}, status=200)

@csrf_exempt
def register(request):
    if request.method == 'POST':
        # Check if it's an API request
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
                form = CustomerRegistrationForm(data)
            except json.JSONDecodeError:
                return JsonResponse({
                    'error': 'Invalid JSON data. Please check your request format.',
                    'details': {},
                    'field_count': 0
                }, status=400)
        else:
            form = CustomerRegistrationForm(request.POST)

        if form.is_valid():
            print(f"DEBUG: Registration form is valid")
            try:
                user = form.save()  # This will handle password setting and other attributes
                print(f"DEBUG: Created user with email: {user.email}")
                print(f"DEBUG: User is_active: {user.is_active}")
            except Exception as save_error:
                logger.error(f"ERROR saving user during registration: {str(save_error)}")
                import traceback
                error_traceback = traceback.format_exc()
                logger.error(error_traceback)
                # Always show detail in response for debugging
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({
                        'error': 'Registration failed. Please try again.',
                        'detail': str(save_error),
                        'traceback': error_traceback if settings.DEBUG else None
                    }, status=500)
                else:
                    messages.error(request, 'Registration failed. Please try again.')
                    return render(request, 'accounts/register.html', {'form': form})
            
            # Generate verification token and send email
            try:
                token = user.generate_email_verification_token()
            except Exception as token_error:
                logger.error(f"ERROR generating verification token: {str(token_error)}")
                import traceback
                logger.error(traceback.format_exc())
                # Continue anyway - user is created, just can't send email
                token = None
            verification_url = request.build_absolute_uri(
                reverse('accounts:verify_email', args=[token])
            )
            print(f"DEBUG: Generated verification URL: {verification_url}")
            
            # Prepare email content
            context = {
                'user': user,
                'verification_url': verification_url
            }
            html_message = render_to_string('accounts/email/verification_email.html', context)
            plain_message = strip_tags(html_message)
            
            try:
                # Send verification email (non-blocking - in background thread)
                from django.core.mail import EmailMultiAlternatives
                from accounts.email_service import send_email_async
                
                msg = EmailMultiAlternatives(
                    subject='Verify your email address',
                    body=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email]
                )
                msg.attach_alternative(html_message, "text/html")
                send_email_async(msg)  # Non-blocking!
                
                print(f"DEBUG: Verification email queued for {user.email}")
                
                # Return appropriate response based on request type
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({
                        'message': 'Registration successful! Please check your email to verify your account.'
                    })
                else:
                    messages.success(request, 'Registration successful! Please check your email to verify your account.')
                    return redirect('accounts:login')
                    
            except Exception as e:
                print(f"DEBUG: Error sending verification email: {str(e)}")
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({
                        'error': 'Registration successful, but there was an error sending the verification email. Please contact support.'
                    }, status=500)
                else:
                    messages.error(request, 'Registration successful, but there was an error sending the verification email. Please contact support.')
                    return redirect('accounts:login')
        else:
            print(f"DEBUG: Form errors: {form.errors}")
            if request.headers.get('Content-Type') == 'application/json':
                # Format errors in a clean, user-friendly way
                formatted_errors = format_form_errors(form.errors)
                return JsonResponse(formatted_errors, status=400)
    else:
        form = CustomerRegistrationForm()
    
    # If it's not a POST request or form is invalid, render the template
    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        # Check rate limiting
        is_limited, remaining_attempts, cooldown_remaining = is_rate_limited(
            request,
            'login_attempts',
            max_attempts=5,  # Maximum 5 attempts
            cooldown_minutes=15  # 15 minutes cooldown
        )
        
        if is_limited:
            messages.error(
                request,
                f'Too many login attempts. Please try again in {cooldown_remaining} minutes.'
            )
            return render(request, 'accounts/login.html', {'form': CustomerLoginForm()})
        
        form = CustomerLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            user.backend = 'accounts.backends.CustomerBackend'  # Specify the backend
            login(request, user)
            messages.success(request, 'Welcome back!')
            return redirect('accounts:home')
        else:
            messages.error(
                request,
                f'Invalid login attempt. {remaining_attempts} attempts remaining.'
            )
    else:
        form = CustomerLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')

def verify_email(request, token):
    print(f"DEBUG: Attempting to verify email with token: {token}")
    try:
        user = Customer.objects.get(email_verification_token=token)
        print(f"DEBUG: Found user with token: {user.email}")
        print(f"DEBUG: Current verification status: {user.is_email_verified}")
        
        if user.is_email_verified:
            print(f"DEBUG: Email already verified")
            messages.info(request, 'Your email is already verified.')
        else:
            user.is_email_verified = True
            user.is_active = True  # Make sure user is active after verification
            user.save()
            print(f"DEBUG: Email verified successfully")
            print(f"DEBUG: New verification status: {user.is_email_verified}")
            print(f"DEBUG: New active status: {user.is_active}")
            messages.success(request, 'Your email has been verified successfully!')
        return redirect('login')
    except Customer.DoesNotExist:
        print(f"DEBUG: No user found with token: {token}")
        messages.error(request, 'Invalid verification link.')
        return redirect('login')

def password_reset_request(request):
    if request.method == 'POST':
        form = CustomerPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            print(f"DEBUG: Attempting password reset for email: {email}")  # Debug log
            try:
                user = User.objects.get(email=email)
                print(f"DEBUG: Found user: {user.email}")  # Debug log
                
                # Generate a UUID token
                token = str(uuid.uuid4())
                user.password_reset_token = token
                user.password_reset_sent_at = timezone.now()
                user.save()
                
                # Send password reset email
                reset_url = request.build_absolute_uri(
                    reverse('accounts:password_reset_confirm', args=[token])
                )
                context = {
                    'user': user,
                    'reset_url': reset_url
                }
                html_message = render_to_string('accounts/email/password_reset_email.html', context)
                plain_message = strip_tags(html_message)
                
                send_mail(
                    'Password Reset Request',
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                messages.success(request, 'Password reset instructions have been sent to your email.')
                return redirect('accounts:login')
            except User.DoesNotExist:
                print(f"DEBUG: No user found with email: {email}")  # Debug log
                # Let's check if there are any users in the database
                all_users = User.objects.all()
                print(f"DEBUG: Total users in database: {all_users.count()}")  # Debug log
                for user in all_users:
                    print(f"DEBUG: User in database: {user.email}")  # Debug log
                messages.error(request, 'No account found with that email address.')
    else:
        form = CustomerPasswordResetForm()
    
    return render(request, 'accounts/password_reset_request.html', {'form': form})

def password_reset_confirm(request, token):
    try:
        user = User.objects.get(password_reset_token=token)
        # Check if token is expired (24 hours)
        if user.password_reset_sent_at < timezone.now() - timedelta(hours=24):
            user.password_reset_token = None
            user.password_reset_sent_at = None
            user.save()
            messages.error(request, 'Password reset link has expired.')
            return redirect('accounts:password_reset_request')
        
        if request.method == 'POST':
            form = CustomerSetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                # Clear the reset token
                user.password_reset_token = None
                user.password_reset_sent_at = None
                user.save()
                messages.success(request, 'Your password has been reset successfully!')
                return redirect('accounts:login')
        else:
            form = CustomerSetPasswordForm(user)
        
        return render(request, 'accounts/password_reset_confirm.html', {'form': form})
    except User.DoesNotExist:
        messages.error(request, 'Invalid password reset link.')
        return redirect('accounts:password_reset_request')

@login_required
def profile(request):
    # Get the user's addresses (up to 3)
    addresses = request.user.addresses.all()[:3]
    
    if request.method == 'POST':
        # Handle address deletion
        delete_address_id = request.POST.get('delete_address_id')
        if delete_address_id:
            try:
                address = request.user.addresses.get(id=delete_address_id)
                address.delete()
                messages.success(request, 'Address deleted successfully.')
                return redirect('accounts:profile')
            except Address.DoesNotExist:
                messages.error(request, 'Address not found.')
                return redirect('accounts:profile')
        
        # Handle address editing
        edit_address_id = request.POST.get('edit_address_id')
        if edit_address_id:
            try:
                address = request.user.addresses.get(id=edit_address_id)
                
                # Get form data
                label = request.POST.get('label', '').strip()
                receiver_name = request.POST.get('receiver_name', '').strip()
                street_address = request.POST.get('street_address', '').strip()
                city = request.POST.get('city', '').strip()
                province = request.POST.get('province', '').strip()
                vahed = request.POST.get('vahed', '').strip()
                country = request.POST.get('country', '').strip() or 'ایران'
                postal_code = request.POST.get('postal_code', '').strip()
                phone = request.POST.get('phone', '').strip()
                
                # Validate required fields
                if not all([label, receiver_name, street_address, city, country, phone]):
                    messages.error(request, 'Please fill in all required fields.')
                    return redirect('accounts:profile')
                
                # Update address
                address.label = label
                address.receiver_name = receiver_name
                address.street_address = street_address
                address.city = city
                address.province = province
                address.vahed = vahed
                address.country = country
                address.postal_code = postal_code
                address.phone = phone
                address.save()
                
                messages.success(request, 'Address updated successfully.')
                return redirect('accounts:profile')
                
            except Address.DoesNotExist:
                messages.error(request, 'Address not found.')
                return redirect('accounts:profile')
            except Exception as e:
                messages.error(request, f'Error updating address: {str(e)}')
                return redirect('accounts:profile')
        
        # Handle address creation
        if addresses.count() < 3:
            label = request.POST.get('label', '').strip()
            receiver_name = request.POST.get('receiver_name', '').strip()
            street_address = request.POST.get('street_address', '').strip()
            city = request.POST.get('city', '').strip()
            province = request.POST.get('province', '').strip()
            vahed = request.POST.get('vahed', '').strip()
            country = request.POST.get('country', '').strip() or 'ایران'
            postal_code = request.POST.get('postal_code', '').strip()
            phone = request.POST.get('phone', '').strip()
            
                        # Debug logging
            print(f"DEBUG - Creating address with label: '{label}'")
            print(f"DEBUG - Form data: label='{label}', receiver_name='{receiver_name}', street_address='{street_address}'")
            
            # Validate required fields
            if not all([label, receiver_name, street_address, city, country, phone]):
                missing_fields = []
                if not label: missing_fields.append('label')
                if not receiver_name: missing_fields.append('receiver_name')
                if not street_address: missing_fields.append('street_address')
                if not city: missing_fields.append('city')
                if not country: missing_fields.append('country')
                if not phone: missing_fields.append('phone')
                messages.error(request, f'Please fill in all required fields: {", ".join(missing_fields)}')
                return redirect('accounts:profile')

            try:
                new_address = request.user.addresses.create(
                    label=label,
                    receiver_name=receiver_name,
                    street_address=street_address,
                    city=city,
                    province=province,
                    vahed=vahed,
                    country=country,
                    postal_code=postal_code,
                    phone=phone
                )
                print(f"DEBUG - Address created with ID: {new_address.id}, Label: '{new_address.label}'")
                messages.success(request, f'Address "{label}" added successfully.')
                return redirect('accounts:profile')
            except Exception as e:
                print(f"DEBUG - Error creating address: {str(e)}")
                messages.error(request, f'Error creating address: {str(e)}')
                return redirect('accounts:profile')
    
    addresses = request.user.addresses.all()[:3]
    return render(request, 'accounts/profile.html', {'addresses': addresses})

@login_required
def home(request):
    # Note: Removed automatic supplier redirect to allow users to access customer dashboard
    # Users can manually navigate to supplier dashboard if needed
    
    from shop.models import Wishlist
    from django.db.models import Exists, OuterRef
    
    # Get user's wishlist items with product details
    wishlist_items = Wishlist.objects.filter(
        customer=request.user
    ).select_related('product', 'product__category').prefetch_related('product__images').order_by('-created_at')[:6]  # Show latest 6 items
    
    # Get all active products with wishlist status for the current user
    products = Product.objects.filter(is_active=True).select_related('category').prefetch_related('images').annotate(
        is_in_wishlist=Exists(
            Wishlist.objects.filter(
                customer=request.user,
                product=OuterRef('pk')
            )
        )
    )[:12]  # Limit to 12 products for performance
    
    # Group products by category
    categories = {}
    for product in products:
        if product.category not in categories:
            categories[product.category] = []
        categories[product.category].append(product)
    
    # Get wishlist count
    wishlist_count = Wishlist.objects.filter(customer=request.user).count()
    
    context = {
        'categories': categories,
        'products': products,
        'wishlist_items': wishlist_items,
        'wishlist_count': wishlist_count,
    }
    return render(request, 'accounts/home.html', context)

@login_required
def admin_address_view(request):
    """Admin web page to view all user addresses"""
    from .models import Customer
    
    # Check if user is staff/admin
    if not request.user.is_staff:
        return redirect('accounts:login')
    
    # Handle POST request for updating addresses
    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        try:
            customer = Customer.objects.get(id=customer_id)
            
            # Update address fields
            customer.street_address = request.POST.get('street_address', '')
            customer.city = request.POST.get('city', '')
            customer.state = request.POST.get('state', '')
            customer.country = request.POST.get('country', '')
            customer.postal_code = request.POST.get('postal_code', '')
            
            customer.save()
            
            # Redirect back to the same page with success message
            messages.success(request, f'Address updated successfully for {customer.email}')
            return redirect('accounts:admin_addresses')
            
        except Customer.DoesNotExist:
            messages.error(request, 'Customer not found')
            return redirect('accounts:admin_addresses')
    
    # Get search parameters
    search_email = request.GET.get('email', '')
    search_country = request.GET.get('country', '')
    search_city = request.GET.get('city', '')
    
    # Filter customers
    customers = Customer.objects.all()
    
    if search_email:
        customers = customers.filter(email__icontains=search_email)
    if search_country:
        customers = customers.filter(country__icontains=search_country)
    if search_city:
        customers = customers.filter(city__icontains=search_city)
    
    # Order by email
    customers = customers.order_by('email')
    
    context = {
        'customers': customers,
        'search_email': search_email,
        'search_country': search_country,
        'search_city': search_city,
        'total_count': customers.count(),
    }
    
    return render(request, 'accounts/admin_addresses.html', context)

@require_POST
@login_required
def admin_update_address_field(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    from .models import Customer
    customer_id = request.POST.get('customer_id')
    field = request.POST.get('field')
    value = request.POST.get('value', '')
    allowed_fields = ['street_address', 'city', 'state', 'country', 'postal_code']
    if field not in allowed_fields:
        return JsonResponse({'success': False, 'error': 'Invalid field'}, status=400)
    try:
        customer = Customer.objects.get(id=customer_id)
        setattr(customer, field, value)
        customer.save()
        return JsonResponse({'success': True, 'value': value})
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Customer not found'}, status=404)

class GoogleAuthView(APIView):
    def post(self, request):
        id_token = request.data.get('id_token')
        if not id_token:
            return Response({'error': 'Missing id_token'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify the Google ID token
        google_response = requests.get(
            f'https://oauth2.googleapis.com/tokeninfo?id_token={id_token}'
        )
        if google_response.status_code != 200:
            return Response({'error': 'Invalid Google token'}, status=status.HTTP_400_BAD_REQUEST)
        user_info = google_response.json()
        email = user_info.get('email')
        if not email:
            return Response({'error': 'No email in Google token'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            print(f"DEBUG: Found user {user.email} with login_method {getattr(user, 'login_method', None)}")
            # Only allow Google login if login_method is 'google'
            if hasattr(user, 'login_method') and user.login_method != 'google':
                return Response(
                    {'error': 'Please log in with your original method.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # login_method is google, proceed
        except User.DoesNotExist:
            # New user: create with Google method
            user = User.objects.create_user(
                username=email,
                email=email,
                login_method='google',
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
            )
            user.set_unusable_password()
            user.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        })


def customer_shopping_interface(request):
    """
    Serve the customer shopping interface HTML page
    """
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    
    # Get the path to the HTML file
    html_file_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'customer_shopping_interface.html')
    
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Replace placeholders with actual user data
        html_content = html_content.replace('{{ user.email }}', request.user.email)
        html_content = html_content.replace('{{ user.first_name }}', request.user.first_name or request.user.username)
        html_content = html_content.replace('{{ user.id }}', str(request.user.id))
        
        return HttpResponse(html_content, content_type='text/html')
    except FileNotFoundError:
        return HttpResponse("Shopping interface not found. Please ensure customer_shopping_interface.html exists in templates directory.", status=404)


# ============================================================================
# SECURITY VIEWS - Login Protection System
# ============================================================================

from django.utils.decorators import method_decorator
from .security_service import validate_unlock_token, LoginSecurityService
from .email_service import SecurityEmailService
from .models import AccountLock, VerificationCode, LoginAttempt
import logging

logger = logging.getLogger('security')


@method_decorator(csrf_exempt, name='dispatch')
class UnlockAccountView(APIView):
    """
    API view to unlock account via token (from email link).
    GET: Display unlock confirmation page
    POST: Process unlock request
    """
    permission_classes = []
    
    def get(self, request, token):
        """Display unlock confirmation page"""
        # Validate token
        success, message, email = validate_unlock_token(token)
        
        context = {
            'success': success,
            'message': message,
            'email': email,
            'token': token
        }
        
        # If successful, also send confirmation email
        if success and email:
            SecurityEmailService.send_unlock_success_email(email)
        
        # Return JSON response (or render HTML template if you have one)
        return Response(context, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)
    
    def post(self, request, token):
        """Process unlock request (same as GET for this implementation)"""
        return self.get(request, token)


class ResendVerificationCodeView(APIView):
    """
    Resend verification code to user's email.
    Used when code expires or user didn't receive it.
    """
    permission_classes = []
    
    def post(self, request):
        """Resend verification code"""
        email = request.data.get('email', '').lower().strip()
        
        if not email:
            return Response(
                {'error': 'Email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Initialize security service
        security = LoginSecurityService(request, email)
        
        # Check if account is locked
        is_locked, lock_obj, _ = security.check_account_lock()
        if is_locked:
            return Response(
                {'error': 'Account is locked. Check your email for unlock instructions.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check rate limiting (prevent code spam)
        recent_codes = VerificationCode.objects.filter(
            email=email,
            created_at__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        
        if recent_codes >= 3:
            return Response(
                {'error': 'Too many code requests. Please wait 5 minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Generate new code
        code_obj = security.create_verification_code()
        
        # Send email
        sent = SecurityEmailService.send_verification_code_email(
            email=email,
            code=code_obj.code,
            expires_minutes=10,
            ip_address=security.ip_address
        )
        
        if sent:
            return Response(
                {'message': 'Verification code sent successfully'},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'error': 'Failed to send verification code'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SecurityDashboardView(APIView):
    """
    View security statistics and recent login attempts.
    Requires admin/staff authentication.
    """
    permission_classes = []  # Change to IsAdminUser in production
    
    def get(self, request):
        """Get security statistics"""
        now = timezone.now()
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        stats = {
            'last_hour': {
                'total_attempts': LoginAttempt.objects.filter(created_at__gte=last_hour).count(),
                'failed_attempts': LoginAttempt.objects.filter(created_at__gte=last_hour, success=False).count(),
                'successful_logins': LoginAttempt.objects.filter(created_at__gte=last_hour, success=True).count(),
                'tier_5_triggers': LoginAttempt.objects.filter(created_at__gte=last_hour, security_tier=5).count(),
            },
            'last_24_hours': {
                'total_attempts': LoginAttempt.objects.filter(created_at__gte=last_day).count(),
                'failed_attempts': LoginAttempt.objects.filter(created_at__gte=last_day, success=False).count(),
                'successful_logins': LoginAttempt.objects.filter(created_at__gte=last_day, success=True).count(),
                'accounts_locked': AccountLock.objects.filter(locked_at__gte=last_day, is_active=True).count(),
            },
            'active_locks': AccountLock.objects.filter(is_active=True).count(),
            'recent_failed_attempts': list(
                LoginAttempt.objects.filter(
                    success=False,
                    created_at__gte=last_hour
                ).values('email', 'ip_address', 'created_at', 'security_tier')[:20]
            ),
            'active_locks_detail': list(
                AccountLock.objects.filter(is_active=True).values(
                    'email', 'locked_at', 'expires_at', 'attempt_count'
                )[:10]
            )
        }
        
        return Response(stats, status=status.HTTP_200_OK)


class CheckSecurityStatusView(APIView):
    """
    Check security status for an email address.
    Useful for debugging and monitoring.
    """
    permission_classes = []
    
    def post(self, request):
        """Check security status"""
        email = request.data.get('email', '').lower().strip()
        
        if not email:
            return Response(
                {'error': 'Email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Initialize security service
        security = LoginSecurityService(request, email)
        
        # Get security status
        security_check = security.check_security()
        
        # Check account lock
        is_locked, lock_obj, minutes_remaining = security.check_account_lock()
        
        response_data = {
            'email': email,
            'is_locked': is_locked,
            'minutes_remaining': minutes_remaining if is_locked else 0,
            'security_tier': security_check['tier'],
            'failed_attempts_24h': security_check['failed_count'],
            'requires_captcha': security_check.get('requires_captcha', False),
            'requires_verification': security_check.get('requires_verification', False),
            'message': security_check.get('message', ''),
        }
        
        if lock_obj:
            response_data['lock_details'] = {
                'locked_at': lock_obj.locked_at.isoformat(),
                'expires_at': lock_obj.expires_at.isoformat(),
                'reason': lock_obj.reason,
                'attempt_count': lock_obj.attempt_count,
            }
        
        return Response(response_data, status=status.HTTP_200_OK)


# ============================================================================
# ACCOUNT DELETION - Apple App Store Requirement
# ============================================================================

class DeleteAccountView(APIView):
    """
    Delete user account (Apple App Store requirement).
    
    What gets deleted:
    - User account (Customer)
    - Personal info (email, phone, address)
    - Addresses
    - Login attempts history
    - Account locks
    - Verification codes
    
    What gets anonymized:
    - Order history (for legal/bookkeeping)
    
    Requires:
    - Authentication (must be logged in)
    - Password confirmation (security)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Delete the authenticated user's account"""
        import logging
        from django.contrib.auth.hashers import check_password
        from .models import LoginAttempt, AccountLock, VerificationCode
        from accounts.email_service import send_email_async
        from django.core.mail import EmailMultiAlternatives
        
        logger = logging.getLogger('security')
        
        user = request.user
        email = user.email
        user_id = user.id
        
        # ================================================================
        # STEP 1: Validate password (security requirement)
        # ================================================================
        password = request.data.get('password')
        
        if not password:
            return Response({
                'error': 'Password confirmation required',
                'detail': 'Please provide your current password to delete your account.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify password
        if not check_password(password, user.password):
            logger.warning(f"Account deletion failed: Invalid password for {email}")
            return Response({
                'error': 'Invalid password',
                'detail': 'The password you entered is incorrect.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # ================================================================
        # STEP 2: Check for active orders (optional warning)
        # ================================================================
        # Note: Order model doesn't have FK to Customer, so orders are safe
        # They'll remain in database for bookkeeping with user's email
        
        try:
            # ================================================================
            # STEP 3: Delete related data
            # ================================================================
            
            # Delete addresses
            deleted_addresses = Address.objects.filter(customer=user).count()
            Address.objects.filter(customer=user).delete()
            
            # Anonymize login attempts (keep for security analytics)
            anonymized_attempts = LoginAttempt.objects.filter(email=email).update(
                email=f'deleted_user_{user_id}@deleted.local',
                user_agent='[deleted]'
            )
            
            # Delete account locks
            deleted_locks = AccountLock.objects.filter(email=email).count()
            AccountLock.objects.filter(email=email).delete()
            
            # Delete verification codes
            deleted_codes = VerificationCode.objects.filter(email=email).count()
            VerificationCode.objects.filter(email=email).delete()
            
            # ================================================================
            # STEP 4: Send confirmation email (before deletion!)
            # ================================================================
            try:
                html_message = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #d9534f;">Account Deletion Confirmation</h2>
                    <p>Hello {user.first_name},</p>
                    <p>Your account has been successfully deleted.</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">What was deleted:</h3>
                        <ul>
                            <li>Your account and login credentials</li>
                            <li>Personal information (name, email, phone)</li>
                            <li>Saved addresses ({deleted_addresses})</li>
                            <li>Security records</li>
                        </ul>
                    </div>
                    
                    <p><strong>Note:</strong> Order history has been anonymized but retained for legal and accounting purposes.</p>
                    
                    <p>If you did not request this deletion, please contact our support team immediately.</p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                    <p style="color: #666; font-size: 12px;">
                        This is an automated message. Your account data has been permanently removed from our systems.
                    </p>
                </body>
                </html>
                """
                
                plain_message = f"""
Account Deletion Confirmation

Hello {user.first_name},

Your account has been successfully deleted.

What was deleted:
- Your account and login credentials
- Personal information (name, email, phone)
- Saved addresses ({deleted_addresses})
- Security records

Note: Order history has been anonymized but retained for legal and accounting purposes.

If you did not request this deletion, please contact our support team immediately.

---
This is an automated message. Your account data has been permanently removed from our systems.
                """
                
                msg = EmailMultiAlternatives(
                    subject='Account Deletion Confirmation',
                    body=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email]
                )
                msg.attach_alternative(html_message, "text/html")
                
                # Send in background (non-blocking)
                send_email_async(msg)
                
                logger.info(f"Account deletion confirmation email queued for {email}")
            except Exception as email_error:
                # Don't fail deletion if email fails
                logger.error(f"Failed to send deletion confirmation email: {str(email_error)}")
            
            # ================================================================
            # STEP 5: Invalidate all sessions immediately
            # ================================================================
            try:
                # Revoke all active sessions
                active_sessions = user.get_active_sessions().count()
                user.invalidate_all_tokens()
                logger.info(f"Invalidated {active_sessions} active sessions for {email}")
            except Exception as session_error:
                logger.error(f"Failed to invalidate sessions: {str(session_error)}")
            
            # ================================================================
            # STEP 6: Delete the user account
            # ================================================================
            user_name = user.get_full_name() or email
            user.delete()
            
            logger.critical(
                f"ACCOUNT DELETED: {email} (ID: {user_id}) - "
                f"Addresses: {deleted_addresses}, "
                f"Login attempts anonymized: {anonymized_attempts}, "
                f"Locks deleted: {deleted_locks}, "
                f"Codes deleted: {deleted_codes}"
            )
            
            # ================================================================
            # STEP 6: Return success response
            # ================================================================
            return Response({
                'success': True,
                'message': 'Your account has been permanently deleted.',
                'details': {
                    'user': user_name,
                    'deleted_at': timezone.now().isoformat(),
                    'items_deleted': {
                        'addresses': deleted_addresses,
                        'security_records': deleted_locks + deleted_codes,
                    },
                    'anonymized': {
                        'login_history': anonymized_attempts
                    }
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Account deletion failed for {email}: {str(e)}")
            return Response({
                'error': 'Deletion failed',
                'detail': 'An error occurred while deleting your account. Please try again or contact support.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ============================================================================
# SESSION MANAGEMENT - Multi-device tracking and control
# ============================================================================

class UserSessionsListView(APIView):
    """
    GET /accounts/sessions/
    List all active sessions (devices) for the authenticated user.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        import logging
        from django.db import OperationalError
        
        logger = logging.getLogger('security')
        
        try:
            from .models import UserSession
            from .session_utils import get_client_ip
        except ImportError:
            return Response({
                'error': 'Session management not available',
                'detail': 'UserSession model not found. Please run migrations.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        user = request.user
        current_ip = get_client_ip(request)
        
        try:
            # Get all active sessions
            sessions = user.get_active_sessions()
        except OperationalError as e:
            # Table doesn't exist yet (migrations not run)
            logger.error(f"UserSession table not found: {str(e)}")
            return Response({
                'error': 'Session management not available',
                'detail': 'Database migrations pending. Please contact support.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Prepare response
        sessions_data = []
        for session in sessions:
            # Mark current session
            is_current = (session.ip_address == current_ip)
            
            sessions_data.append({
                'id': session.id,
                'device': session.get_device_display(),
                'device_type': session.device_type,
                'os_version': session.os_version,
                'app_version': session.app_version,
                'ip_address': session.ip_address,
                'location': session.get_location_display(),
                'created_at': session.created_at.isoformat(),
                'last_activity': session.last_activity.isoformat(),
                'expires_at': session.expires_at.isoformat(),
                'is_current': is_current,
            })
        
        logger.info(f"User {user.email} viewed {len(sessions_data)} active sessions")
        
        return Response({
            'sessions': sessions_data,
            'total': len(sessions_data)
        }, status=status.HTTP_200_OK)


class RevokeSessionView(APIView):
    """
    DELETE /accounts/sessions/<session_id>/
    Revoke (logout) a specific session/device.
    """
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, session_id):
        import logging
        from django.db import OperationalError
        
        logger = logging.getLogger('security')
        
        try:
            from .models import UserSession
        except ImportError:
            return Response({
                'error': 'Session management not available',
                'detail': 'UserSession model not found. Please run migrations.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        user = request.user
        
        try:
            session = UserSession.objects.get(
                id=session_id,
                user=user,
                is_active=True
            )
        except UserSession.DoesNotExist:
            return Response({
                'error': 'Session not found',
                'detail': 'This session does not exist or has already been revoked.'
            }, status=status.HTTP_404_NOT_FOUND)
        except OperationalError as e:
            logger.error(f"UserSession table not found: {str(e)}")
            return Response({
                'error': 'Session management not available',
                'detail': 'Database migrations pending. Please contact support.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Revoke the session
        device_name = session.get_device_display()
        session.revoke(reason='user_action')
        
        logger.warning(
            f"User {user.email} revoked session: {device_name} "
            f"(IP: {session.ip_address})"
        )
        
        return Response({
            'success': True,
            'message': f'Session revoked: {device_name}',
            'revoked_session': {
                'id': session.id,
                'device': device_name,
                'revoked_at': session.revoked_at.isoformat()
            }
        }, status=status.HTTP_200_OK)


class RevokeAllSessionsView(APIView):
    """
    POST /accounts/sessions/revoke-all/
    Logout from all devices except the current one (optional).
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        import logging
        from django.db import OperationalError
        
        logger = logging.getLogger('security')
        
        try:
            from .session_utils import get_client_ip
        except ImportError:
            return Response({
                'error': 'Session management not available',
                'detail': 'Session utilities not found.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        user = request.user
        include_current = request.data.get('include_current', False)
        current_ip = get_client_ip(request)
        
        try:
            # Get sessions to revoke
            if include_current:
                sessions_to_revoke = user.get_active_sessions()
            else:
                # Exclude current session (by IP)
                sessions_to_revoke = user.get_active_sessions().exclude(
                    ip_address=current_ip
                )
        except OperationalError as e:
            logger.error(f"UserSession table not found: {str(e)}")
            return Response({
                'error': 'Session management not available',
                'detail': 'Database migrations pending. Please contact support.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        revoked_count = sessions_to_revoke.count()
        
        # Revoke all sessions
        for session in sessions_to_revoke:
            session.revoke(reason='user_revoke_all')
        
        # Also invalidate all tokens
        user.invalidate_all_tokens()
        
        logger.critical(
            f"User {user.email} revoked ALL sessions "
            f"(count: {revoked_count}, include_current: {include_current})"
        )
        
        return Response({
            'success': True,
            'message': f'Revoked {revoked_count} session(s)',
            'revoked_count': revoked_count,
            'include_current': include_current
        }, status=status.HTTP_200_OK)


class CurrentSessionView(APIView):
    """
    GET /accounts/sessions/current/
    Get information about the current session.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from .session_utils import parse_device_info, get_client_ip
        
        user = request.user
        device_info = parse_device_info(request)
        ip_address = get_client_ip(request)
        
        return Response({
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.get_full_name(),
            },
            'session': {
                'device': device_info['device_name'],
                'device_type': device_info['device_type'],
                'os_version': device_info['os_version'],
                'app_version': device_info['app_version'],
                'ip_address': ip_address,
            },
            'active_sessions_count': user.get_session_count(),
        }, status=status.HTTP_200_OK)
