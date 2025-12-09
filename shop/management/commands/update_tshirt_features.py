from django.core.management.base import BaseCommand
from shop.models import Category, CategoryAttribute, AttributeValue


class Command(BaseCommand):
    help = "Populate 'feature' attribute for تی‌شرت categories with provided Persian values"

    FEATURE_KEY = "feature"
    FEATURE_LABEL_FA = "ویژگی‌ خاص"

    FEATURE_VALUES = [
        "نرم",
        "لطیف",
        "سبک",
        "خنک",
        "کشی",
        "ضخیم",
        "نازک",
        "زبر",
        "کرکی",
        "اسلاپ (بافت نامنظم)",
        "مات",
        "براق",
        "نیمه‌براق",
        "رنگ ثابت",
        "ضد چروک",
        "آنتی پیل (ضد گوله شدن)",
        "شسته‌شده / واش‌شده",
        "دیسترس (کهنه‌نما)",
        "تای‌دای (رنگ‌آمیزی فانتزی)",
        "چاپ‌دار / گرافیکی",
        "ضد تعریق",
        "خشک‌شونده سریع",
        "ضد بو",
        "تنفس‌پذیر",
        "آنتی‌باکتریال",
        "ضد حساسیت",
        "مقاوم در برابر آفتاب (UV)",
        "مقاوم در برابر شستشو",
        "بدون نیاز به اتو",
        "دوخت دوبل",
        "درز مخفی",
        "لبه‌دوزی تمیز",
        "برش آزاد",
        "برش جذب / فیت",
    ]

    def handle(self, *args, **options):
        # Find categories for t-shirts. Match both ZWNJ and space variants and include subgroup linkage
        name_matches = Category.objects.filter(name__regex=r"(?i)تی.?شرت")
        subgroup_matches = Category.objects.filter(subgroup__name__regex=r"(?i)تی.?شرت")
        tshirt_categories = (name_matches | subgroup_matches).distinct()

        if not tshirt_categories.exists():
            self.stdout.write(self.style.WARNING("No تی‌شرت categories found."))
            return

        for category in tshirt_categories:
            self.stdout.write(f"Processing category: {category.name}")

            # Create or update CategoryAttribute
            attr, created = CategoryAttribute.objects.get_or_create(
                category=category,
                key=self.FEATURE_KEY,
                defaults={
                    "type": "multiselect",
                    "required": False,
                    "display_order": 0,
                    "label_fa": self.FEATURE_LABEL_FA,
                    "is_displayed_in_product": True,
                },
            )

            if not created:
                # Ensure correct type/label
                attr.type = "multiselect"
                attr.label_fa = self.FEATURE_LABEL_FA
                attr.is_displayed_in_product = True
                attr.save()

            # Replace existing values with the provided list
            attr.values.all().delete()

            bulk_values = [
                AttributeValue(attribute=attr, value=v, display_order=i)
                for i, v in enumerate(self.FEATURE_VALUES)
            ]
            AttributeValue.objects.bulk_create(bulk_values)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated '{self.FEATURE_KEY}' for {category.name} with {len(self.FEATURE_VALUES)} values."
                )
            )


