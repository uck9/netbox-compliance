from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceResultStatusChoices,
    CompliancePackageStatusChoices,
    EffectiveStatusChoices,
)
from ..models import (
    ComplianceExemption,
    ComplianceMeasure,
    CompliancePackage,
    ComplianceResult,
    MeasureAssignment,
    PackageAssignment,
    PackageMeasure,
)
from ..services import get_effective_measures, score_device, score_group
from .base import ComplianceTestMixin


def make_measure(slug, max_result_age_days=35):
    return ComplianceMeasure.objects.create(
        name=slug,
        slug=slug,
        category=ComplianceMeasureCategoryChoices.SECURITY,
        severity=ComplianceMeasureSeverityChoices.HIGH,
        max_result_age_days=max_result_age_days,
    )


class EffectiveMeasureResolutionTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure1 = make_measure('measure1')
        cls.measure2 = make_measure('measure2')
        cls.package = CompliancePackage.objects.create(
            name='Package1', slug='package1', status=CompliancePackageStatusChoices.ACTIVE,
        )
        PackageMeasure.objects.create(package=cls.package, measure=cls.measure1, weight=1, required=True)

    def test_direct_measure_is_effective(self):
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=self.measure2, weight=2)

        effective = get_effective_measures(device)

        self.assertEqual(len(effective['direct']), 1)
        self.assertEqual(effective['direct'][0].measure, self.measure2)
        self.assertEqual(effective['packages'], {})

    def test_package_measure_via_site_scope(self):
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=self.package, site=self.site)

        effective = get_effective_measures(device)

        self.assertIn(self.package, effective['packages'])
        self.assertEqual([row.measure for row in effective['packages'][self.package]], [self.measure1])

    def test_package_scoped_to_different_site_not_effective(self):
        device = self.make_device(site=self.site2)
        PackageAssignment.objects.create(package=self.package, site=self.site)

        effective = get_effective_measures(device)

        self.assertEqual(effective['packages'], {})

    def test_retired_package_not_effective(self):
        device = self.make_device(site=self.site)
        self.package.status = CompliancePackageStatusChoices.RETIRED
        self.package.save()
        PackageAssignment.objects.create(package=self.package, site=self.site)

        effective = get_effective_measures(device)

        self.assertEqual(effective['packages'], {})

    def test_device_level_exemption_removes_measure(self):
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=self.measure2, weight=1)
        ComplianceExemption.objects.create(measure=self.measure2, device=device, justification='waived')

        effective = get_effective_measures(device)

        self.assertEqual(effective['direct'], [])
        self.assertEqual(len(effective['exemptions_applied']), 1)
        self.assertEqual(effective['exemptions_applied'][0].measure, self.measure2)

    def test_expired_exemption_does_not_apply(self):
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=self.measure2, weight=1)
        ComplianceExemption.objects.create(
            measure=self.measure2, device=device, justification='waived',
            valid_from=timezone.now().date() - timedelta(days=30),
            valid_until=timezone.now().date() - timedelta(days=1),
        )

        effective = get_effective_measures(device)

        self.assertEqual(len(effective['direct']), 1)
        self.assertEqual(effective['exemptions_applied'], [])

    def test_scoped_exemption_via_site_group(self):
        device = self.make_device(site=self.site)  # site belongs to self.site_group
        MeasureAssignment.objects.create(device=device, measure=self.measure2, weight=1)
        ComplianceExemption.objects.create(
            measure=self.measure2, site_group=self.site_group, justification='regional waiver',
        )

        effective = get_effective_measures(device)

        self.assertEqual(effective['direct'], [])


class StalenessTest(ComplianceTestMixin, TestCase):
    def test_no_result_is_pending(self):
        measure = make_measure('measure-pending')
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)

        effective = get_effective_measures(device)

        self.assertEqual(effective['direct'][0].status, EffectiveStatusChoices.PENDING)

    def test_old_result_is_stale(self):
        measure = make_measure('measure-stale', max_result_age_days=10)
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=measure, status=ComplianceResultStatusChoices.PASS,
            timestamp=timezone.now() - timedelta(days=20), source='test',
        )

        effective = get_effective_measures(device)

        self.assertEqual(effective['direct'][0].status, EffectiveStatusChoices.STALE)
        self.assertTrue(effective['direct'][0].stale)

    def test_recent_result_uses_its_status(self):
        measure = make_measure('measure-fresh', max_result_age_days=10)
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=measure, status=ComplianceResultStatusChoices.FAIL,
            timestamp=timezone.now(), source='test',
        )

        effective = get_effective_measures(device)

        self.assertEqual(effective['direct'][0].status, EffectiveStatusChoices.FAIL)
        self.assertFalse(effective['direct'][0].stale)


class ScoringTest(ComplianceTestMixin, TestCase):
    def _post_result(self, device, measure, status):
        ComplianceResult.objects.create(device=device, measure=measure, status=status, timestamp=timezone.now(), source='test')

    def test_all_not_applicable_is_vacuously_compliant(self):
        measure = make_measure('measure-na')
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=5)
        self._post_result(device, measure, ComplianceResultStatusChoices.NOT_APPLICABLE)

        scoring = score_device(device)

        self.assertEqual(scoring['overall_score'], Decimal('100.00'))
        self.assertTrue(scoring['compliant'])

    def test_informational_only_measures_never_affect_score(self):
        package = CompliancePackage.objects.create(name='InfoPkg', slug='infopkg', status=CompliancePackageStatusChoices.ACTIVE)
        measure = make_measure('measure-info')
        PackageMeasure.objects.create(package=package, measure=measure, weight=10, required=False)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post_result(device, measure, ComplianceResultStatusChoices.FAIL)

        scoring = score_device(device)

        self.assertEqual(scoring['overall_score'], Decimal('100.00'))
        self.assertTrue(scoring['compliant'])

    def test_weighted_pass_fail(self):
        package = CompliancePackage.objects.create(name='Pkg', slug='pkg', status=CompliancePackageStatusChoices.ACTIVE)
        measure_pass = make_measure('measure-pass-w')
        measure_fail = make_measure('measure-fail-w')
        PackageMeasure.objects.create(package=package, measure=measure_pass, weight=3, required=True)
        PackageMeasure.objects.create(package=package, measure=measure_fail, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post_result(device, measure_pass, ComplianceResultStatusChoices.PASS)
        self._post_result(device, measure_fail, ComplianceResultStatusChoices.FAIL)

        scoring = score_device(device)

        self.assertEqual(scoring['overall_score'], Decimal('75.00'))
        self.assertFalse(scoring['compliant'])

    def test_score_group_zero_weight_guard(self):
        score, weight = score_group([])
        self.assertEqual(score, Decimal('100.00'))
        self.assertEqual(weight, 0)
