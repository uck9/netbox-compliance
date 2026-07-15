from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from ..choices import ComplianceMeasureCategoryChoices, ComplianceMeasureSeverityChoices
from ..models import ComplianceExemption, ComplianceMeasure, CompliancePackage, PackageAssignment
from .base import ComplianceTestMixin


def make_measure(name='Measure1', slug='measure1'):
    return ComplianceMeasure.objects.create(
        name=name,
        slug=slug,
        category=ComplianceMeasureCategoryChoices.SECURITY,
        severity=ComplianceMeasureSeverityChoices.HIGH,
    )


class PackageAssignmentScopeTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.package = CompliancePackage.objects.create(name='Package1', slug='package1', status='active')

    def test_no_scope_set_is_invalid(self):
        assignment = PackageAssignment(package=self.package)
        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_two_scopes_set_is_invalid(self):
        assignment = PackageAssignment(package=self.package, site=self.site, platform=self.platform)
        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_exactly_one_scope_is_valid(self):
        assignment = PackageAssignment(package=self.package, site=self.site)
        assignment.full_clean()  # should not raise


class ComplianceExemptionScopeTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = make_measure()

    def test_no_scope_set_is_invalid(self):
        exemption = ComplianceExemption(measure=self.measure, justification='because')
        with self.assertRaises(ValidationError):
            exemption.full_clean()

    def test_two_scopes_set_is_invalid(self):
        exemption = ComplianceExemption(
            measure=self.measure, justification='because', site=self.site, site_group=self.site_group,
        )
        with self.assertRaises(ValidationError):
            exemption.full_clean()

    def test_valid_until_before_valid_from_is_invalid(self):
        exemption = ComplianceExemption(
            measure=self.measure, justification='because', site=self.site,
            valid_from=date.today(), valid_until=date.today() - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            exemption.full_clean()

    def test_is_active_property(self):
        active = ComplianceExemption.objects.create(
            measure=self.measure, justification='because', site=self.site,
            valid_from=date.today() - timedelta(days=10), valid_until=None,
        )
        self.assertTrue(active.is_active)

        expired = ComplianceExemption.objects.create(
            measure=self.measure, justification='because', site=self.site2,
            valid_from=date.today() - timedelta(days=30), valid_until=date.today() - timedelta(days=1),
        )
        self.assertFalse(expired.is_active)

        future = ComplianceExemption.objects.create(
            measure=self.measure, justification='because', tag=None, device=self.make_device(),
            valid_from=date.today() + timedelta(days=1),
        )
        self.assertFalse(future.is_active)
