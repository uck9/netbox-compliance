from dcim.models import DeviceType, Manufacturer, Platform
from django.test import TestCase

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureResultTypeChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceResultStatusChoices,
)
from ..models import ComplianceMeasure, ComplianceResult
from ..services import SOFTWARE_VERSION_MEASURE_SLUG, evaluate_software_version
from .base import ComplianceTestMixin

# Matches the *live* measure's actual value_map keys (the legacy script's own
# vocabulary), not the naming-conventions doc's aspirational table -- see
# services.py's SOFTWARE_VERSION_KEY_* comment.
VALUE_MAP = {
    'target_active_version': {'label': 'Target Active Version', 'color': 'green', 'credit': 100},
    'accepted_active_version': {'label': 'Accepted Active Version', 'color': 'green', 'credit': 100},
    'required_upgrade': {'label': 'Required Upgrade', 'color': 'orange', 'credit': 0},
    'required_upgrade_retired': {'label': 'Required Upgrade - Retired Version', 'color': 'orange', 'credit': 0},
    'exempted': {'label': 'Exempted', 'color': 'green', 'credit': 100},
}

# Shape mirrors real live-instance data: a child-platform-scoped object with
# a `defaults.version_policy` baseline plus optional `roles`/
# `device_type_overrides` overrides. See platform "IOS XE - Routing - ASR1000
# Series" / "IOS XE - Routing - ISR 4000 Series" for the real-world originals.
PLATFORM_DATA = {
    'roles': {
        'router-sdwan': {
            'version_policy': {
                'retired_versions': {},
                'target_active_versions': ['17.9.8'],
                'accepted_active_versions': [],
            },
        },
    },
    'defaults': {
        'version_policy': {
            'retired_versions': {'16.12.1': 'End of vendor support'},
            'target_active_versions': ['17.12.3'],
            'accepted_active_versions': ['17.9.4a'],
        },
    },
    'policy_scope': 'child_platform',
    'schema_version': '1.0',
    'device_type_overrides': {},
}


def make_software_version_measure():
    return ComplianceMeasure.objects.create(
        name='Software Version', slug=SOFTWARE_VERSION_MEASURE_SLUG,
        category=ComplianceMeasureCategoryChoices.OPERATIONAL,
        severity=ComplianceMeasureSeverityChoices.HIGH,
        result_type=ComplianceMeasureResultTypeChoices.ENUM,
        value_map=VALUE_MAP,
        required_detail_keys=['running', 'target'],
    )


class EvaluateSoftwareVersionTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = make_software_version_measure()
        cls.versioned_platform = Platform.objects.create(
            name='VersionedPlatform', slug='versioned-platform',
            custom_field_data={'software_version_management': PLATFORM_DATA},
        )

    def test_no_measure_configured_writes_nothing(self):
        ComplianceMeasure.objects.filter(slug=SOFTWARE_VERSION_MEASURE_SLUG).delete()
        device = self.make_device(platform=self.versioned_platform)
        device.custom_field_data = {'software_version': '17.12.3'}

        result = evaluate_software_version(device)

        self.assertIsNone(result)
        self.assertEqual(ComplianceResult.objects.count(), 0)

    def test_no_platform_is_not_applicable(self):
        device = self.make_device()
        device.custom_field_data = {'software_version': '17.12.3'}

        result = evaluate_software_version(device)

        self.assertEqual(result.status, ComplianceResultStatusChoices.NOT_APPLICABLE)
        self.assertIsNone(result.value)

    def test_platform_without_version_data_is_error(self):
        platform = Platform.objects.create(name='NoDataPlatform', slug='no-data-platform')
        device = self.make_device(platform=platform)
        device.custom_field_data = {'software_version': '17.12.3'}

        result = evaluate_software_version(device)

        self.assertEqual(result.status, ComplianceResultStatusChoices.ERROR)

    def test_parent_platform_with_no_version_policy_is_error(self):
        # Parent-level platforms (policy_scope=parent_platform) carry only
        # eol/parser/vulnerabilities -- no defaults.version_policy at all.
        platform = Platform.objects.create(
            name='ParentOnlyPlatform', slug='parent-only-platform',
            custom_field_data={'software_version_management': {
                'policy_scope': 'parent_platform', 'schema_version': '1.0',
                'eol': {'by_train': {}}, 'parser': {}, 'vulnerabilities': {},
            }},
        )
        device = self.make_device(platform=platform)
        device.custom_field_data = {'software_version': '17.12.3'}

        result = evaluate_software_version(device)

        self.assertEqual(result.status, ComplianceResultStatusChoices.ERROR)

    def test_no_running_version_is_error_not_an_enum_value(self):
        # No key in the live value_map represents "no version reported" --
        # this is a data-availability gap, not a classifiable state.
        device = self.make_device(platform=self.versioned_platform)

        result = evaluate_software_version(device)

        self.assertIsNone(result.value)
        self.assertEqual(result.status, ComplianceResultStatusChoices.ERROR)
        self.assertEqual(result.details['running'], None)
        self.assertEqual(result.details['target'], '17.12.3')

    def test_target_version_is_on_target(self):
        device = self.make_device(platform=self.versioned_platform)
        device.custom_field_data = {'software_version': '17.12.3'}

        result = evaluate_software_version(device)

        self.assertEqual(result.value, 'target_active_version')
        self.assertEqual(result.status, ComplianceResultStatusChoices.PASS)
        self.assertEqual(result.details, {'running': '17.12.3', 'target': '17.12.3'})

    def test_accepted_version_is_accepted(self):
        device = self.make_device(platform=self.versioned_platform)
        device.custom_field_data = {'software_version': '17.9.4a'}

        result = evaluate_software_version(device)

        self.assertEqual(result.value, 'accepted_active_version')
        self.assertEqual(result.status, ComplianceResultStatusChoices.PASS)

    def test_retired_version_is_upgrade_required_retired(self):
        device = self.make_device(platform=self.versioned_platform)
        device.custom_field_data = {'software_version': '16.12.1'}

        result = evaluate_software_version(device)

        self.assertEqual(result.value, 'required_upgrade_retired')
        self.assertEqual(result.status, ComplianceResultStatusChoices.FAIL)

    def test_unmatched_version_is_upgrade_required(self):
        device = self.make_device(platform=self.versioned_platform)
        device.custom_field_data = {'software_version': '17.6.1'}

        result = evaluate_software_version(device)

        self.assertEqual(result.value, 'required_upgrade')
        self.assertEqual(result.status, ComplianceResultStatusChoices.FAIL)

    def test_role_override_applies_for_matching_role(self):
        device = self.make_device(platform=self.versioned_platform, role=self.device_role2)
        self.device_role2.slug = 'router-sdwan'
        self.device_role2.save()
        device.custom_field_data = {'software_version': '17.9.8'}

        result = evaluate_software_version(device)

        self.assertEqual(result.value, 'target_active_version')
        self.assertEqual(result.details['target'], '17.9.8')

    def test_device_type_override_used_even_when_role_override_disagrees(self):
        manufacturer = Manufacturer.objects.create(name='OverrideMfr2', slug='override-mfr-2')
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model='ASR1001-X', slug='asr1001-x-test-2',
        )
        platform = Platform.objects.create(
            name='OverridePlatform2', slug='override-platform-2',
            custom_field_data={'software_version_management': {
                **PLATFORM_DATA,
                'device_type_overrides': {
                    'ASR1001-X': {
                        'version_policy': {
                            'retired_versions': {},
                            'target_active_versions': ['1.2.3'],
                            'accepted_active_versions': [],
                        },
                    },
                },
            }},
        )
        self.device_role2.slug = 'router-sdwan'
        self.device_role2.save()
        device = self.make_device(platform=platform, role=self.device_role2, device_type=device_type)
        device.custom_field_data = {'software_version': '1.2.3'}

        result = evaluate_software_version(device)

        # role override's target is 17.9.8; device_type override's target is
        # 1.2.3 -- device_type must win.
        self.assertEqual(result.value, 'target_active_version')
        self.assertEqual(result.details['target'], '1.2.3')

    def test_device_type_level_version_data_is_never_consulted(self):
        # device_type also carries software_version_management (same custom
        # field exists on both models) -- it must be ignored entirely, since
        # platform is the single source of truth going forward.
        self.device_type.custom_field_data = {'software_version_management': {
            'defaults': {'version_policy': {
                'retired_versions': {}, 'target_active_versions': ['1.0.0'], 'accepted_active_versions': [],
            }},
            'policy_scope': 'child_platform', 'schema_version': '1.0',
        }}
        self.device_type.save()
        device = self.make_device(platform=self.versioned_platform)
        device.custom_field_data = {'software_version': '17.12.3'}

        result = evaluate_software_version(device)

        self.assertEqual(result.value, 'target_active_version')
        self.assertEqual(result.details['target'], '17.12.3')


class SoftwareVersionSignalTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.measure = make_software_version_measure()
        cls.versioned_platform = Platform.objects.create(
            name='VersionedPlatform2', slug='versioned-platform-2',
            custom_field_data={'software_version_management': PLATFORM_DATA},
        )

    def test_saving_device_with_new_software_version_creates_result(self):
        device = self.make_device(platform=self.versioned_platform)
        self.assertEqual(ComplianceResult.objects.filter(device=device, measure=self.measure).count(), 0)

        device.custom_field_data = {'software_version': '17.12.3'}
        device.save()

        results = ComplianceResult.objects.filter(device=device, measure=self.measure)
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().value, 'target_active_version')

    def test_changing_software_version_creates_a_new_result(self):
        device = self.make_device(platform=self.versioned_platform)
        device.custom_field_data = {'software_version': '17.12.3'}
        device.save()

        device.custom_field_data = {'software_version': '16.12.1'}
        device.save()

        results = ComplianceResult.objects.filter(device=device, measure=self.measure).order_by('-timestamp')
        self.assertEqual(results.count(), 2)
        self.assertEqual(results.first().value, 'required_upgrade_retired')

    def test_unrelated_field_change_does_not_create_a_new_result(self):
        device = self.make_device(platform=self.versioned_platform)
        device.custom_field_data = {'software_version': '17.12.3'}
        device.save()

        device.name = f'{device.name}-renamed'
        device.save()

        self.assertEqual(ComplianceResult.objects.filter(device=device, measure=self.measure).count(), 1)

    def test_resaving_same_software_version_does_not_create_a_new_result(self):
        device = self.make_device(platform=self.versioned_platform)
        device.custom_field_data = {'software_version': '17.12.3'}
        device.save()

        device.save()

        self.assertEqual(ComplianceResult.objects.filter(device=device, measure=self.measure).count(), 1)
