from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceResultStatusChoices,
    CompliancePackageStatusChoices,
)
from ..models import ComplianceMeasure, CompliancePackage, ComplianceResult, PackageAssignment, PackageMeasure
from .base import ComplianceTestMixin


def make_measure(slug, title='', description=''):
    return ComplianceMeasure.objects.create(
        name=slug, slug=slug, title=title, description=description,
        category=ComplianceMeasureCategoryChoices.SECURITY,
        severity=ComplianceMeasureSeverityChoices.HIGH,
    )


class DeviceComplianceTabBucketingTest(ComplianceTestMixin, TestCase):
    """The 'Compliance' tab on the core Device page (views/device.py's DeviceComplianceTabView)
    buckets each package's rows into failing (shown by default), not_applicable (collapsed,
    like passing), and passing (collapsed) -- regression coverage for the not_applicable split,
    plus that each row's measure.short_description reaches the template context unmangled."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.package = CompliancePackage.objects.create(
            name='TabPkg', slug='tabpkg', status=CompliancePackageStatusChoices.ACTIVE,
        )
        cls.measure_pass = make_measure('tab-measure-pass', title='Short desc for pass')
        cls.measure_fail = make_measure('tab-measure-fail', title='Short desc for fail')
        cls.measure_na = make_measure('tab-measure-na', title='Short desc for na')
        for m in (cls.measure_pass, cls.measure_fail, cls.measure_na):
            PackageMeasure.objects.create(package=cls.package, measure=m, weight=1, required=True)

    def _post_result(self, device, measure, status):
        ComplianceResult.objects.create(device=device, measure=measure, status=status, timestamp=timezone.now(), source='test')

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(username='tester', password='pw')
        self.client.force_login(self.user)

    def test_rows_bucketed_into_failing_not_applicable_passing(self):
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=self.package, site=self.site)
        self._post_result(device, self.measure_pass, ComplianceResultStatusChoices.PASS)
        self._post_result(device, self.measure_fail, ComplianceResultStatusChoices.FAIL)
        self._post_result(device, self.measure_na, ComplianceResultStatusChoices.NOT_APPLICABLE)

        response = self.client.get(reverse('dcim:device_compliance', args=[device.pk]))

        self.assertEqual(response.status_code, 200)
        entry = response.context['packages'][0]
        self.assertEqual([r.measure for r in entry['failing_rows']], [self.measure_fail])
        self.assertEqual([r.measure for r in entry['not_applicable_rows']], [self.measure_na])
        self.assertEqual([r.measure for r in entry['passing_rows']], [self.measure_pass])
        self.assertEqual(entry['not_applicable_count'], 1)

    def test_short_description_rendered_for_each_status_bucket(self):
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=self.package, site=self.site)
        self._post_result(device, self.measure_pass, ComplianceResultStatusChoices.PASS)
        self._post_result(device, self.measure_fail, ComplianceResultStatusChoices.FAIL)
        self._post_result(device, self.measure_na, ComplianceResultStatusChoices.NOT_APPLICABLE)

        response = self.client.get(reverse('dcim:device_compliance', args=[device.pk]))
        content = response.content.decode()

        self.assertIn('Short desc for pass', content)
        self.assertIn('Short desc for fail', content)
        self.assertIn('Short desc for na', content)
