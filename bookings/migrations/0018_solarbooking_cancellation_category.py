from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0017_normalize_default_pipeline_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='solarbooking',
            name='cancellation_category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('CUSTOMER_CANCELLED', 'Customer cancelled / changed decision'),
                    ('PRICE_OR_FINANCE', 'Price or finance issue'),
                    ('SITE_NOT_FEASIBLE', 'Site not technically feasible'),
                    ('OUTSIDE_SERVICE_AREA', 'Outside service area'),
                    ('DUPLICATE_OR_ERROR', 'Duplicate or incorrect order'),
                    ('OTHER', 'Other reason'),
                ],
                default='',
                max_length=40,
            ),
        ),
    ]
