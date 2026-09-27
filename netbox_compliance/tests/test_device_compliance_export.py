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
from ..models import (
    ComplianceMeasure,
    CompliancePackage,
    CompliancePackageReport,
    ComplianceResult,
    MeasureAssignment,
    PackageAssignment,
    PackageMeasure,
)
from .base import ComplianceTestMixin


class DeviceComplianceExportViewTest(ComplianceTestMixin, TestCase):
    """The standalone, self-contained per-device compliance export/download document
    (views/device.py's DeviceComplianceExportView, dcim:device_compliance_export) --
    same resolved data as the Compliance tab, flattened into one printable/downloadable
    page rather than the tab's collapsible per-package cards."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.package = CompliancePackage.objects.create(
            name='ExportPkg', slug='exportpkg', status=CompliancePackageStatusChoices.ACTIVE,
        )
        cls.measure = ComplianceMeasure.objects.create(
            name='ExportMeasure', slug='export-measure',
            category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.CRITICAL,
        )
        PackageMeasure.objects.create(package=cls.package, measure=cls.measure, weight=1, required=True)
        PackageAssignment.objects.create(package=cls.package, site=cls.site)

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(username='tester', password='pw')
        self.client.force_login(self.user)

    def test_export_shows_device_package_and_test(self):
        device = self.make_device(site=self.site)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.FAIL,
            timestamp=timezone.now(), source='test',
            details={'running': '17.3.1', 'target': '17.6.1'},
        )

        response = self.client.get(reverse('dcim:device_compliance_export', args=[device.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, device.name)
        self.assertContains(response, self.package.name)
        self.assertContains(response, self.measure.name)
        self.assertContains(response, 'Fail')
        self.assertContains(response, 'Critical')
        self.assertContains(response, 'running')
        self.assertContains(response, '17.3.1')

    def test_evidence_shaped_details_show_missing_unexpected_and_remediation(self):
        """A details blob shaped like config-compliance-engine's Evidence gets broken out into
        Missing/Unexpected/Remediation callouts here too, not just on the in-app result page --
        same evidence shape, same treatment, in the downloadable/printable document."""
        device = self.make_device(site=self.site)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.FAIL,
            timestamp=timezone.now(), source='test',
            details={
                'rule_id': 'CONF-NETCF-003',
                'evidence': {
                    'expected': 'exactly the approved permit entries',
                    'found': [],
                    'missing': [{'regex': '^ permit 10.240.18.0 0.0.0.255$', 'parent': 'ACL'}],
                    'unexpected': [{'line': ' 50 permit 10.99.99.0 0.0.0.255', 'line_number': 12, 'parent': 'ACL'}],
                    'error': None,
                },
                'remediation': 'Remove the unapproved permit entry and add the missing approved one.',
            },
        )

        response = self.client.get(reverse('dcim:device_compliance_export', args=[device.pk]))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('Missing', content)
        self.assertIn('Unexpected', content)
        self.assertIn('10.240.18.0 0.0.0.255', content)
        self.assertIn('10.99.99.0 0.0.0.255', content)
        self.assertIn('Remediation', content)
        self.assertIn('Remove the unapproved permit entry', content)
        # full raw JSON is still available, collapsed behind a <details> toggle -- same as the
        # in-app result page, nothing lost just because it's summarized above
        self.assertIn('Raw details', content)
        self.assertIn('<details', content)
        self.assertIn('CONF-NETCF-003', content)

    def test_embeds_raw_package_report_when_present(self):
        device = self.make_device(site=self.site)
        CompliancePackageReport.objects.create(
            device=device, device_name=device.name, package=self.package, package_slug=self.package.slug,
            html='<p>Raw external report body</p>', source='external-tool', timestamp=timezone.now(),
        )

        response = self.client.get(reverse('dcim:device_compliance_export', args=[device.pk]))
        content = response.content.decode()

        self.assertIn('External Evaluation Report', content)
        self.assertIn('Raw external report body', content)

    def test_direct_measure_included(self):
        """Also regression coverage for the get_extra_context bug this session found:
        DeviceComplianceTabView (which _build_device_compliance_context is shared with)
        used to call the never-defined services.render_value_display() for direct
        measures -- a 500 that no prior test caught since none exercised this path."""
        device = self.make_device(site=self.site)
        direct_measure = ComplianceMeasure.objects.create(
            name='DirectExportMeasure', slug='direct-export-measure',
            category=ComplianceMeasureCategoryChoices.OPERATIONAL,
            severity=ComplianceMeasureSeverityChoices.LOW,
        )
        MeasureAssignment.objects.create(device=device, measure=direct_measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=direct_measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now(), source='test',
        )

        response = self.client.get(reverse('dcim:device_compliance_export', args=[device.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Direct Measures')
        self.assertContains(response, direct_measure.name)

    def test_download_sets_content_disposition(self):
        device = self.make_device(site=self.site)

        response = self.client.get(reverse('dcim:device_compliance_export', args=[device.pk]) + '?download=1')

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn(device.name, response['Content-Disposition'])

    def test_viewing_inline_has_no_content_disposition(self):
        device = self.make_device(site=self.site)

        response = self.client.get(reverse('dcim:device_compliance_export', args=[device.pk]))

        self.assertNotIn('Content-Disposition', response)

    def test_permission_required(self):
        self.client.logout()
        user = get_user_model().objects.create_user(username='nobody', password='pw')
        self.client.force_login(user)
        device = self.make_device(site=self.site)

        response = self.client.get(reverse('dcim:device_compliance_export', args=[device.pk]))

        self.assertEqual(response.status_code, 403)

    def test_unknown_device_404s(self):
        response = self.client.get(reverse('dcim:device_compliance_export', args=[999999]))

        self.assertEqual(response.status_code, 404)
