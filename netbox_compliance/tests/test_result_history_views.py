"""UI page renders for ComplianceResult/ComplianceResultHistory -- caught a real bug the API-only
tests in test_api.py couldn't: ComplianceResultHistoryTable inherited NetBoxTable's default
actions column (edit/delete/changelog), but no edit view exists for this read-only, system-
generated model, so rendering the list (or the inline history panel on a ComplianceResult's own
detail page) raised NoReverseMatch. Full HTML rendering, not just querying the table/queryset in
isolation, is the only way this class of bug shows up -- see tables/results.py's fix
(ActionsColumn restricted to ('delete', 'changelog'), same as ComplianceSnapshotTable)."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from ..models import ComplianceMeasure, ComplianceResultHistory
from ..choices import ComplianceMeasureCategoryChoices, ComplianceMeasureSeverityChoices
from ..services import record_result
from .base import ComplianceTestMixin


class ResultAndHistoryPageRenderTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = ComplianceMeasure.objects.create(
            name='render-measure', slug='render-measure',
            category=ComplianceMeasureCategoryChoices.OPERATIONAL,
            severity=ComplianceMeasureSeverityChoices.LOW,
        )

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(username='tester', password='pw')
        self.client.force_login(self.user)

    def test_result_history_list_view_renders(self):
        device = self.make_device()
        record_result(device, self.measure, status='pass', value='true', source='test')

        response = self.client.get(reverse('plugins:netbox_compliance:complianceresulthistory_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, device.name)

    def test_result_detail_view_renders_with_history_panel(self):
        device = self.make_device()
        record_result(device, self.measure, status='pass', value='true', source='test')
        record_result(device, self.measure, status='fail', value='false', source='test')

        from ..models import ComplianceResult
        result = ComplianceResult.objects.get(device=device, measure=self.measure)
        response = self.client.get(reverse('plugins:netbox_compliance:complianceresult', args=[result.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'History')
        # both history entries (pass then fail) show up in the inline panel
        self.assertEqual(
            ComplianceResultHistory.objects.filter(device=device, measure=self.measure).count(), 2,
        )

    def test_result_history_detail_view_renders(self):
        device = self.make_device()
        record_result(device, self.measure, status='pass', value='true', source='test')
        entry = ComplianceResultHistory.objects.get(device=device, measure=self.measure)

        response = self.client.get(reverse('plugins:netbox_compliance:complianceresulthistory', args=[entry.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, device.name)

    def test_result_history_detail_view_renders_after_device_deleted(self):
        """device is SET_NULL on ComplianceResultHistory -- the detail page must still
        render using the denormalized device_name, not 404 or crash on a null FK."""
        device = self.make_device()
        record_result(device, self.measure, status='pass', value='true', source='test')
        entry = ComplianceResultHistory.objects.get(device=device, measure=self.measure)
        device_name = device.name
        device.delete()

        response = self.client.get(reverse('plugins:netbox_compliance:complianceresulthistory', args=[entry.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, device_name)
        self.assertContains(response, 'device deleted')

    def test_result_detail_view_renders_evidence_missing_unexpected_and_remediation(self):
        """A details blob shaped like config-compliance-engine's Evidence (missing/unexpected
        lists, a remediation string) gets broken out into its own labelled callouts on the
        result detail page, not left as an opaque JSON blob."""
        device = self.make_device()
        details = {
            'rule_id': 'CONF-NETCF-003',
            'evidence': {
                'expected': 'exactly the approved permit entries',
                'found': [],
                'missing': [{'regex': '^ permit 10.240.18.0 0.0.0.255$', 'parent': 'ip access-list standard X'}],
                'unexpected': [{'line': ' 50 permit 10.99.99.0 0.0.0.255', 'line_number': 12, 'parent': 'ip access-list standard X'}],
                'error': None,
            },
            'remediation': 'Remove the unapproved permit entry and add the missing approved one.',
        }
        result = record_result(device, self.measure, status='fail', value='false', details=details, source='test')

        response = self.client.get(reverse('plugins:netbox_compliance:complianceresult', args=[result.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Missing')
        self.assertContains(response, 'Unexpected')
        self.assertContains(response, '10.240.18.0 0.0.0.255')
        self.assertContains(response, '10.99.99.0 0.0.0.255')
        self.assertContains(response, 'Remediation')
        self.assertContains(response, 'Remove the unapproved permit entry')

    def test_result_detail_view_falls_back_to_raw_json_for_unrecognised_details_shape(self):
        """A details blob from some other source/script (no evidence.missing/unexpected keys)
        must still render -- as the plain raw JSON this page always showed -- not error out or
        silently show nothing."""
        device = self.make_device()
        details = {'running': '17.3.4', 'target': '17.3.6', 'note': 'behind by two releases'}
        result = record_result(device, self.measure, status='fail', value='false', details=details, source='test')

        response = self.client.get(reverse('plugins:netbox_compliance:complianceresult', args=[result.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '17.3.4')
        self.assertContains(response, 'behind by two releases')
        self.assertNotContains(response, 'Remediation')
