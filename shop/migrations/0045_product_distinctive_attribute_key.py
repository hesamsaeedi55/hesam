# Generated manually for distinctive attribute feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0042_add_display_in_basket_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='distinctive_attribute_key',
            field=models.CharField(
                blank=True,
                help_text='ویژگی‌ای که برای تشخیص انواع محصول استفاده می‌شود (مثلاً رنگ)',
                max_length=50,
                null=True,
                verbose_name='ویژگی متمایز'
            ),
        ),
    ]

