from datetime import date

from django.test import TestCase
from django.utils import timezone

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceResultStatusChoices,
)
from ..models import ComplianceMeasure, ComplianceResult, ComplianceSnapshot, MeasureAssignment
from ..services import generate_snapshots_for_period
from .base import ComplianceTestMixin


class SnapshotIdempotencyTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = ComplianceMeasure.objects.create(
            name='Measure1', slug='measure1',
            category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH,
        )

    def test_regenerating_a_period_replaces_existing_snapshots(self):
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now(), source='test',
        )
        period = date(2026, 6, 1)

        count1 = generate_snapshots_for_period(period)
        self.assertEqual(count1, 1)
        self.assertEqual(ComplianceSnapshot.objects.filter(period=period).count(), 1)
        first_id = ComplianceSnapshot.objects.get(period=period).pk

        # Change the underlying data, then regenerate -- should replace, not duplicate.
        ComplianceResult.objects.create(
            device=device, measure=self.measure, status=ComplianceResultStatusChoices.FAIL,
            timestamp=timezone.now(), source='test',
        )
        count2 = generate_snapshots_for_period(period)

        self.assertEqual(count2, 1)
        self.assertEqual(ComplianceSnapshot.objects.filter(period=period).count(), 1)
        snapshot = ComplianceSnapshot.objects.get(period=period)
        self.assertNotEqual(snapshot.pk, first_id)
        self.assertFalse(snapshot.compliant)

    def test_device_with_no_effective_measures_is_skipped(self):
        self.make_device()  # no assignments at all
        period = date(2026, 6, 1)

        count = generate_snapshots_for_period(period)

        self.assertEqual(count, 0)
