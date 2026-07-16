from decimal import Decimal

from django.urls import reverse
from rest_framework import status

from ..choices import ComplianceMeasureCategoryChoices, ComplianceMeasureResultTypeChoices, ComplianceMeasureSeverityChoices
from ..models import ComplianceResult, MeasureAssignment
from ..models import ComplianceMeasure
from .base import ComplianceTestMixin
from .custom import APITestCase

VALUE_MAP = {
    'target': {'label': 'Target version', 'color': 'green', 'credit': 100},
    'upgrade_required': {'label': 'Upgrade required', 'color': 'orange', 'credit': 40},
}


def make_measure(slug, result_type=ComplianceMeasureResultTypeChoices.BOOLEAN, **kwargs):
    return ComplianceMeasure.objects.create(
        name=slug, slug=slug,
        category=ComplianceMeasureCategoryChoices.SECURITY,
        severity=ComplianceMeasureSeverityChoices.HIGH,
        result_type=result_type,
        **kwargs,
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
                {'measure': self.measure1.slug, 'value': True},
            ],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(response.data['warnings'], [])
        result = ComplianceResult.objects.get(device=self.device, measure=self.measure1)
        self.assertEqual(result.status, 'pass')
        self.assertEqual(result.value, 'true')

    def test_measure_not_in_effective_set_warns_but_still_stores(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [
                {'measure': self.measure2.slug, 'value': False},
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
            'results': [{'measure': self.measure1.slug, 'value': True}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_unknown_measure_in_one_item_rejects_whole_batch(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [
                {'measure': self.measure1.slug, 'value': True},
                {'measure': 'does-not-exist', 'value': True},
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
                'results': [{'measure': self.measure1.slug, 'value': True}],
            },
            {
                'device': device2.name, 'source': 'runner',
                'results': [{'measure': self.measure1.slug, 'value': False}],
            },
        ]
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['created'], 2)

    def test_enum_unknown_key_rejected_atomically(self):
        enum_measure = make_measure('bulk-enum', result_type=ComplianceMeasureResultTypeChoices.ENUM, value_map=VALUE_MAP)
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{'measure': enum_measure.slug, 'value': 'not-a-real-key'}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_enum_known_key_creates_result_with_derived_status(self):
        enum_measure = make_measure('bulk-enum-2', result_type=ComplianceMeasureResultTypeChoices.ENUM, value_map=VALUE_MAP)
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{'measure': enum_measure.slug, 'value': 'upgrade_required', 'details': {}}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        result = ComplianceResult.objects.get(device=self.device, measure=enum_measure)
        self.assertEqual(result.status, 'fail')  # credit 40 != 100
        self.assertEqual(result.value, 'upgrade_required')

    def test_percentage_non_numeric_value_rejected(self):
        pct_measure = make_measure('bulk-pct', result_type=ComplianceMeasureResultTypeChoices.PERCENTAGE, pass_threshold=Decimal('90.00'))
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{'measure': pct_measure.slug, 'value': 'not-a-number'}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_percentage_value_creates_result_with_derived_status(self):
        pct_measure = make_measure('bulk-pct-2', result_type=ComplianceMeasureResultTypeChoices.PERCENTAGE, pass_threshold=Decimal('90.00'))
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{'measure': pct_measure.slug, 'value': 95.5}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        result = ComplianceResult.objects.get(device=self.device, measure=pct_measure)
        self.assertEqual(result.status, 'pass')

    def test_boolean_missing_value_rejected(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{'measure': self.measure1.slug, 'status': 'pass'}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_explicit_error_status_accepted_without_value(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{'measure': self.measure1.slug, 'status': 'error'}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        result = ComplianceResult.objects.get(device=self.device, measure=self.measure1)
        self.assertEqual(result.status, 'error')
        self.assertIsNone(result.value)

    def test_explicit_not_applicable_status_accepted_without_value(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{'measure': self.measure1.slug, 'status': 'not_applicable'}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        result = ComplianceResult.objects.get(device=self.device, measure=self.measure1)
        self.assertEqual(result.status, 'not_applicable')

    def test_status_other_than_error_or_na_rejected_as_explicit_input(self):
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{'measure': self.measure1.slug, 'status': 'pass'}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_required_detail_keys_enforced_missing_key_rejects_batch(self):
        detail_measure = make_measure(
            'bulk-details', result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map=VALUE_MAP, required_detail_keys=['running', 'target'],
        )
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{'measure': detail_measure.slug, 'value': 'target', 'details': {'running': '1.0'}}],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_required_detail_keys_satisfied_creates_result(self):
        detail_measure = make_measure(
            'bulk-details-2', result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map=VALUE_MAP, required_detail_keys=['running', 'target'],
        )
        payload = {
            'device': self.device.name,
            'source': 'test-runner',
            'results': [{
                'measure': detail_measure.slug, 'value': 'target',
                'details': {'running': '1.0', 'target': '1.0'},
            }],
        }
        response = self.client.post(self._url(), payload, format='json', **self.header)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(ComplianceResult.objects.filter(device=self.device, measure=detail_measure).exists())


class ComplianceResultLatestFilterTest(ComplianceTestMixin, APITestCase):
    model = ComplianceResult
    user_permissions = ('netbox_compliance.view_complianceresult',)

    def test_latest_filter_returns_one_row_per_device_measure(self):
        from django.utils import timezone

        measure = make_measure('latest-measure')
        device = self.make_device()
        older = ComplianceResult.objects.create(
            device=device, measure=measure, status='pass', value='true',
            timestamp=timezone.now() - timezone.timedelta(days=2), source='test',
        )
        newer = ComplianceResult.objects.create(
            device=device, measure=measure, status='fail', value='false',
            timestamp=timezone.now(), source='test',
        )

        url = reverse('plugins-api:netbox_compliance-api:complianceresult-list')
        response = self.client.get(f'{url}?latest=true', **self.header)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {newer.pk})
        self.assertNotIn(older.pk, ids)


class DeviceComplianceStatusAPITest(ComplianceTestMixin, APITestCase):
    model = ComplianceResult
    user_permissions = ('netbox_compliance.view_complianceresult', 'dcim.view_device')

    def test_status_endpoint_includes_typed_fields_and_traffic_light(self):
        from django.utils import timezone

        from ..models import CompliancePackage, PackageAssignment, PackageMeasure
        from ..choices import CompliancePackageStatusChoices

        measure = make_measure(
            'status-enum', result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map=VALUE_MAP, display_template='{{ label }}',
        )
        package = CompliancePackage.objects.create(name='StatusPkg', slug='statuspkg', status=CompliancePackageStatusChoices.ACTIVE)
        PackageMeasure.objects.create(package=package, measure=measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        ComplianceResult.objects.create(
            device=device, measure=measure, status='fail', value='upgrade_required',
            timestamp=timezone.now(), source='test',
        )

        url = reverse('plugins-api:netbox_compliance-api:device-status', kwargs={'pk': device.pk})
        response = self.client.get(url, **self.header)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        package_data = response.data['packages'][0]
        self.assertIn('traffic_light', package_data)
        measure_data = package_data['measures'][0]
        self.assertEqual(measure_data['result_type'], 'enum')
        self.assertEqual(measure_data['value'], 'upgrade_required')
        self.assertEqual(measure_data['display_label'], 'Upgrade required')
        self.assertEqual(measure_data['credit'], 40)

    def test_status_endpoint_display_text_renders_display_template(self):
        from django.utils import timezone

        from ..models import MeasureAssignment

        measure = make_measure(
            'status-template', result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map=VALUE_MAP, display_template='{{ details.running }} (target {{ details.target }})',
        )
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=measure, status='pass', value='target',
            details={'running': '17.9.4a', 'target': '17.12.3'},
            timestamp=timezone.now(), source='test',
        )

        url = reverse('plugins-api:netbox_compliance-api:device-status', kwargs={'pk': device.pk})
        response = self.client.get(url, **self.header)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        measure_data = response.data['direct_measures'][0]
        self.assertEqual(measure_data['display_text'], '17.9.4a (target 17.12.3)')
