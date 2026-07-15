from django.urls import reverse
from rest_framework import status

from ..choices import ComplianceMeasureCategoryChoices, ComplianceMeasureSeverityChoices
from ..models import ComplianceResult, MeasureAssignment
from ..models import ComplianceMeasure
from .base import ComplianceTestMixin
from .custom import APITestCase


def make_measure(slug):
    return ComplianceMeasure.objects.create(
        name=slug, slug=slug,
        category=ComplianceMeasureCategoryChoices.SECURITY,
        severity=ComplianceMeasureSeverityChoices.HIGH,
    )


class BulkResultIngestTest(ComplianceTestMixin, APITestCase):
    model = ComplianceResult
    user_permissions = ('netbox_compliance.add_complianceresult',)

    def setUp(self):
        super().setUp()
        self.measure1 = make_measure('bulk-measure-1')
        self.measure2 = make_measure('bulk-measure-2')
        self.device = self.make_device()
        MeasureAssignment.objects.create(device=self.device, measure=self.measure1, weight=1)

    def _url(self):
        return reverse('plugins-api:netbox_compliance-api:result-bulk')

    def test_single_object_payload_creates_results(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [
                {'measure': self.measure1.slug, 'status': 'pass'},
            ],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(response.data['warnings'], [])
        self.assertEqual(ComplianceResult.objects.filter(device=self.device, measure=self.measure1).count(), 1)

    def test_measure_not_in_effective_set_warns_but_still_stores(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [
                {'measure': self.measure2.slug, 'status': 'fail'},
            ],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(len(response.data['warnings']), 1)
        self.assertTrue(ComplianceResult.objects.filter(device=self.device, measure=self.measure2).exists())

    def test_unknown_device_rejects_whole_payload_atomically(self):
        payload = {
            'device': 'does-not-exist',
            'source': 'test-runner',
            'results': [{'measure': self.measure1.slug, 'status': 'pass'}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_unknown_measure_in_one_item_rejects_whole_batch(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [
                {'measure': self.measure1.slug, 'status': 'pass'},
                {'measure': 'does-not-exist', 'status': 'pass'},
            ],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_list_payload_covers_multiple_devices(self):
        device2 = self.make_device()
        MeasureAssignment.objects.create(device=device2, measure=self.measure1, weight=1)

        payload = [
            {
                'device': self.device.name, 'source': 'runner',
                'results': [{'measure': self.measure1.slug, 'status': 'pass'}],
            },
            {
                'device': device2.name, 'source': 'runner',
                'results': [{'measure': self.measure1.slug, 'status': 'fail'}],
            },
        ]
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created'], 2)
