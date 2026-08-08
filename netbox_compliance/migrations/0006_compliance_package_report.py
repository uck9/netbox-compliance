import django.db.models.deletion
import taggit.managers
from django.db import migrations, models
from django.utils import timezone

import utilities.json


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_compliance', '0005_result_history_and_unique_result'),
        ('dcim', '0237_module_remove_local_context_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompliancePackageReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('device_name', models.CharField(help_text='Denormalised for posterity', max_length=100)),
                ('package_slug', models.CharField(help_text='Denormalised for posterity', max_length=100)),
                ('html', models.TextField(help_text="Raw self-contained report rendered by the last evaluation run")),
                ('source', models.CharField(help_text='Which script/system produced this report', max_length=100)),
                ('timestamp', models.DateTimeField(default=timezone.now, help_text='When this report was last (re)generated')),
                ('device', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='compliance_package_reports', to='dcim.device',
                )),
                ('package', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reports', to='netbox_compliance.compliancepackage',
                )),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'compliance package report',
                'verbose_name_plural': 'compliance package reports',
                'ordering': ['device_name', 'package_slug'],
            },
        ),
        migrations.AddConstraint(
            model_name='compliancepackagereport',
            constraint=models.UniqueConstraint(
                fields=('device', 'package'), name='netbox_compliance_compliancepackagereport_unique_device_package',
                violation_error_message='A report already exists for this device and package -- update it instead.',
            ),
        ),
    ]
