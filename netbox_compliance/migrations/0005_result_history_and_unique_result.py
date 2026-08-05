import django.db.models.deletion
import taggit.managers
from django.db import migrations, models
from django.utils import timezone

import utilities.json


def _backfill_history_and_collapse_results(apps, schema_editor):
    """
    One-time transition from "ComplianceResult is an append-only log" to
    "ComplianceResult is the current row, ComplianceResultHistory is the
    log": every existing ComplianceResult row is copied into
    ComplianceResultHistory first (nothing is lost), then ComplianceResult
    itself is collapsed down to one row per (device, measure) -- the newest
    survives, older duplicates for the same pair are deleted (their content
    already lives on in history) so the new unique constraint can be added.
    """
    ComplianceResult = apps.get_model('netbox_compliance', 'ComplianceResult')
    ComplianceResultHistory = apps.get_model('netbox_compliance', 'ComplianceResultHistory')

    history_rows = []
    for result in ComplianceResult.objects.select_related('device', 'measure').all():
        device_name = ''
        if result.device_id:
            device_name = result.device.name or f'device (id {result.device_id})'
        measure_slug = result.measure.slug if result.measure_id else ''
        history_rows.append(ComplianceResultHistory(
            device_id=result.device_id,
            device_name=device_name,
            measure_id=result.measure_id,
            measure_slug=measure_slug,
            status=result.status,
            value=result.value,
            timestamp=result.timestamp,
            source=result.source,
            details=result.details,
        ))
    ComplianceResultHistory.objects.bulk_create(history_rows, batch_size=500)

    # Historical migration models carry no custom __str__/manager methods,
    # and Postgres DISTINCT ON needs the real model's queryset machinery --
    # a plain Python pass over (device_id, measure_id, -timestamp, -pk) is
    # simplest here since this only ever runs once, at migration time.
    seen = set()
    stale_ids = []
    for result in ComplianceResult.objects.order_by('device_id', 'measure_id', '-timestamp', '-pk').only(
        'pk', 'device_id', 'measure_id',
    ):
        key = (result.device_id, result.measure_id)
        if key in seen:
            stale_ids.append(result.pk)
        else:
            seen.add(key)
    ComplianceResult.objects.filter(pk__in=stale_ids).delete()


def _noop_reverse(apps, schema_editor):
    pass  # collapsing/backfilling is not reversible; migrating backward loses data regardless


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_compliance', '0004_exemption_package_and_tenant_scope'),
        ('dcim', '0237_module_remove_local_context_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComplianceResultHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('device_name', models.CharField(help_text='Denormalised for posterity', max_length=100)),
                ('measure_slug', models.CharField(help_text='Denormalised for posterity', max_length=100)),
                ('status', models.CharField(max_length=30)),
                ('value', models.CharField(blank=True, max_length=100, null=True)),
                ('timestamp', models.DateTimeField(default=timezone.now, help_text='When this observation was recorded')),
                ('source', models.CharField(max_length=100)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('device', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='compliance_result_history', to='dcim.device',
                )),
                ('measure', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='result_history', to='netbox_compliance.compliancemeasure',
                )),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'compliance result history entry',
                'verbose_name_plural': 'compliance result history',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='complianceresulthistory',
            index=models.Index(fields=['device', 'measure', '-timestamp'], name='netbox_comp_device__hist_idx'),
        ),
        migrations.RunPython(_backfill_history_and_collapse_results, _noop_reverse),
        migrations.RemoveIndex(
            model_name='complianceresult',
            name='netbox_comp_device__1ff2f8_idx',
        ),
        migrations.AddConstraint(
            model_name='complianceresult',
            constraint=models.UniqueConstraint(
                fields=('device', 'measure'), name='netbox_compliance_complianceresult_unique_device_measure',
                violation_error_message='A result already exists for this device and measure -- update it instead.',
            ),
        ),
    ]
