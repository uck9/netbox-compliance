from decimal import Decimal

from django.db import migrations, models


def _wipe_legacy_results_and_snapshots(apps, schema_editor):
    """
    ComplianceResult/ComplianceSnapshot rows created under the old
    status-only contract have no `value` and cannot be scored under the new
    credit-based model. Per spec, no backward compatibility is required --
    scripts repopulate results under the new value-based contract.
    """
    ComplianceResult = apps.get_model('netbox_compliance', 'ComplianceResult')
    ComplianceSnapshot = apps.get_model('netbox_compliance', 'ComplianceSnapshot')
    ComplianceResult.objects.all().delete()
    ComplianceSnapshot.objects.all().delete()


def _noop_reverse(apps, schema_editor):
    pass  # deletion is not reversible; migrating backward loses data regardless


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_compliance', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='compliancemeasure',
            name='result_type',
            field=models.CharField(default='boolean', max_length=20),
        ),
        migrations.AddField(
            model_name='compliancemeasure',
            name='pass_threshold',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='compliancemeasure',
            name='value_map',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='compliancemeasure',
            name='show_on_device_panel',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='compliancemeasure',
            name='panel_display_order',
            field=models.PositiveSmallIntegerField(default=100),
        ),
        migrations.AddField(
            model_name='compliancemeasure',
            name='display_template',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='compliancemeasure',
            name='required_detail_keys',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='compliancepackage',
            name='show_on_device_panel',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='compliancepackage',
            name='panel_display_order',
            field=models.PositiveSmallIntegerField(default=100),
        ),
        migrations.AddField(
            model_name='compliancepackage',
            name='amber_threshold',
            field=models.DecimalField(decimal_places=2, default=Decimal('80.00'), max_digits=5),
        ),
        migrations.AddField(
            model_name='compliancepackage',
            name='red_on_critical_fail',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='complianceresult',
            name='value',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.RunPython(_wipe_legacy_results_and_snapshots, _noop_reverse),
    ]
