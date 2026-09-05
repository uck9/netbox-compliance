from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from ..choices import ComplianceMeasureCategoryChoices, ComplianceMeasureResultTypeChoices, ComplianceMeasureSeverityChoices
from ..models import (
    ComplianceMeasure,
    ComplianceResult,
    ComplianceResultHistory,
    ComplianceSnapshot,
    ComplianceSnapshotMeasureResult,
    MeasureAssignment,
)
from ..services import build_snapshot_data, record_result
from .base import ComplianceTestMixin

VALUE_MAP = {
    'target': {'label': 'Target version', 'color': 'green', 'credit': 100},
    'upgrade_required': {'label': 'Upgrade required', 'color': 'orange', 'credit': 40},
}


class ImportResultsFromCustomFieldsTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = ComplianceMeasure.objects.create(
            name='software-version', slug='software-version',
            category=ComplianceMeasureCategoryChoices.OPERATIONAL,
            severity=ComplianceMeasureSeverityChoices.HIGH,
            result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map=VALUE_MAP,
            required_detail_keys=['running', 'target'],
        )

    def _call(self, *args, **kwargs):
        out = StringIO()
        kwargs.setdefault('stdout', out)
        call_command('import_results_from_custom_fields', *args, **kwargs)
        return out.getvalue()

    def test_maps_cf_value_to_enum_key_and_creates_result(self):
        device = self.make_device()
        device.custom_field_data = {'sw_state': 'target', 'sw_running': '17.12.3', 'sw_target': '17.12.3'}
        device.save()

        output = self._call(
            measure='software-version', value_cf='sw_state',
            detail_cf=['running=sw_running', 'target=sw_target'],
        )

        self.assertIn('Created 1 results', output)
        result = ComplianceResult.objects.get(device=device, measure=self.measure)
        self.assertEqual(result.value, 'target')
        self.assertEqual(result.status, 'pass')
        self.assertEqual(result.details, {'running': '17.12.3', 'target': '17.12.3'})

    def test_dry_run_creates_nothing(self):
        device = self.make_device()
        device.custom_field_data = {'sw_state': 'target', 'sw_running': '17.12.3', 'sw_target': '17.12.3'}
        device.save()

        self._call(
            measure='software-version', value_cf='sw_state',
            detail_cf=['running=sw_running', 'target=sw_target'],
            dry_run=True,
        )

        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_unknown_enum_key_in_cf_is_skipped_with_warning(self):
        device = self.make_device()
        device.custom_field_data = {'sw_state': 'not-a-real-state', 'sw_running': '1.0', 'sw_target': '1.0'}
        device.save()

        output = self._call(
            measure='software-version', value_cf='sw_state',
            detail_cf=['running=sw_running', 'target=sw_target'],
        )

        self.assertIn('skipping', output)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_missing_required_detail_cf_mapping_raises_command_error(self):
        with self.assertRaises(CommandError):
            self._call(measure='software-version', value_cf='sw_state', detail_cf=['running=sw_running'])

    def test_non_enum_measure_rejected(self):
        boolean_measure = ComplianceMeasure.objects.create(
            name='bool-measure', slug='bool-measure',
            category=ComplianceMeasureCategoryChoices.OPERATIONAL,
            severity=ComplianceMeasureSeverityChoices.LOW,
        )
        with self.assertRaises(CommandError):
            self._call(measure='bool-measure', value_cf='sw_state', detail_cf=[])


class PruneComplianceResultsTest(ComplianceTestMixin, TestCase):
    """prune_compliance_results only ever prunes ComplianceResultHistory (the growing
    log) -- ComplianceResult itself (one row per device/measure, kept current in
    place) has nothing there to prune by age."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = ComplianceMeasure.objects.create(
            name='prune-measure', slug='prune-measure',
            category=ComplianceMeasureCategoryChoices.OPERATIONAL,
            severity=ComplianceMeasureSeverityChoices.LOW,
        )

    def _call(self, *args, **kwargs):
        out = StringIO()
        kwargs.setdefault('stdout', out)
        call_command('prune_compliance_results', *args, **kwargs)
        return out.getvalue()

    def test_old_history_not_covered_by_a_snapshot_is_kept(self):
        device = self.make_device()
        record_result(device, self.measure, status='pass', value='true', source='test')
        ComplianceResultHistory.objects.all().update(timestamp=timezone.now() - timedelta(days=200))

        output = self._call('--keep-days', '90')

        self.assertIn('Deleted 0', output)
        self.assertEqual(ComplianceResultHistory.objects.count(), 1)

    def test_old_history_covered_by_a_snapshot_is_pruned(self):
        device = self.make_device()
        record_result(device, self.measure, status='pass', value='true', source='test')
        old_timestamp = timezone.now() - timedelta(days=200)
        ComplianceResultHistory.objects.all().update(timestamp=old_timestamp)
        ComplianceSnapshot.objects.create(
            device=device, device_name=device.name, period=date(old_timestamp.year, old_timestamp.month, 1),
            overall_score=100, compliant=True, data={},
        )

        output = self._call('--keep-days', '90')

        self.assertIn('Deleted 1', output)
        self.assertEqual(ComplianceResultHistory.objects.count(), 0)

    def test_dry_run_deletes_nothing(self):
        device = self.make_device()
        record_result(device, self.measure, status='pass', value='true', source='test')
        old_timestamp = timezone.now() - timedelta(days=200)
        ComplianceResultHistory.objects.all().update(timestamp=old_timestamp)
        ComplianceSnapshot.objects.create(
            device=device, device_name=device.name, period=date(old_timestamp.year, old_timestamp.month, 1),
            overall_score=100, compliant=True, data={},
        )

        output = self._call('--keep-days', '90', '--dry-run')

        self.assertIn('Would delete 1', output)
        self.assertEqual(ComplianceResultHistory.objects.count(), 1)

    def test_orphaned_history_for_a_deleted_device_is_pruned_by_age_alone(self):
        device = self.make_device()
        record_result(device, self.measure, status='pass', value='true', source='test')
        ComplianceResultHistory.objects.all().update(timestamp=timezone.now() - timedelta(days=200))
        device.delete()  # ComplianceResultHistory.device is SET_NULL -- row survives with device_id=None

        entry = ComplianceResultHistory.objects.get()
        self.assertIsNone(entry.device_id)

        output = self._call('--keep-days', '90')

        self.assertIn('Deleted 1', output)
        self.assertEqual(ComplianceResultHistory.objects.count(), 0)

    def test_complianceresult_itself_is_never_touched(self):
        device = self.make_device()
        record_result(device, self.measure, status='pass', value='true', source='test')
        ComplianceResult.objects.all().update(timestamp=timezone.now() - timedelta(days=200))
        ComplianceResultHistory.objects.all().update(timestamp=timezone.now() - timedelta(days=200))
        old_timestamp = timezone.now() - timedelta(days=200)
        ComplianceSnapshot.objects.create(
            device=device, device_name=device.name, period=date(old_timestamp.year, old_timestamp.month, 1),
            overall_score=100, compliant=True, data={},
        )

        self._call('--keep-days', '90')

        self.assertEqual(ComplianceResult.objects.count(), 1)


class BackfillSnapshotMeasureResultsTest(ComplianceTestMixin, TestCase):
    """backfill_snapshot_measure_results -- one-off fixup for ComplianceSnapshot rows
    written before site/role/ComplianceSnapshotMeasureResult existed, deriving both
    from data already on hand (the snapshot's device, and its frozen `data`) rather
    than recomputing scoring for a past period."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = ComplianceMeasure.objects.create(
            name='Measure1', slug='measure1',
            category=ComplianceMeasureCategoryChoices.OPERATIONAL,
            severity=ComplianceMeasureSeverityChoices.LOW,
        )

    def _call(self, *args, **kwargs):
        out = StringIO()
        kwargs.setdefault('stdout', out)
        call_command('backfill_snapshot_measure_results', *args, **kwargs)
        return out.getvalue()

    def _pre_backfill_snapshot(self, device):
        """Build a snapshot the way generate_snapshots_for_period did before this
        feature existed: real `data`, but no site/role and no measure_results rows.
        Caller must assign self.measure to `device` first so it resolves as effective."""
        data, overall_score, compliant = build_snapshot_data(device)
        return ComplianceSnapshot.objects.create(
            device=device, device_name=device.name, period=date(2026, 5, 1),
            overall_score=overall_score, compliant=compliant, data=data,
        )

    def test_backfills_site_role_and_measure_results(self):
        device = self.make_device(site=self.site2, role=self.device_role2)
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)
        record_result(device, self.measure, status='pass', value='true', source='test')
        snapshot = self._pre_backfill_snapshot(device)
        self.assertIsNone(snapshot.site)
        self.assertEqual(ComplianceSnapshotMeasureResult.objects.filter(snapshot=snapshot).count(), 0)

        output = self._call()

        self.assertIn('Updated site/role on 1 snapshot', output)
        self.assertIn('created 1 measure result row', output)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.site, self.site2)
        self.assertEqual(snapshot.role, self.device_role2)
        result = ComplianceSnapshotMeasureResult.objects.get(snapshot=snapshot)
        self.assertEqual(result.measure, 'measure1')

    def test_is_idempotent(self):
        device = self.make_device(site=self.site2)
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)
        record_result(device, self.measure, status='pass', value='true', source='test')
        self._pre_backfill_snapshot(device)

        self._call()
        second_output = self._call()

        self.assertIn('Updated site/role on 0 snapshot', second_output)
        self.assertIn('created 0 measure result row', second_output)

    def test_dry_run_writes_nothing(self):
        device = self.make_device(site=self.site2)
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)
        record_result(device, self.measure, status='pass', value='true', source='test')
        snapshot = self._pre_backfill_snapshot(device)

        output = self._call('--dry-run')

        self.assertIn('Would update site/role on 1 snapshot', output)
        snapshot.refresh_from_db()
        self.assertIsNone(snapshot.site)
        self.assertEqual(ComplianceSnapshotMeasureResult.objects.filter(snapshot=snapshot).count(), 0)

    def test_device_since_deleted_is_skipped_for_site_role_but_still_gets_measure_results(self):
        device = self.make_device(site=self.site2)
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)
        record_result(device, self.measure, status='pass', value='true', source='test')
        snapshot = self._pre_backfill_snapshot(device)
        device.delete()  # ComplianceSnapshot.device is SET_NULL
        snapshot.refresh_from_db()
        self.assertIsNone(snapshot.device_id)

        output = self._call()

        self.assertIn('Updated site/role on 0 snapshot', output)
        self.assertEqual(ComplianceSnapshotMeasureResult.objects.filter(snapshot=snapshot).count(), 1)
