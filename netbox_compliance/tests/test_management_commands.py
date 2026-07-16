from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ..choices import ComplianceMeasureCategoryChoices, ComplianceMeasureResultTypeChoices, ComplianceMeasureSeverityChoices
from ..models import ComplianceMeasure, ComplianceResult
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
