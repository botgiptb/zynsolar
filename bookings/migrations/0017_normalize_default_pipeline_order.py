from django.db import migrations


def normalize_default_pipeline_order(apps, schema_editor):
    """Repair the default workflow order without changing user-facing names."""
    PipelineStage = apps.get_model('bookings', 'PipelineStage')
    expected_order = {
        'NEW': 1,
        'SITE_SURVEY': 2,
        'INSTALLATION': 3,
        'COMPLETED': 4,
    }
    for code, order in expected_order.items():
        PipelineStage.objects.filter(code=code).update(order=order)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0016_solarbooking_site_city_solarbooking_site_district_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize_default_pipeline_order, migrations.RunPython.noop),
    ]
