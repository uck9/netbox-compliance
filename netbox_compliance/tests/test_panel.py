from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureResultTypeChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceResultStatusChoices,
    CompliancePackageStatusChoices,
)
from ..models import (
    ComplianceMeasure,
    CompliancePackage,
    ComplianceResult,
    MeasureAssignment,
    PackageAssignment,
    PackageMeasure,
)
from ..services import PANEL_CACHE_KEY, get_device_panel_data, invalidate_device_panel_cache
from .base import ComplianceTestMixin


def make_measure(slug, result_type=ComplianceMeasureResultTypeChoices.BOOLEAN, **kwargs):
    return ComplianceMeasure.objects.create(
        name=slug, slug=slug,
        category=ComplianceMeasureCategoryChoices.SECURITY,
        severity=ComplianceMeasureSeverityChoices.HIGH,
        result_type=result_type,
        **kwargs,
    )


class DevicePanelDataTest(ComplianceTestMixin, TestCase):
    def tearDown(self):
        # Real Redis-backed cache in this environment -- clean up only the
        # keys this test touched rather than cache.clear() (shared backend).
        cache.delete_many([PANEL_CACHE_KEY.format(device_id=d.pk) for d in getattr(self, '_panel_devices', [])])
        super().tearDown()

    def make_device(self, *args, **kwargs):
        device = super().make_device(*args, **kwargs)
        self._panel_devices = getattr(self, '_panel_devices', []) + [device]
        return device

    def test_panel_empty_when_no_flagged_packages_or_measures(self):
        measure = make_measure('panel-unpinned')
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)

        panel = get_device_panel_data(device)

        self.assertEqual(panel['packages'], [])
        self.assertEqual(panel['measures'], [])

    def test_panel_package_rows_ordered_by_panel_display_order(self):
        pkg_a = CompliancePackage.objects.create(
            name='PkgA', slug='pkg-a', status=CompliancePackageStatusChoices.ACTIVE,
            show_on_device_panel=True, panel_display_order=200,
        )
        pkg_b = CompliancePackage.objects.create(
            name='PkgB', slug='pkg-b', status=CompliancePackageStatusChoices.ACTIVE,
            show_on_device_panel=True, panel_display_order=100,
        )
        measure_a = make_measure('panel-a')
        measure_b = make_measure('panel-b')
        PackageMeasure.objects.create(package=pkg_a, measure=measure_a, weight=1, required=True)
        PackageMeasure.objects.create(package=pkg_b, measure=measure_b, weight=1, required=True)
        device = self.make_device(site=self.site)
        PackageAssignment.objects.create(package=pkg_a, site=self.site)
        PackageAssignment.objects.create(package=pkg_b, site=self.site)

        panel = get_device_panel_data(device)

        self.assertEqual([row['package'] for row in panel['packages']], [pkg_b, pkg_a])

    def test_panel_pinned_measure_rows_ordered_by_panel_display_order(self):
        measure_a = make_measure('panel-order-a', show_on_device_panel=True, panel_display_order=200)
        measure_b = make_measure('panel-order-b', show_on_device_panel=True, panel_display_order=100)
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure_a, weight=1)
        MeasureAssignment.objects.create(device=device, measure=measure_b, weight=1)

        panel = get_device_panel_data(device)

        self.assertEqual([m['row'].measure for m in panel['measures']], [measure_b, measure_a])

    def test_panel_pinned_measure_renders_display_template(self):
        measure = make_measure(
            'panel-template', result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map={'target': {'label': 'Target', 'color': 'green', 'credit': 100}},
            show_on_device_panel=True, display_template='{{ details.running }} (target {{ details.target }})',
        )
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=measure, status=ComplianceResultStatusChoices.PASS, value='target',
            details={'running': '17.9.4a', 'target': '17.12.3'}, timestamp=timezone.now(), source='test',
        )

        panel = get_device_panel_data(device)

        self.assertEqual(panel['measures'][0]['display_text'], '17.9.4a (target 17.12.3)')

    def test_panel_stale_result_shows_grey_badge_but_still_renders_last_known_template_text(self):
        measure = make_measure(
            'panel-stale', result_type=ComplianceMeasureResultTypeChoices.ENUM,
            value_map={'target': {'label': 'Target', 'color': 'green', 'credit': 100}},
            show_on_device_panel=True, display_template='{{ details.running }}',
            max_result_age_days=1,
        )
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)
        ComplianceResult.objects.create(
            device=device, measure=measure, status=ComplianceResultStatusChoices.PASS, value='target',
            details={'running': '17.9.4a'}, timestamp=timezone.now() - timezone.timedelta(days=10), source='test',
        )

        panel = get_device_panel_data(device)

        entry = panel['measures'][0]
        self.assertTrue(entry['row'].stale)
        self.assertEqual(entry['display_color'], 'grey')
        self.assertEqual(entry['display_text'], '17.9.4a')

    def test_panel_cache_hit_returns_same_payload_without_requery(self):
        import netbox_compliance.services as services_module

        measure = make_measure('panel-cache', show_on_device_panel=True)
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)

        get_device_panel_data(device)  # populate cache

        call_count = {'n': 0}
        original = services_module.get_effective_measures

        def _counting(*args, **kwargs):
            call_count['n'] += 1
            return original(*args, **kwargs)

        services_module.get_effective_measures = _counting
        try:
            get_device_panel_data(device)
            get_device_panel_data(device)
        finally:
            services_module.get_effective_measures = original

        self.assertEqual(call_count['n'], 0)

    def test_panel_cache_invalidated_on_result_save(self):
        measure = make_measure('panel-invalidate', show_on_device_panel=True)
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)

        panel_before = get_device_panel_data(device)
        self.assertEqual(panel_before['measures'][0]['row'].status, 'pending')

        ComplianceResult.objects.create(
            device=device, measure=measure, status=ComplianceResultStatusChoices.PASS, value='true',
            timestamp=timezone.now(), source='test',
        )

        panel_after = get_device_panel_data(device)
        self.assertEqual(panel_after['measures'][0]['row'].status, 'pass')

    def test_invalidate_device_panel_cache_clears_key(self):
        measure = make_measure('panel-manual-invalidate', show_on_device_panel=True)
        device = self.make_device()
        MeasureAssignment.objects.create(device=device, measure=measure, weight=1)

        get_device_panel_data(device)
        self.assertIsNotNone(cache.get(PANEL_CACHE_KEY.format(device_id=device.pk)))

        invalidate_device_panel_cache(device.pk)

        self.assertIsNone(cache.get(PANEL_CACHE_KEY.format(device_id=device.pk)))
