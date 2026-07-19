from io import StringIO

from dcim.models import Device, Platform
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from ..models import ComplianceMeasure, ComplianceResult
from ..services import SOFTWARE_VERSION_MEASURE_SLUG
from .base import ComplianceTestMixin
from .test_software_version import PLATFORM_DATA, make_software_version_measure


class ValidateSoftwareVersionResultsTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = make_software_version_measure()
        cls.platform = Platform.objects.create(
            name='ValidatePlatform', slug='validate-platform',
            custom_field_data={'software_version_management': PLATFORM_DATA},
        )

    def _call(self, *args, **kwargs):
        out = StringIO()
        kwargs.setdefault('stdout', out)
        call_command('validate_software_version_results', *args, **kwargs)
        return out.getvalue()

    def test_raises_if_measure_missing(self):
        ComplianceMeasure.objects.filter(slug=SOFTWARE_VERSION_MEASURE_SLUG).delete()

        with self.assertRaises(CommandError):
            self._call()

    def test_no_results_is_zero_checked_zero_mismatches(self):
        output = self._call()

        self.assertIn('Checked 0 device(s)', output)
        self.assertIn('0 mismatch(es)', output)

    def test_stored_result_matching_current_policy_is_not_a_mismatch(self):
        device = self.make_device(platform=self.platform)
        # .update() bypasses the Device post_save signal (services.py's
        # evaluate_software_version) deliberately -- these tests want full
        # control over which ComplianceResult rows exist, not an
        # auto-generated one competing with the manually-created rows below.
        Device.objects.filter(pk=device.pk).update(custom_field_data={'software_version': '17.12.3'})
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status='pass', value='target_active_version',
            details={'running': '17.12.3', 'target': '17.12.3'}, timestamp=timezone.now(), source='test',
        )

        output = self._call()

        self.assertIn('Checked 1 device(s)', output)
        self.assertIn('0 mismatch(es)', output)

    def test_stale_target_is_reported_as_a_mismatch(self):
        device = self.make_device(platform=self.platform)
        Device.objects.filter(pk=device.pk).update(custom_field_data={'software_version': '17.12.3'})
        # Stored result claims a target that no longer matches the platform's
        # current version_policy (e.g. left over from before a policy update,
        # or from the pre-fix schema-mismatch bug).
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status='pass', value='target_active_version',
            details={'running': '17.12.3', 'target': '99.0.0'}, timestamp=timezone.now(), source='test',
        )

        output = self._call()

        self.assertIn('Checked 1 device(s)', output)
        self.assertIn('1 mismatch(es)', output)
        self.assertIn(str(device), output)
        self.assertIn("target='99.0.0'", output)
        self.assertIn("target='17.12.3'", output)

    def test_fix_writes_a_corrected_result_for_each_mismatch(self):
        device = self.make_device(platform=self.platform)
        Device.objects.filter(pk=device.pk).update(custom_field_data={'software_version': '17.12.3'})
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status='pass', value='target_active_version',
            details={'running': '17.12.3', 'target': '99.0.0'}, timestamp=timezone.now(), source='test',
        )

        output = self._call('--fix')

        self.assertIn('1 mismatch(es)', output)
        self.assertIn('Wrote 1 corrected ComplianceResult row(s)', output)
        latest = ComplianceResult.objects.filter(device=device, measure=self.measure).order_by('-timestamp').first()
        self.assertEqual(latest.value, 'target_active_version')
        self.assertEqual(latest.details['target'], '17.12.3')

    def test_fix_without_mismatches_writes_nothing_extra(self):
        device = self.make_device(platform=self.platform)
        Device.objects.filter(pk=device.pk).update(custom_field_data={'software_version': '17.12.3'})
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status='pass', value='target_active_version',
            details={'running': '17.12.3', 'target': '17.12.3'}, timestamp=timezone.now(), source='test',
        )

        output = self._call('--fix')

        self.assertIn('0 mismatch(es)', output)
        self.assertNotIn('Wrote', output)
        self.assertEqual(ComplianceResult.objects.filter(device=device, measure=self.measure).count(), 1)

    def test_only_latest_result_per_device_is_checked(self):
        device = self.make_device(platform=self.platform)
        Device.objects.filter(pk=device.pk).update(custom_field_data={'software_version': '17.12.3'})
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status='fail', value='required_upgrade',
            details={'running': '1.0.0', 'target': 'nonsense'}, timestamp=timezone.now() - timezone.timedelta(days=1),
            source='test',
        )
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status='pass', value='target_active_version',
            details={'running': '17.12.3', 'target': '17.12.3'}, timestamp=timezone.now(), source='test',
        )

        output = self._call()

        self.assertIn('Checked 1 device(s)', output)
        self.assertIn('0 mismatch(es)', output)
