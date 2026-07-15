import django.db.models.deletion
import taggit.managers
from django.db import migrations, models

import utilities.json


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('dcim', '0237_module_remove_local_context_data'),
        ('extras', '0140_imageattachment_image_size'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComplianceMeasure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('category', models.CharField(max_length=30)),
                ('severity', models.CharField(max_length=30)),
                ('max_result_age_days', models.PositiveIntegerField(default=35)),
                ('status', models.CharField(default='active', max_length=30)),
                ('comments', models.TextField(blank=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'compliance measure',
                'verbose_name_plural': 'compliance measures',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CompliancePackage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(default='draft', max_length=30)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'compliance package',
                'verbose_name_plural': 'compliance packages',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='PackageMeasure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('weight', models.PositiveSmallIntegerField(default=1)),
                ('required', models.BooleanField(default=True)),
                ('display_order', models.PositiveSmallIntegerField(default=100)),
                ('measure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='package_measures', to='netbox_compliance.compliancemeasure')),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='package_measures', to='netbox_compliance.compliancepackage')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'package measure',
                'verbose_name_plural': 'package measures',
                'ordering': ['display_order', 'measure__name'],
            },
        ),
        migrations.AddField(
            model_name='compliancepackage',
            name='measures',
            field=models.ManyToManyField(blank=True, related_name='packages', through='netbox_compliance.PackageMeasure', to='netbox_compliance.compliancemeasure'),
        ),
        migrations.AddConstraint(
            model_name='packagemeasure',
            constraint=models.UniqueConstraint(fields=('package', 'measure'), name='netbox_compliance_packagemeasure_unique_package_measure', violation_error_message='This measure is already part of this package.'),
        ),
        migrations.CreateModel(
            name='PackageAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('description', models.TextField(blank=True)),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_package_assignments', to='dcim.device')),
                ('device_role', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_package_assignments', to='dcim.devicerole')),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='netbox_compliance.compliancepackage')),
                ('platform', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_package_assignments', to='dcim.platform')),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_package_assignments', to='dcim.site')),
                ('site_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_package_assignments', to='dcim.sitegroup')),
                ('tag', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_package_assignments', to='extras.tag')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'package assignment',
                'verbose_name_plural': 'package assignments',
                'ordering': ['package', 'id'],
            },
        ),
        migrations.CreateModel(
            name='MeasureAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('description', models.TextField(blank=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compliance_measure_assignments', to='dcim.device')),
                ('measure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='direct_assignments', to='netbox_compliance.compliancemeasure')),
                ('weight', models.PositiveSmallIntegerField(default=1)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'measure assignment',
                'verbose_name_plural': 'measure assignments',
                'ordering': ['device', 'measure__name'],
            },
        ),
        migrations.AddConstraint(
            model_name='measureassignment',
            constraint=models.UniqueConstraint(fields=('device', 'measure'), name='netbox_compliance_measureassignment_unique_device_measure', violation_error_message='This measure is already directly assigned to this device.'),
        ),
        migrations.CreateModel(
            name='ComplianceExemption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('justification', models.TextField()),
                ('approved_by', models.CharField(blank=True, max_length=100)),
                ('valid_from', models.DateField()),
                ('valid_until', models.DateField(blank=True, null=True)),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_exemptions', to='dcim.device')),
                ('measure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exemptions', to='netbox_compliance.compliancemeasure')),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_exemptions', to='dcim.site')),
                ('site_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_exemptions', to='dcim.sitegroup')),
                ('tag', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='compliance_exemptions', to='extras.tag')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'compliance exemption',
                'verbose_name_plural': 'compliance exemptions',
                'ordering': ['-valid_from'],
            },
        ),
        migrations.CreateModel(
            name='ComplianceResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('status', models.CharField(max_length=30)),
                ('timestamp', models.DateTimeField()),
                ('source', models.CharField(max_length=100)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compliance_results', to='dcim.device')),
                ('measure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='netbox_compliance.compliancemeasure')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'compliance result',
                'verbose_name_plural': 'compliance results',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='complianceresult',
            index=models.Index(fields=['device', 'measure', '-timestamp'], name='netbox_comp_device__1ff2f8_idx'),
        ),
        migrations.CreateModel(
            name='ComplianceSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('device_name', models.CharField(max_length=100)),
                ('period', models.DateField()),
                ('overall_score', models.DecimalField(decimal_places=2, max_digits=5)),
                ('compliant', models.BooleanField(default=False)),
                ('data', models.JSONField()),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='compliance_snapshots', to='dcim.device')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'compliance snapshot',
                'verbose_name_plural': 'compliance snapshots',
                'ordering': ['-period', 'device_name'],
            },
        ),
        migrations.AddConstraint(
            model_name='compliancesnapshot',
            constraint=models.UniqueConstraint(fields=('device', 'period'), name='netbox_compliance_compliancesnapshot_unique_device_period', violation_error_message='A snapshot already exists for this device and period.'),
        ),
    ]
