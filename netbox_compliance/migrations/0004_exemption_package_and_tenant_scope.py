import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_compliance', '0003_add_measure_title'),
        ('tenancy', '0001_squashed_0012'),
    ]

    operations = [
        migrations.AlterField(
            model_name='complianceexemption',
            name='measure',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='exemptions', to='netbox_compliance.compliancemeasure',
            ),
        ),
        migrations.AddField(
            model_name='complianceexemption',
            name='package',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='exemptions', to='netbox_compliance.compliancepackage',
                help_text='Exempt every measure in this package, instead of a single measure',
            ),
        ),
        migrations.AddField(
            model_name='complianceexemption',
            name='tenant',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='compliance_exemptions', to='tenancy.tenant',
            ),
        ),
    ]
