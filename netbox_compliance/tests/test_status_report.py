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
    grouped into a box per site with per-device rows; By Package (traffic light +
    per-package severity counters) and By Test (per-test status) tabs, plus tidy/long
    CSV export -- see views/status_report.py."""

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

    def test_by_package_tab_shows_site_box_with_device_and_package(self):
        device = self.make_device(site=self.site, tenant=self.tenant)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now(), source='test',
        )

        response = self.client.get(self._url(report='by_package', submitted='1'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.site.name)          # per-site box header
        self.assertContains(response, device.name)
        self.assertContains(response, f'#package-{self.package.slug}')  # package row link

    def test_by_test_tab_shows_device_measure_status_and_severity_ring(self):
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
        # Severity (High) shown on the row and as a ring class around the status dot.
        self.assertContains(response, self.measure.get_severity_display())
        self.assertContains(response, 'severity-ring-high')

    def test_failing_test_produces_a_severity_counter(self):
        device = self.make_device(site=self.site)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.FAIL,
            timestamp=timezone.now(), source='test',
        )

        response = self.client.get(self._url(report='by_package', submitted='1'))

        # One High-severity test failing -> "1 High" counter badge, on the package
        # row and rolled up onto the device line.
        self.assertContains(response, '1 High')

    def test_site_score_reflects_test_scores(self):
        # Two devices at the site: one PASS, one FAIL on the single required measure.
        # Site score = weighted mean of per-row credits = (100 + 0) / 2 = 50%.
        d1 = self.make_device(name='dev-pass', site=self.site)
        d2 = self.make_device(name='dev-fail', site=self.site)
        ComplianceResult.objects.create(
            device=d1, measure=self.measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now(), source='test',
        )
        ComplianceResult.objects.create(
            device=d2, measure=self.measure, status=ComplianceResultStatusChoices.FAIL,
            timestamp=timezone.now(), source='test',
        )

        response = self.client.get(self._url(report='by_package', submitted='1'))

        self.assertContains(response, 'cr-site-score')
        self.assertContains(response, '50%')

    def test_unevaluated_device_shows_no_results_not_no_failures(self):
        # Package assigned, but the device has zero ComplianceResults -> pending.
        self.make_device(site=self.site)

        response = self.client.get(self._url(report='by_package', submitted='1'))

        self.assertContains(response, 'no results yet')
        self.assertNotContains(response, 'no failing tests')

    def test_passing_device_shows_no_failing_tests(self):
        device = self.make_device(site=self.site)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now(), source='test',
        )

        response = self.client.get(self._url(report='by_test', submitted='1'))

        self.assertContains(response, device.name)
        self.assertContains(response, 'no failing tests')

    def test_devices_grouped_into_separate_site_boxes(self):
        PackageAssignment.objects.create(package=self.package, site=self.site2)
        d1 = self.make_device(name='dev-a', site=self.site)
        d2 = self.make_device(name='dev-b', site=self.site2)

        response = self.client.get(self._url(report='by_package', submitted='1'))
        content = response.content.decode()

        self.assertIn(self.site.name, content)
        self.assertIn(self.site2.name, content)
        self.assertIn(d1.name, content)
        self.assertIn(d2.name, content)
        # Two site boxes rendered.
        self.assertEqual(content.count('class="cr-site"'), 2)

    def test_non_applicable_package_row_is_omitted(self):
        other_package = CompliancePackage.objects.create(
            name='OtherPkg', slug='otherpkg', status=CompliancePackageStatusChoices.ACTIVE,
        )
        PackageMeasure.objects.create(package=other_package, measure=self.measure, weight=1, required=True)
        # other_package is only assigned to site2, so it does not apply to a site1 device.
        PackageAssignment.objects.create(package=other_package, site=self.site2)
        self.make_device(site=self.site)

        response = self.client.get(self._url(report='by_package', submitted='1'))

        self.assertContains(response, f'#package-{self.package.slug}')
        self.assertNotContains(response, f'#package-{other_package.slug}')

    def test_site_filter_excludes_devices_at_other_sites(self):
        PackageAssignment.objects.create(package=self.package, site=self.site2)
        device = self.make_device(site=self.site)
        other = self.make_device(name='other-device', site=self.site2)

        response = self.client.get(self._url(report='by_package', submitted='1', site=self.site.pk))

        self.assertContains(response, device.name)
        self.assertNotContains(response, other.name)

    def test_package_filter_narrows_tests_on_by_test_tab(self):
        other_measure = ComplianceMeasure.objects.create(
            name='Measure2', slug='measure2',
            category=ComplianceMeasureCategoryChoices.OPERATIONAL,
            severity=ComplianceMeasureSeverityChoices.LOW,
        )
        other_package = CompliancePackage.objects.create(
            name='Package2', slug='package2', status=CompliancePackageStatusChoices.ACTIVE,
        )
        PackageMeasure.objects.create(package=other_package, measure=other_measure, weight=1, required=True)
        PackageAssignment.objects.create(package=other_package, site=self.site)
        self.make_device(site=self.site)

        response = self.client.get(self._url(report='by_test', submitted='1', package=self.package.pk))

        # Only self.package's own test is listed as a row; the other package's test is not.
        self.assertContains(response, f'#measure-{self.measure.slug}')
        self.assertNotContains(response, f'#measure-{other_measure.slug}')

    def test_criticality_filter_limits_by_test_rows(self):
        low_measure = ComplianceMeasure.objects.create(
            name='LowMeasure', slug='lowmeasure',
            category=ComplianceMeasureCategoryChoices.OPERATIONAL,
            severity=ComplianceMeasureSeverityChoices.LOW,
        )
        PackageMeasure.objects.create(package=self.package, measure=low_measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        for m in (self.measure, low_measure):
            ComplianceResult.objects.create(
                device=device, measure=m, status=ComplianceResultStatusChoices.FAIL,
                timestamp=timezone.now(), source='test',
            )

        # self.measure is HIGH; low_measure is LOW. Filter to HIGH only.
        response = self.client.get(self._url(
            report='by_test', submitted='1', severity=ComplianceMeasureSeverityChoices.HIGH,
        ))

        self.assertContains(response, f'#measure-{self.measure.slug}')
        self.assertNotContains(response, f'#measure-{low_measure.slug}')

    def test_criticality_filter_all_selected_is_no_restriction(self):
        device = self.make_device(site=self.site)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.FAIL,
            timestamp=timezone.now(), source='test',
        )
        all_sev = [c[0] for c in ComplianceMeasureSeverityChoices.CHOICES]

        response = self.client.get(self._url(report='by_test', submitted='1', severity=all_sev))

        self.assertContains(response, f'#measure-{self.measure.slug}')

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
        self.assertIn(
            'Device,Site,Site Score,Tenant,Role,Device Score,Device Failing Tests,Test,Severity,Status,Value',
            content,
        )
        self.assertIn(device.name, content)
        self.assertIn(self.measure.name, content)
        self.assertIn(self.measure.get_severity_display(), content)

    def test_permission_required(self):
        self.client.logout()
        user = get_user_model().objects.create_user(username='nobody', password='pw')
        self.client.force_login(user)

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 403)
