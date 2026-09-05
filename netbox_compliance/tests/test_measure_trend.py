from datetime import date
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ..choices import ComplianceMeasureCategoryChoices, ComplianceMeasureSeverityChoices, ComplianceResultStatusChoices
from ..models import ComplianceMeasure, ComplianceResult, MeasureAssignment
from ..services import generate_snapshots_for_period, measure_adherence_matrix, overall_compliance_trend
from .base import ComplianceTestMixin


class MeasureAdherenceMatrixTest(ComplianceTestMixin, TestCase):
    """services.measure_adherence_matrix / overall_compliance_trend -- the aggregation
    behind the Measure Adherence Trend report (views/reports.py)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = ComplianceMeasure.objects.create(
            name='Measure1', slug='measure1',
            category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH,
        )

    def _snapshot(self, status, *, site=None, role=None, period=date(2026, 6, 1)):
        device = self.make_device(site=site or self.site, role=role or self.device_role)
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=status, timestamp=timezone.now(), source='test',
        )
        return device

    def test_pct_improves_across_periods_as_devices_move_from_fail_to_pass(self):
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)
        result = ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.FAIL,
            timestamp=timezone.now(), source='test',
        )
        generate_snapshots_for_period(date(2026, 5, 1))

        # Same device, same measure -- it gets fixed between snapshot runs, same as a
        # real device improving over time (see SnapshotIdempotencyTest's own use of
        # in-place ComplianceResult updates rather than delete+recreate).
        result.status = ComplianceResultStatusChoices.PASS
        result.timestamp = timezone.now()
        result.save()
        generate_snapshots_for_period(date(2026, 6, 1))

        periods, rows = measure_adherence_matrix(periods=[date(2026, 5, 1), date(2026, 6, 1)])

        self.assertEqual(periods, [date(2026, 5, 1), date(2026, 6, 1)])
        row = next(r for r in rows if r['measure'] == 'measure1')
        self.assertEqual(row['cells'][0]['pct'], 0.0)
        self.assertEqual(row['cells'][0]['color'], 'red')
        self.assertEqual(row['cells'][1]['pct'], 100.0)
        self.assertEqual(row['cells'][1]['color'], 'green')

    def test_period_with_no_snapshot_yet_is_grey_not_missing(self):
        self._snapshot(ComplianceResultStatusChoices.PASS, period=date(2026, 6, 1))
        generate_snapshots_for_period(date(2026, 6, 1))

        periods, rows = measure_adherence_matrix(periods=[date(2026, 5, 1), date(2026, 6, 1)])

        row = next(r for r in rows if r['measure'] == 'measure1')
        self.assertIsNone(row['cells'][0]['pct'])
        self.assertEqual(row['cells'][0]['color'], 'grey')
        self.assertEqual(row['cells'][1]['pct'], 100.0)

    def test_site_filter_scopes_to_snapshot_site_not_live_device_site(self):
        device = self._snapshot(ComplianceResultStatusChoices.PASS, site=self.site2)
        generate_snapshots_for_period(date(2026, 6, 1))
        device.site = self.site  # move the device after the snapshot was taken
        device.save()

        periods, rows = measure_adherence_matrix(site_id=self.site2.pk, periods=[date(2026, 6, 1)])
        self.assertEqual(rows[0]['cells'][0]['pct'], 100.0)

        periods, rows = measure_adherence_matrix(site_id=self.site.pk, periods=[date(2026, 6, 1)])
        self.assertEqual(rows, [])

    def test_overall_compliance_trend_counts_fully_compliant_devices(self):
        self._snapshot(ComplianceResultStatusChoices.PASS)
        self._snapshot(ComplianceResultStatusChoices.FAIL)
        generate_snapshots_for_period(date(2026, 6, 1))

        rows = overall_compliance_trend(periods=[date(2026, 6, 1)])

        self.assertEqual(rows[0]['total'], 2)
        self.assertEqual(rows[0]['compliant_count'], 1)
        self.assertEqual(rows[0]['pct'], 50.0)


class MeasureAdherenceTrendViewTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = ComplianceMeasure.objects.create(
            name='Measure1', slug='measure1',
            category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH,
        )

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(username='tester', password='pw')
        self.client.force_login(self.user)

    def _url(self, **params):
        url = reverse('plugins:netbox_compliance:measure_trend_report')
        if params:
            url += '?' + urlencode(params, doseq=True)
        return url

    def test_no_snapshots_shows_empty_state(self):
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No compliance snapshots yet')

    def test_renders_measure_row_with_pass_rate(self):
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now(), source='test',
        )
        generate_snapshots_for_period(date(2026, 6, 1))

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Measure1')
        self.assertContains(response, '100.0%')

    def test_csv_export(self):
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now(), source='test',
        )
        generate_snapshots_for_period(date(2026, 6, 1))

        response = self.client.get(self._url(export='csv'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode()
        self.assertIn('Measure1', content)
        self.assertIn('100.0', content)

    def test_anonymous_user_is_redirected(self):
        self.client.logout()

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 302)
