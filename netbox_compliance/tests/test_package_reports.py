from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from ..models import CompliancePackage, CompliancePackageReport
from ..services import record_package_report
from .base import ComplianceTestMixin
from .custom import APITestCase


def make_package(slug='pkg-1', name=None):
    return CompliancePackage.objects.create(name=name or slug, slug=slug)


class CompliancePackageReportModelTest(ComplianceTestMixin, TestCase):
    def test_record_package_report_upserts_in_place(self):
        device = self.make_device()
        package = make_package()

        record_package_report(device, package, html='<h1>first</h1>', source='test')
        self.assertEqual(CompliancePackageReport.objects.count(), 1)

        record_package_report(device, package, html='<h1>second</h1>', source='test')
        self.assertEqual(CompliancePackageReport.objects.count(), 1)

        report = CompliancePackageReport.objects.get(device=device, package=package)
        self.assertEqual(report.html, '<h1>second</h1>')
        self.assertEqual(report.device_name, str(device))
        self.assertEqual(report.package_slug, package.slug)

    def test_different_devices_or_packages_get_separate_rows(self):
        device1 = self.make_device()
        device2 = self.make_device()
        package1 = make_package('pkg-a')
        package2 = make_package('pkg-b')

        record_package_report(device1, package1, html='<h1>a</h1>', source='test')
        record_package_report(device1, package2, html='<h1>b</h1>', source='test')
        record_package_report(device2, package1, html='<h1>c</h1>', source='test')

        self.assertEqual(CompliancePackageReport.objects.count(), 3)

    def test_device_deletion_set_nulls_but_keeps_the_row(self):
        device = self.make_device()
        package = make_package()
        record_package_report(device, package, html='<h1>x</h1>', source='test')

        device.delete()

        report = CompliancePackageReport.objects.get(package=package)
        self.assertIsNone(report.device_id)
        self.assertTrue(report.device_name)  # denormalized name survives

    def test_package_deletion_set_nulls_but_keeps_the_row(self):
        device = self.make_device()
        package = make_package()
        record_package_report(device, package, html='<h1>x</h1>', source='test')

        package.delete()

        report = CompliancePackageReport.objects.get(device=device)
        self.assertIsNone(report.package_id)
        self.assertTrue(report.package_slug)  # denormalized slug survives


class PackageReportBulkIngestTest(ComplianceTestMixin, APITestCase):
    model = CompliancePackageReport
    user_permissions = ('netbox_compliance.add_compliancepackagereport',)

    def setUp(self):
        super().setUp()
        self.device = self.make_device()
        self.package1 = make_package('pkg-a', 'Package A')
        self.package2 = make_package('pkg-b', 'Package B')

    def _url(self):
        return reverse('plugins-api:netbox_compliance-api:package-report-bulk')

    def test_single_object_payload_creates_reports(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'reports': [
                {'package': self.package1.slug, 'html': '<h1>a</h1>'},
                {'package': self.package2.slug, 'html': '<h1>b</h1>'},
            ],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created'], 2)
        self.assertEqual(CompliancePackageReport.objects.count(), 2)
        report = CompliancePackageReport.objects.get(device=self.device, package=self.package1)
        self.assertEqual(report.html, '<h1>a</h1>')
        self.assertEqual(report.source, 'test-runner')

    def test_repost_updates_the_existing_row_not_a_new_one(self):
        payload = {
            'device': self.device.name, 'source': 'test-runner',
            'reports': [{'package': self.package1.slug, 'html': '<h1>v1</h1>'}],
        }
        self.client.post(self._url(), payload, format='json', **self.header)

        payload['reports'][0]['html'] = '<h1>v2</h1>'
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CompliancePackageReport.objects.count(), 1)
        report = CompliancePackageReport.objects.get(device=self.device, package=self.package1)
        self.assertEqual(report.html, '<h1>v2</h1>')

    def test_package_resolves_by_pk_too(self):
        payload = {
            'device': self.device.name, 'source': 'test-runner',
            'reports': [{'package': self.package1.pk, 'html': '<h1>a</h1>'}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CompliancePackageReport.objects.filter(device=self.device, package=self.package1).exists())

    def test_unknown_device_rejects_whole_payload_atomically(self):
        payload = {
            'device': 'does-not-exist', 'source': 'test-runner',
            'reports': [{'package': self.package1.slug, 'html': '<h1>a</h1>'}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CompliancePackageReport.objects.count(), 0)

    def test_unknown_package_in_one_item_rejects_whole_batch(self):
        payload = {
            'device': self.device.name, 'source': 'test-runner',
            'reports': [
                {'package': self.package1.slug, 'html': '<h1>a</h1>'},
                {'package': 'does-not-exist', 'html': '<h1>b</h1>'},
            ],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CompliancePackageReport.objects.count(), 0)

    def test_missing_html_rejects_the_batch(self):
        payload = {
            'device': self.device.name, 'source': 'test-runner',
            'reports': [{'package': self.package1.slug}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CompliancePackageReport.objects.count(), 0)

    def test_list_payload_covers_multiple_devices(self):
        device2 = self.make_device()
        payload = [
            {'device': self.device.name, 'source': 'test-runner',
             'reports': [{'package': self.package1.slug, 'html': '<h1>a</h1>'}]},
            {'device': device2.name, 'source': 'test-runner',
             'reports': [{'package': self.package1.slug, 'html': '<h1>b</h1>'}]},
        ]
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created'], 2)
        self.assertEqual(CompliancePackageReport.objects.count(), 2)


class CompliancePackageReportRawViewTest(ComplianceTestMixin, TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(username='tester', password='pw')
        self.client.force_login(self.user)

    def test_returns_the_stored_html_verbatim_with_html_content_type(self):
        device = self.make_device()
        package = make_package()
        report = record_package_report(device, package, html='<h1>hello</h1>', source='test', timestamp=timezone.now())

        response = self.client.get(reverse('plugins:netbox_compliance:compliancepackagereport_raw', args=[report.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html')
        self.assertEqual(response.content.decode(), '<h1>hello</h1>')

    def test_404_on_missing_pk(self):
        response = self.client.get(reverse('plugins:netbox_compliance:compliancepackagereport_raw', args=[999999]))
        self.assertEqual(response.status_code, 404)
