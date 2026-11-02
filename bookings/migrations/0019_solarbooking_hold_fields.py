from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0018_solarbooking_cancellation_category'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AddField(model_name='solarbooking', name='held_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='solarbooking', name='hold_reason', field=models.TextField(blank=True, null=True)),
        migrations.AddField(model_name='solarbooking', name='is_on_hold', field=models.BooleanField(db_index=True, default=False)),
        migrations.AddField(model_name='solarbooking', name='held_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='held_bookings', to='auth.user')),
    ]
