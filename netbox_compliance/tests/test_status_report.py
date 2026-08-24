from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from tenancy.models import Tenant

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceResultStatusChoices,
    CompliancePackageStatusChoices,
)
from ..models import ComplianceMeasure, CompliancePackage, ComplianceResult, PackageAssignment, PackageMeasure
from .base import ComplianceTestMixin


class StatusReportViewTest(ComplianceTestMixin, TestCase):
    """The dynamic Package & Test Status Report: filter by site/tenant/package/test,
    By Package (traffic light per package) and By Test (status blob per measure)
    tabs, and tidy/long CSV export -- see views/status_report.py."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tenant = Tenant.objects.create(name='Tenant1', slug='tenant1')
        cls.package = CompliancePackage.objects.create(
            name='Package1', slug='package1', status=CompliancePackageStatusChoices.ACTIVE,
        )
        cls.measure = ComplianceMeasure.objects.create(
            name='Measure1', slug='measure1',
            category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH,
        )
        PackageMeasure.objects.create(package=cls.package, measure=cls.measure, weight=1, required=True)
        PackageAssignment.objects.create(package=cls.package, site=cls.site)

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(username='tester', password='pw')
        self.client.force_login(self.user)

    def _url(self, **params):
        url = reverse('plugins:netbox_compliance:status_report')
        if params:
            url += '?' + urlencode(params, doseq=True)
        return url

    def test_unsubmitted_shows_prompt_without_querying(self):
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select filters above')

    def test_by_package_tab_shows_device_and_package(self):
        device = self.make_device(site=self.site, tenant=self.tenant)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now(), source='test',
        )

        response = self.client.get(self._url(report='by_package', submitted='1'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, device.name)
        self.assertContains(response, self.package.name)

    def test_by_test_tab_shows_device_measure_and_status(self):
        device = self.make_device(site=self.site, tenant=self.tenant)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.FAIL,
            timestamp=timezone.now(), source='test',
        )

        response = self.client.get(self._url(report='by_test', submitted='1'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, device.name)
        self.assertContains(response, self.measure.name)
        self.assertContains(response, 'Fail')
        # Severity (High, per setUpTestData) shown on the column header and as a ring
        # class around the status dot -- see status_report.html's severity-ring-* CSS.
        self.assertContains(response, self.measure.get_severity_display())
        self.assertContains(response, 'severity-ring-high')

    def test_site_filter_excludes_devices_at_other_sites(self):
        device = self.make_device(site=self.site)
        other = self.make_device(name='other-device', site=self.site2)

        response = self.client.get(self._url(report='by_package', submitted='1', site=self.site.pk))

        self.assertContains(response, device.name)
        self.assertNotContains(response, other.name)

    def test_package_filter_narrows_test_columns_on_by_test_tab(self):
        other_measure = ComplianceMeasure.objects.create(
            name='Measure2', slug='measure2',
            category=ComplianceMeasureCategoryChoices.OPERATIONAL,
            severity=ComplianceMeasureSeverityChoices.LOW,
        )
        self.make_device(site=self.site)

        response = self.client.get(self._url(report='by_test', submitted='1', package=self.package.pk))

        # Both measures' names also appear as options in the filter bar's Test <select>,
        # so assert on the table-column-only link href rather than the bare name.
        self.assertContains(response, self.measure.get_absolute_url())
        self.assertNotContains(response, other_measure.get_absolute_url())

    def test_csv_export_is_tidy_long_format(self):
        device = self.make_device(site=self.site, tenant=self.tenant)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now(), source='test',
        )

        response = self.client.get(self._url(report='by_test', submitted='1', format='csv'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode()
        self.assertIn('Device,Site,Tenant,Test,Severity,Applicable,Status,Value', content)
        self.assertIn(device.name, content)
        self.assertIn(self.measure.name, content)
        self.assertIn(self.measure.get_severity_display(), content)

    def test_permission_required(self):
        self.client.logout()
        user = get_user_model().objects.create_user(username='nobody', password='pw')
        self.client.force_login(user)

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 403)
