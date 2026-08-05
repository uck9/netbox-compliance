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
