from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureResultTypeChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceResultStatusChoices,
    CompliancePackageStatusChoices,
)
from ..models import ComplianceMeasure, CompliancePackage, ComplianceResult, MeasureAssignment, PackageAssignment, PackageMeasure
from ..services import get_effective_measures, package_traffic_light, score_device, score_group
from .base import ComplianceTestMixin

VALUE_MAP = {
    'target': {'label': 'Target version', 'color': 'green', 'credit': 100},
    'accepted': {'label': 'Accepted version', 'color': 'green', 'credit': 90},
    'upgrade_required': {'label': 'Upgrade required', 'color': 'orange', 'credit': 40},
    'unsupported': {'label': 'Unsupported', 'color': 'red', 'credit': 0},
}


def make_measure(slug, result_type=ComplianceMeasureResultTypeChoices.BOOLEAN, max_result_age_days=35, **kwargs):
    return ComplianceMeasure.objects.create(
        name=slug,
        slug=slug,
        category=ComplianceMeasureCategoryChoices.SECURITY,
        severity=kwargs.pop('severity', ComplianceMeasureSeverityChoices.HIGH),
        max_result_age_days=max_result_age_days,
        result_type=result_type,
        **kwargs,
    )


class ValueMapValidationTest(TestCase):
    def test_enum_requires_nonempty_value_map(self):
        measure = ComplianceMeasure(
            name='m', slug='m', category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH, result_type=ComplianceMeasureResultTypeChoices.ENUM,
        )
        with self.assertRaises(ValidationError):
            measure.clean()

    def test_enum_value_map_bad_color_rejected(self):
        measure = ComplianceMeasure(
            name='m', slug='m', category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH, result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map={'x': {'label': 'X', 'color': 'purple', 'credit': 100}},
        )
        with self.assertRaises(ValidationError):
            measure.clean()

    def test_enum_value_map_missing_credit_rejected(self):
        measure = ComplianceMeasure(
            name='m', slug='m', category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH, result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map={'x': {'label': 'X', 'color': 'green'}},
        )
        with self.assertRaises(ValidationError):
            measure.clean()

    def test_enum_value_map_credit_out_of_range_rejected(self):
        measure = ComplianceMeasure(
            name='m', slug='m', category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH, result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map={'x': {'label': 'X', 'color': 'green', 'credit': 150}},
        )
        with self.assertRaises(ValidationError):
            measure.clean()

    def test_enum_valid_value_map_passes(self):
        measure = ComplianceMeasure(
            name='m', slug='m', category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH, result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map=VALUE_MAP,
        )
        measure.clean()  # should not raise

    def test_percentage_requires_pass_threshold(self):
        measure = ComplianceMeasure(
            name='m', slug='m', category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH, result_type=ComplianceMeasureResultTypeChoices.PERCENTAGE,
        )
        with self.assertRaises(ValidationError):
            measure.clean()

    def test_boolean_rejects_pass_threshold_and_value_map(self):
        measure = ComplianceMeasure(
            name='m', slug='m', category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH, result_type=ComplianceMeasureResultTypeChoices.BOOLEAN,
            pass_threshold=Decimal('80.00'),
        )
        with self.assertRaises(ValidationError):
            measure.clean()

    def test_enum_rejects_pass_threshold(self):
        measure = ComplianceMeasure(
            name='m', slug='m', category=ComplianceMeasureCategoryChoices.SECURITY,
            severity=ComplianceMeasureSeverityChoices.HIGH, result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map=VALUE_MAP, pass_threshold=Decimal('80.00'),
        )
        with self.assertRaises(ValidationError):
            measure.clean()


class CreditScoringTest(ComplianceTestMixin, TestCase):
    def _post(self, device, measure, status=None, value=None):
        ComplianceResult.objects.create(
            device=device, measure=measure, status=status, value=value,
            timestamp=timezone.now(), source='test',
        )

    def test_boolean_only_package_score_unchanged_from_legacy_formula(self):
        package = CompliancePackage.objects.create(name='Pkg', slug='pkg', status=CompliancePackageStatusChoices.ACTIVE)
        measure_pass = make_measure('m-pass')
        measure_fail = make_measure('m-fail')
        PackageMeasure.objects.create(package=package, measure=measure_pass, weight=3, required=True)
        PackageMeasure.objects.create(package=package, measure=measure_fail, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post(device, measure_pass, status=ComplianceResultStatusChoices.PASS, value='true')
        self._post(device, measure_fail, status=ComplianceResultStatusChoices.FAIL, value='false')

        scoring = score_device(device)

        self.assertEqual(scoring['overall_score'], Decimal('75.00'))
        self.assertFalse(scoring['compliant'])

    def test_percentage_measure_credit_equals_clamped_value(self):
        measure = make_measure('m-pct', result_type=ComplianceMeasureResultTypeChoices.PERCENTAGE, pass_threshold=Decimal('90.00'))
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)
        self._post(device, measure, status=ComplianceResultStatusChoices.FAIL, value='87.3')

        effective = get_effective_measures(device)
        row = effective['direct'][0]

        self.assertEqual(row.credit, 87)
        self.assertEqual(row.display_color, 'orange')  # >= threshold-20 (70) but < threshold (90)

    def test_enum_measure_credit_from_value_map(self):
        measure = make_measure('m-enum', result_type=ComplianceMeasureResultTypeChoices.ENUM, value_map=VALUE_MAP)
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)
        self._post(device, measure, status=ComplianceResultStatusChoices.FAIL, value='upgrade_required')

        effective = get_effective_measures(device)
        row = effective['direct'][0]

        self.assertEqual(row.credit, 40)
        self.assertEqual(row.display_color, 'orange')
        self.assertEqual(row.display_label, 'Upgrade required')

    def test_mixed_type_package_weighted_credit_score(self):
        package = CompliancePackage.objects.create(name='Mix', slug='mix', status=CompliancePackageStatusChoices.ACTIVE)
        bool_measure = make_measure('m-mix-bool')
        pct_measure = make_measure('m-mix-pct', result_type=ComplianceMeasureResultTypeChoices.PERCENTAGE, pass_threshold=Decimal('100.00'))
        PackageMeasure.objects.create(package=package, measure=bool_measure, weight=1, required=True)
        PackageMeasure.objects.create(package=package, measure=pct_measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post(device, bool_measure, status=ComplianceResultStatusChoices.PASS, value='true')
        self._post(device, pct_measure, status=ComplianceResultStatusChoices.FAIL, value='50')

        scoring = score_device(device)

        # (1*100 + 1*50) / (2*100) * 100 = 75
        self.assertEqual(scoring['overall_score'], Decimal('75.00'))

    def test_not_applicable_excluded_from_numerator_and_denominator(self):
        package = CompliancePackage.objects.create(name='NA', slug='na', status=CompliancePackageStatusChoices.ACTIVE)
        measure_pass = make_measure('m-na-pass')
        measure_na = make_measure('m-na-na')
        PackageMeasure.objects.create(package=package, measure=measure_pass, weight=1, required=True)
        PackageMeasure.objects.create(package=package, measure=measure_na, weight=99, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post(device, measure_pass, status=ComplianceResultStatusChoices.PASS, value='true')
        self._post(device, measure_na, status=ComplianceResultStatusChoices.NOT_APPLICABLE)

        scoring = score_device(device)

        self.assertEqual(scoring['overall_score'], Decimal('100.00'))
        self.assertTrue(scoring['compliant'])

    def test_stale_and_error_credit_zero(self):
        measure = make_measure('m-stale', max_result_age_days=1)
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)
        self._post(device, measure, status=ComplianceResultStatusChoices.PASS, value='true')
        ComplianceResult.objects.filter(measure=measure).update(timestamp=timezone.now() - timezone.timedelta(days=10))

        effective = get_effective_measures(device)
        row = effective['direct'][0]

        self.assertTrue(row.stale)
        self.assertEqual(row.credit, 0)

        error_measure = make_measure('m-error')
        MeasureAssignment.objects.create(device=device, measure=error_measure, weight=1)
        self._post(device, error_measure, status=ComplianceResultStatusChoices.ERROR)

        effective = get_effective_measures(device)
        error_row = [r for r in effective['direct'] if r.measure == error_measure][0]
        self.assertEqual(error_row.credit, 0)

    def test_credit_based_compliant_flag_matches_all_pass_semantics(self):
        package = CompliancePackage.objects.create(name='Comp', slug='comp', status=CompliancePackageStatusChoices.ACTIVE)
        pct_measure = make_measure('m-comp-pct', result_type=ComplianceMeasureResultTypeChoices.PERCENTAGE, pass_threshold=Decimal('50.00'))
        PackageMeasure.objects.create(package=package, measure=pct_measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        # 100% is both "pass" (>=50 threshold) and full credit -- overall_score should hit exactly 100.
        self._post(device, pct_measure, status=ComplianceResultStatusChoices.PASS, value='100')

        scoring = score_device(device)

        self.assertEqual(scoring['overall_score'], Decimal('100.00'))
        self.assertTrue(scoring['compliant'])

    def test_score_group_zero_weight_guard(self):
        score, weight = score_group([])
        self.assertEqual(score, Decimal('100.00'))
        self.assertEqual(weight, 0)


class TrafficLightTest(ComplianceTestMixin, TestCase):
    def _post(self, device, measure, status, value=None):
        ComplianceResult.objects.create(
            device=device, measure=measure, status=status, value=value,
            timestamp=timezone.now(), source='test',
        )

    def _package(self, **kwargs):
        kwargs.setdefault('status', CompliancePackageStatusChoices.ACTIVE)
        return CompliancePackage.objects.create(name=f'pkg-{CompliancePackage.objects.count()}', slug=f'pkg-{CompliancePackage.objects.count()}', **kwargs)

    def test_grey_when_no_results(self):
        package = self._package()
        measure = make_measure('tl-pending')
        PackageMeasure.objects.create(package=package, measure=measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)

        self.assertEqual(package_traffic_light(device, package), 'grey')

    def test_grey_when_all_pending_or_stale(self):
        package = self._package()
        measure = make_measure('tl-stale', max_result_age_days=1)
        PackageMeasure.objects.create(package=package, measure=measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post(device, measure, ComplianceResultStatusChoices.PASS, value='true')
        ComplianceResult.objects.filter(measure=measure).update(timestamp=timezone.now() - timezone.timedelta(days=10))

        self.assertEqual(package_traffic_light(device, package), 'grey')

    def test_green_when_all_required_pass(self):
        package = self._package()
        measure = make_measure('tl-pass')
        PackageMeasure.objects.create(package=package, measure=measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post(device, measure, ComplianceResultStatusChoices.PASS, value='true')

        self.assertEqual(package_traffic_light(device, package), 'green')

    def test_red_on_critical_fail_true_forces_red_even_with_high_score(self):
        package = self._package(red_on_critical_fail=True, amber_threshold=Decimal('10.00'))
        good_measure = make_measure('tl-good', severity=ComplianceMeasureSeverityChoices.LOW)
        crit_measure = make_measure('tl-crit', severity=ComplianceMeasureSeverityChoices.CRITICAL)
        PackageMeasure.objects.create(package=package, measure=good_measure, weight=99, required=True)
        PackageMeasure.objects.create(package=package, measure=crit_measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post(device, good_measure, ComplianceResultStatusChoices.PASS, value='true')
        self._post(device, crit_measure, ComplianceResultStatusChoices.FAIL, value='false')

        self.assertEqual(package_traffic_light(device, package), 'red')

    def test_red_on_critical_fail_false_falls_through_to_amber_threshold(self):
        package = self._package(red_on_critical_fail=False, amber_threshold=Decimal('50.00'))
        good_measure = make_measure('tl-good2', severity=ComplianceMeasureSeverityChoices.LOW)
        crit_measure = make_measure('tl-crit2', severity=ComplianceMeasureSeverityChoices.CRITICAL)
        PackageMeasure.objects.create(package=package, measure=good_measure, weight=99, required=True)
        PackageMeasure.objects.create(package=package, measure=crit_measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post(device, good_measure, ComplianceResultStatusChoices.PASS, value='true')
        self._post(device, crit_measure, ComplianceResultStatusChoices.FAIL, value='false')

        # score = 99*100/(100*100) = 99 >= amber_threshold(50) -> amber, since red_on_critical_fail is off
        self.assertEqual(package_traffic_light(device, package), 'amber')

    def test_amber_when_score_above_threshold_with_only_low_severity_fail(self):
        package = self._package(red_on_critical_fail=True, amber_threshold=Decimal('50.00'))
        good_measure = make_measure('tl-good3', severity=ComplianceMeasureSeverityChoices.LOW)
        low_measure = make_measure('tl-low3', severity=ComplianceMeasureSeverityChoices.LOW)
        PackageMeasure.objects.create(package=package, measure=good_measure, weight=9, required=True)
        PackageMeasure.objects.create(package=package, measure=low_measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post(device, good_measure, ComplianceResultStatusChoices.PASS, value='true')
        self._post(device, low_measure, ComplianceResultStatusChoices.FAIL, value='false')

        self.assertEqual(package_traffic_light(device, package), 'amber')

    def test_red_when_score_below_amber_threshold(self):
        package = self._package(red_on_critical_fail=False, amber_threshold=Decimal('90.00'))
        good_measure = make_measure('tl-good4', severity=ComplianceMeasureSeverityChoices.LOW)
        low_measure = make_measure('tl-low4', severity=ComplianceMeasureSeverityChoices.LOW)
        PackageMeasure.objects.create(package=package, measure=good_measure, weight=1, required=True)
        PackageMeasure.objects.create(package=package, measure=low_measure, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=package, site=self.site)
        self._post(device, good_measure, ComplianceResultStatusChoices.PASS, value='true')
        self._post(device, low_measure, ComplianceResultStatusChoices.FAIL, value='false')

        # score = 50 < amber_threshold(90) -> red
        self.assertEqual(package_traffic_light(device, package), 'red')
