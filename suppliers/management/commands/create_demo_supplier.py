from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from suppliers.models import User, Supplier, Store, SupplierAdmin
from django.db import transaction


class Command(BaseCommand):
    help = 'Create a demo supplier for testing'

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                # Create demo user
                user = User.objects.create_user(
                    username="demosupplier",
                    email="admin@demosupplier.com",
                    password="demo123",
                    first_name="John",
                    last_name="Admin",
                    is_supplier=True,
                    is_active=True
                )

                # Create demo supplier
                supplier = Supplier.objects.create(
                    user=user,
                    name="Demo Supplier Company",
                    email="admin@demosupplier.com",
                    phone="+1234567890",
                    address="123 Business St, New York, NY 10001",
                    description="A demo supplier for testing the platform",
                    is_active=True
                )

                # Create demo store
                store = Store.objects.create(
                    supplier=supplier,
                    name="Demo Main Store",
                    address="123 Business St, New York, NY 10001",
                    is_active=True
                )

                # Create supplier admin
                admin = SupplierAdmin.objects.create(
                    user=user,
                    supplier=supplier,
                    role="admin",
                    is_active=True
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Demo supplier created successfully!\n'
                        f'   Supplier: {supplier.name}\n'
                        f'   Username: {user.username}\n'
                        f'   Email: {user.email}\n'
                        f'   Password: demo123\n'
                        f'   Store: {store.name}\n\n'
                        f'🌐 Access URLs:\n'
                        f'   Landing Page: http://localhost:8000/suppliers/web/\n'
                        f'   Login Page: http://localhost:8000/suppliers/web/login/\n'
                        f'   Dashboard: http://localhost:8000/suppliers/web/dashboard/\n\n'
                        f'📝 Login Credentials:\n'
                        f'   Username: demosupplier\n'
                        f'   Password: demo123\n'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creating demo supplier: {str(e)}')
            )