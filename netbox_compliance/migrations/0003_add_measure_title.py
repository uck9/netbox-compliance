from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_compliance', '0002_typed_measures_panel'),
    ]

    operations = [
        migrations.AddField(
            model_name='compliancemeasure',
            name='title',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
