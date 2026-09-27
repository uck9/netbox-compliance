import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_compliance', '0006_compliance_package_report'),
        ('tenancy', '0001_squashed_0012'),
    ]

    operations = [
        migrations.AddField(
            model_name='packageassignment',
            name='tenant',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='compliance_package_assignments', to='tenancy.tenant',
            ),
        ),
    ]
