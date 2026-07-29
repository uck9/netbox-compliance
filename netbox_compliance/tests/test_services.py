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
from ..services import (
    devices_for_package,
    devices_matching_assignment_scope,
    devices_with_effective_measures,
    get_effective_measures,
    score_device,
    score_group,
)
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

    def test_package_measure_via_parent_platform_scope(self):
        from dcim.models import Platform

        child_platform = Platform.objects.create(name='ChildPlatform', slug='child-platform', parent=self.platform)
        device = self.make_device(platform=child_platform)
        PackageAssignment.objects.create(package=self.package, platform=self.platform)

        effective = get_effective_measures(device)

        self.assertIn(self.package, effective['packages'])
        self.assertEqual([row.measure for row in effective['packages'][self.package]], [self.measure1])

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

    def test_package_level_exemption_via_device_drops_whole_package_from_platform_assignment(self):
        """The motivating case: a package assigned broadly by platform (so every device with
        that platform, or a child platform, gets it -- see test_package_measure_via_parent_platform_scope
        above) needs to be excludable for one specific device without touching the assignment
        itself. A package-level ComplianceExemption scoped to just that device does this."""
        from dcim.models import Platform

        child_platform = Platform.objects.create(name='ChildPlatform2', slug='child-platform-2', parent=self.platform)
        device = self.make_device(platform=child_platform)
        PackageAssignment.objects.create(package=self.package, platform=self.platform)
        ComplianceExemption.objects.create(package=self.package, device=device, justification='opted out')

        effective = get_effective_measures(device)

        self.assertEqual(effective['packages'], {})
        self.assertEqual(len(effective['exemptions_applied']), 1)
        self.assertEqual(effective['exemptions_applied'][0].package, self.package)

    def test_package_level_exemption_does_not_affect_other_devices(self):
        from dcim.models import Platform

        child_platform = Platform.objects.create(name='ChildPlatform3', slug='child-platform-3', parent=self.platform)
        exempted_device = self.make_device(platform=child_platform)
        other_device = self.make_device(platform=child_platform)
        PackageAssignment.objects.create(package=self.package, platform=self.platform)
        ComplianceExemption.objects.create(package=self.package, device=exempted_device, justification='opted out')

        self.assertEqual(get_effective_measures(exempted_device)['packages'], {})
        self.assertIn(self.package, get_effective_measures(other_device)['packages'])

    def test_tenant_scoped_exemption(self):
        from tenancy.models import Tenant

        tenant = Tenant.objects.create(name='Tenant1', slug='tenant1')
        device = self.make_device(tenant=tenant)
        MeasureAssignment.objects.create(device=device, measure=self.measure2, weight=1)
        ComplianceExemption.objects.create(measure=self.measure2, tenant=tenant, justification='tenant waiver')

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


class AssignmentScopeDeviceResolutionTest(ComplianceTestMixin, TestCase):
    """Reverse direction of test_package_measure_via_parent_platform_scope above (device ->
    assignment): given an assignment, which devices does it resolve to. Regression coverage for
    a real bug where the CompliancePackage detail view's device count (and, before the shared
    `devices_matching_assignment_scope` helper existed, `devices_with_effective_measures` had
    its own separately-written copy of this logic) matched a platform-scoped assignment against
    only devices with that *exact* platform, silently excluding every child platform -- e.g. a
    package assigned to the parent 'IOS XE' platform showing ~26 matched devices instead of the
    ~3400 real IOS XE devices, since almost none of them use the bare parent platform directly."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from dcim.models import Platform

        cls.child_platform = Platform.objects.create(name='ChildPlatform', slug='child-platform', parent=cls.platform)
        cls.package = CompliancePackage.objects.create(
            name='Package1', slug='package1', status=CompliancePackageStatusChoices.ACTIVE,
        )

    def test_platform_scope_matches_child_platform_devices(self):
        parent_device = self.make_device(platform=self.platform)
        child_device = self.make_device(platform=self.child_platform)
        other_device = self.make_device()  # no platform at all -- must not match
        assignment = PackageAssignment.objects.create(package=self.package, platform=self.platform)

        matched_ids = set(devices_matching_assignment_scope(assignment).values_list('pk', flat=True))

        self.assertEqual(matched_ids, {parent_device.pk, child_device.pk})
        self.assertNotIn(other_device.pk, matched_ids)

    def test_devices_with_effective_measures_includes_child_platform_devices(self):
        child_device = self.make_device(platform=self.child_platform)
        make_measure('measure-scope')  # unused directly; package needs no measures to matter here
        PackageAssignment.objects.create(package=self.package, platform=self.platform)

        result_ids = set(devices_with_effective_measures().values_list('pk', flat=True))

        self.assertIn(child_device.pk, result_ids)

    def test_devices_for_package_unions_multiple_assignments_and_includes_child_platforms(self):
        platform_device = self.make_device(platform=self.child_platform)
        role_device = self.make_device(role=self.device_role2)
        unrelated_device = self.make_device()
        PackageAssignment.objects.create(package=self.package, platform=self.platform)
        PackageAssignment.objects.create(package=self.package, device_role=self.device_role2)

        result_ids = set(devices_for_package(self.package).values_list('pk', flat=True))

        self.assertEqual(result_ids, {platform_device.pk, role_device.pk})
        self.assertNotIn(unrelated_device.pk, result_ids)

    def test_devices_for_package_excludes_device_level_package_exemption(self):
        device = self.make_device(platform=self.child_platform)
        other_device = self.make_device(platform=self.child_platform)
        PackageAssignment.objects.create(package=self.package, platform=self.platform)
        ComplianceExemption.objects.create(package=self.package, device=device, justification='opted out')

        result_ids = set(devices_for_package(self.package).values_list('pk', flat=True))

        self.assertNotIn(device.pk, result_ids)
        self.assertIn(other_device.pk, result_ids)

    def test_devices_for_package_excludes_tenant_level_package_exemption(self):
        """The reported bug: excluding a package by tenant left the device still showing up in
        the Devices tab, because devices_for_package originally ignored exemptions entirely."""
        from tenancy.models import Tenant

        tenant = Tenant.objects.create(name='ExcludedTenant', slug='excluded-tenant')
        tenant_device = self.make_device(platform=self.child_platform, tenant=tenant)
        other_device = self.make_device(platform=self.child_platform)
        PackageAssignment.objects.create(package=self.package, platform=self.platform)
        ComplianceExemption.objects.create(package=self.package, tenant=tenant, justification='tenant opted out')

        result_ids = set(devices_for_package(self.package).values_list('pk', flat=True))

        self.assertNotIn(tenant_device.pk, result_ids)
        self.assertIn(other_device.pk, result_ids)

    def test_devices_for_package_ignores_expired_exemption(self):
        from datetime import date, timedelta as td

        device = self.make_device(platform=self.child_platform)
        PackageAssignment.objects.create(package=self.package, platform=self.platform)
        ComplianceExemption.objects.create(
            package=self.package, device=device, justification='expired',
            valid_from=date.today() - td(days=30), valid_until=date.today() - td(days=1),
        )

        result_ids = set(devices_for_package(self.package).values_list('pk', flat=True))

        self.assertIn(device.pk, result_ids)

    def test_devices_for_package_ignores_measure_level_exemption(self):
        """Documented limitation: a measure-level (not package-level) exemption doesn't remove
        the device from scope here, even if it happens to cover every measure in the package --
        devices_for_package only reacts to package-level exemptions."""
        measure = make_measure('package-scope-measure')
        device = self.make_device(platform=self.child_platform)
        PackageMeasure.objects.create(package=self.package, measure=measure, weight=1, required=True)
        PackageAssignment.objects.create(package=self.package, platform=self.platform)
        ComplianceExemption.objects.create(measure=measure, device=device, justification='measure-level only')

        result_ids = set(devices_for_package(self.package).values_list('pk', flat=True))

        self.assertIn(device.pk, result_ids)


class DeviceEligibilityTest(ComplianceTestMixin, TestCase):
    """Stack members and unreachable devices: compliance is tracked against a Virtual Chassis's
    single master member, not every physical unit, and a device with no primary IP at all can
    never produce real collector results. `is_device_eligible_for_compliance` (single device) and
    `eligible_devices_qs` (bulk) implement this, wired into both `get_effective_measures` (so a
    non-master member's own compliance tab is empty too, not just hidden from lists) and
    `devices_matching_assignment_scope` (so package scope/device-count/Devices-tab lists agree)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = make_measure('eligibility-measure')
        cls.package = CompliancePackage.objects.create(
            name='EligPkg', slug='eligpkg', status=CompliancePackageStatusChoices.ACTIVE,
        )
        PackageMeasure.objects.create(package=cls.package, measure=cls.measure, weight=1, required=True)

    def _make_vc(self, name='VC1'):
        from dcim.models import VirtualChassis

        return VirtualChassis.objects.create(name=name)

    def test_device_with_no_primary_ip_has_no_effective_measures(self):
        device = self.make_device(primary_ip=False, site=self.site)
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)

        effective = get_effective_measures(device)

        self.assertEqual(effective['direct'], [])
        self.assertEqual(effective['packages'], {})

    def test_device_with_no_primary_ip_excluded_from_package_scope(self):
        device = self.make_device(primary_ip=False, platform=self.platform)
        PackageAssignment.objects.create(package=self.package, platform=self.platform)

        result_ids = set(devices_for_package(self.package).values_list('pk', flat=True))

        self.assertNotIn(device.pk, result_ids)

    def test_non_master_vc_member_has_no_effective_measures(self):
        vc = self._make_vc()
        master = self.make_device(name='master-device')
        member = self.make_device(name='member-device')
        master.virtual_chassis = vc
        master.vc_position = 1
        master.save()
        member.virtual_chassis = vc
        member.vc_position = 2
        member.save()
        vc.master = master
        vc.save()
        MeasureAssignment.objects.create(device=member, measure=self.measure, weight=1)

        self.assertEqual(get_effective_measures(member)['direct'], [])

    def test_vc_master_still_has_effective_measures(self):
        vc = self._make_vc()
        master = self.make_device(name='master-device2')
        master.virtual_chassis = vc
        master.vc_position = 1
        master.save()
        vc.master = master
        vc.save()
        MeasureAssignment.objects.create(device=master, measure=self.measure, weight=1)

        self.assertEqual(len(get_effective_measures(master)['direct']), 1)

    def test_non_master_vc_member_excluded_from_package_scope_master_included(self):
        vc = self._make_vc()
        master = self.make_device(name='master-device3', platform=self.platform)
        member = self.make_device(name='member-device3', platform=self.platform)
        master.virtual_chassis = vc
        master.vc_position = 1
        master.save()
        member.virtual_chassis = vc
        member.vc_position = 2
        member.save()
        vc.master = master
        vc.save()
        PackageAssignment.objects.create(package=self.package, platform=self.platform)

        result_ids = set(devices_for_package(self.package).values_list('pk', flat=True))

        self.assertIn(master.pk, result_ids)
        self.assertNotIn(member.pk, result_ids)

    def test_vc_with_no_master_designated_fails_open_all_members_eligible(self):
        """Explicit product decision: an unconfigured stack (no master set yet) must not silently
        vanish from compliance coverage -- every member stays individually eligible until someone
        designates a master, rather than the whole stack going dark."""
        vc = self._make_vc()
        member1 = self.make_device(name='nomaster-member1')
        member2 = self.make_device(name='nomaster-member2')
        member1.virtual_chassis = vc
        member1.vc_position = 1
        member1.save()
        member2.virtual_chassis = vc
        member2.vc_position = 2
        member2.save()
        MeasureAssignment.objects.create(device=member1, measure=self.measure, weight=1)
        MeasureAssignment.objects.create(device=member2, measure=self.measure, weight=1)

        self.assertEqual(len(get_effective_measures(member1)['direct']), 1)
        self.assertEqual(len(get_effective_measures(member2)['direct']), 1)

    def test_device_with_no_vc_at_all_is_unaffected(self):
        """The firewall-HA-pair case: devices with no Virtual Chassis membership at all have no
        'master' concept to apply, so each one is independently eligible on its own -- same as
        every other test in this file relies on via make_device()'s default primary_ip=True."""
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=self.measure, weight=1)

        self.assertEqual(len(get_effective_measures(device)['direct']), 1)
