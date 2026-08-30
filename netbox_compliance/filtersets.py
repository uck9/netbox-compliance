import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, DeviceRole, Platform, Site, SiteGroup
from extras.models import Tag
from netbox.filtersets import NetBoxModelFilterSet
from tenancy.models import Tenant

from .choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceMeasureStatusChoices,
    CompliancePackageStatusChoices,
    ComplianceResultStatusChoices,
)
from .models import (
    ComplianceExemption,
    ComplianceMeasure,
    CompliancePackage,
    CompliancePackageReport,
    ComplianceResult,
    ComplianceResultHistory,
    ComplianceSnapshot,
    MeasureAssignment,
    PackageAssignment,
    PackageMeasure,
)

__all__ = (
    'ComplianceMeasureFilterSet',
    'CompliancePackageFilterSet',
    'PackageMeasureFilterSet',
    'PackageAssignmentFilterSet',
    'MeasureAssignmentFilterSet',
    'ComplianceExemptionFilterSet',
    'ComplianceResultFilterSet',
    'ComplianceResultHistoryFilterSet',
    'ComplianceSnapshotFilterSet',
    'CompliancePackageReportFilterSet',
)


class ComplianceMeasureFilterSet(NetBoxModelFilterSet):
    category = django_filters.MultipleChoiceFilter(choices=ComplianceMeasureCategoryChoices)
    severity = django_filters.MultipleChoiceFilter(choices=ComplianceMeasureSeverityChoices)
    status = django_filters.MultipleChoiceFilter(choices=ComplianceMeasureStatusChoices)

    class Meta:
        model = ComplianceMeasure
        fields = ('id', 'name', 'slug', 'title', 'max_result_age_days')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(slug__icontains=value) | Q(title__icontains=value)
            | Q(description__icontains=value)
        )


class CompliancePackageFilterSet(NetBoxModelFilterSet):
    status = django_filters.MultipleChoiceFilter(choices=CompliancePackageStatusChoices)
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measures', queryset=ComplianceMeasure.objects.all(), label=_('Measure (ID)'),
    )
    measure = django_filters.ModelMultipleChoiceFilter(
        field_name='measures__slug', queryset=ComplianceMeasure.objects.all(),
        to_field_name='slug', label=_('Measure (slug)'),
    )

    class Meta:
        model = CompliancePackage
        fields = ('id', 'name', 'slug')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(slug__icontains=value) | Q(description__icontains=value)
        )


class PackageMeasureFilterSet(NetBoxModelFilterSet):
    package_id = django_filters.ModelMultipleChoiceFilter(
        field_name='package', queryset=CompliancePackage.objects.all(), label=_('Package (ID)'),
    )
    package = django_filters.ModelMultipleChoiceFilter(
        field_name='package__slug', queryset=CompliancePackage.objects.all(),
        to_field_name='slug', label=_('Package (slug)'),
    )
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measure', queryset=ComplianceMeasure.objects.all(), label=_('Measure (ID)'),
    )
    measure = django_filters.ModelMultipleChoiceFilter(
        field_name='measure__slug', queryset=ComplianceMeasure.objects.all(),
        to_field_name='slug', label=_('Measure (slug)'),
    )
    required = django_filters.BooleanFilter()

    class Meta:
        model = PackageMeasure
        fields = ('id', 'weight', 'display_order')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(package__name__icontains=value) | Q(measure__name__icontains=value)
        )


class PackageAssignmentFilterSet(NetBoxModelFilterSet):
    package_id = django_filters.ModelMultipleChoiceFilter(
        field_name='package', queryset=CompliancePackage.objects.all(), label=_('Package (ID)'),
    )
    package = django_filters.ModelMultipleChoiceFilter(
        field_name='package__slug', queryset=CompliancePackage.objects.all(),
        to_field_name='slug', label=_('Package (slug)'),
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device (ID)'),
    )
    device = django_filters.ModelMultipleChoiceFilter(
        field_name='device__name', queryset=Device.objects.all(),
        to_field_name='name', label=_('Device (name)'),
    )
    device_role_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device_role', queryset=DeviceRole.objects.all(), label=_('Device Role (ID)'),
    )
    device_role = django_filters.ModelMultipleChoiceFilter(
        field_name='device_role__slug', queryset=DeviceRole.objects.all(),
        to_field_name='slug', label=_('Device Role (slug)'),
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site', queryset=Site.objects.all(), label=_('Site (ID)'),
    )
    site = django_filters.ModelMultipleChoiceFilter(
        field_name='site__slug', queryset=Site.objects.all(),
        to_field_name='slug', label=_('Site (slug)'),
    )
    site_group_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site_group', queryset=SiteGroup.objects.all(), label=_('Site Group (ID)'),
    )
    site_group = django_filters.ModelMultipleChoiceFilter(
        field_name='site_group__slug', queryset=SiteGroup.objects.all(),
        to_field_name='slug', label=_('Site Group (slug)'),
    )
    platform_id = django_filters.ModelMultipleChoiceFilter(
        field_name='platform', queryset=Platform.objects.all(), label=_('Platform (ID)'),
    )
    platform = django_filters.ModelMultipleChoiceFilter(
        field_name='platform__slug', queryset=Platform.objects.all(),
        to_field_name='slug', label=_('Platform (slug)'),
    )
    tag_id = django_filters.ModelMultipleChoiceFilter(
        field_name='tag', queryset=Tag.objects.all(), label=_('Tag (ID)'),
    )
    tag = django_filters.ModelMultipleChoiceFilter(
        field_name='tag__slug', queryset=Tag.objects.all(),
        to_field_name='slug', label=_('Tag (slug)'),
    )
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        field_name='tenants', queryset=Tenant.objects.all(), label=_('Tenant (ID)'), distinct=True,
    )
    tenant = django_filters.ModelMultipleChoiceFilter(
        field_name='tenants__slug', queryset=Tenant.objects.all(),
        to_field_name='slug', label=_('Tenant (slug)'), distinct=True,
    )

    class Meta:
        model = PackageAssignment
        fields = ('id', 'description')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(package__name__icontains=value) | Q(description__icontains=value))


class MeasureAssignmentFilterSet(NetBoxModelFilterSet):
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device (ID)'),
    )
    device = django_filters.ModelMultipleChoiceFilter(
        field_name='device__name', queryset=Device.objects.all(),
        to_field_name='name', label=_('Device (name)'),
    )
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measure', queryset=ComplianceMeasure.objects.all(), label=_('Measure (ID)'),
    )
    measure = django_filters.ModelMultipleChoiceFilter(
        field_name='measure__slug', queryset=ComplianceMeasure.objects.all(),
        to_field_name='slug', label=_('Measure (slug)'),
    )

    class Meta:
        model = MeasureAssignment
        fields = ('id', 'weight', 'description')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(measure__name__icontains=value) | Q(description__icontains=value))


class ComplianceExemptionFilterSet(NetBoxModelFilterSet):
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measure', queryset=ComplianceMeasure.objects.all(), label=_('Measure (ID)'),
    )
    measure = django_filters.ModelMultipleChoiceFilter(
        field_name='measure__slug', queryset=ComplianceMeasure.objects.all(),
        to_field_name='slug', label=_('Measure (slug)'),
    )
    package_id = django_filters.ModelMultipleChoiceFilter(
        field_name='package', queryset=CompliancePackage.objects.all(), label=_('Package (ID)'),
    )
    package = django_filters.ModelMultipleChoiceFilter(
        field_name='package__slug', queryset=CompliancePackage.objects.all(),
        to_field_name='slug', label=_('Package (slug)'),
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device (ID)'),
    )
    device = django_filters.ModelMultipleChoiceFilter(
        field_name='device__name', queryset=Device.objects.all(),
        to_field_name='name', label=_('Device (name)'),
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site', queryset=Site.objects.all(), label=_('Site (ID)'),
    )
    site = django_filters.ModelMultipleChoiceFilter(
        field_name='site__slug', queryset=Site.objects.all(),
        to_field_name='slug', label=_('Site (slug)'),
    )
    site_group_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site_group', queryset=SiteGroup.objects.all(), label=_('Site Group (ID)'),
    )
    site_group = django_filters.ModelMultipleChoiceFilter(
        field_name='site_group__slug', queryset=SiteGroup.objects.all(),
        to_field_name='slug', label=_('Site Group (slug)'),
    )
    tag_id = django_filters.ModelMultipleChoiceFilter(
        field_name='tag', queryset=Tag.objects.all(), label=_('Tag (ID)'),
    )
    tag = django_filters.ModelMultipleChoiceFilter(
        field_name='tag__slug', queryset=Tag.objects.all(),
        to_field_name='slug', label=_('Tag (slug)'),
    )
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        field_name='tenant', queryset=Tenant.objects.all(), label=_('Tenant (ID)'),
    )
    tenant = django_filters.ModelMultipleChoiceFilter(
        field_name='tenant__slug', queryset=Tenant.objects.all(),
        to_field_name='slug', label=_('Tenant (slug)'),
    )
    active = django_filters.BooleanFilter(method='filter_active', label=_('Currently active'))
    valid_until__lt = django_filters.DateFilter(field_name='valid_until', lookup_expr='lt')

    class Meta:
        model = ComplianceExemption
        fields = ('id', 'justification', 'approved_by', 'valid_from', 'valid_until')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(justification__icontains=value) | Q(approved_by__icontains=value))

    def filter_active(self, queryset, name, value):
        from datetime import date

        today = date.today()
        active_q = Q(valid_from__lte=today) & (Q(valid_until__isnull=True) | Q(valid_until__gte=today))
        return queryset.filter(active_q) if value else queryset.exclude(active_q)


class ComplianceResultFilterSet(NetBoxModelFilterSet):
    """
    ComplianceResult holds at most one row per (device, measure) -- the
    unique constraint means the plain queryset here is already "latest",
    no distinct-on-device/measure post-filtering needed. For full history,
    see ComplianceResultHistoryFilterSet below.
    """
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device (ID)'),
    )
    device = django_filters.ModelMultipleChoiceFilter(
        field_name='device__name', queryset=Device.objects.all(),
        to_field_name='name', label=_('Device (name)'),
    )
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measure', queryset=ComplianceMeasure.objects.all(), label=_('Measure (ID)'),
    )
    measure = django_filters.ModelMultipleChoiceFilter(
        field_name='measure__slug', queryset=ComplianceMeasure.objects.all(),
        to_field_name='slug', label=_('Measure (slug)'),
    )
    status = django_filters.MultipleChoiceFilter(choices=ComplianceResultStatusChoices)
    timestamp = django_filters.DateTimeFromToRangeFilter()

    class Meta:
        model = ComplianceResult
        fields = ('id', 'source')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(source__icontains=value) | Q(device__name__icontains=value))


class ComplianceResultHistoryFilterSet(NetBoxModelFilterSet):
    """Every observation ever recorded for a (device, measure) pair -- see ComplianceResultHistory."""
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device (ID)'),
    )
    device = django_filters.ModelMultipleChoiceFilter(
        field_name='device__name', queryset=Device.objects.all(),
        to_field_name='name', label=_('Device (name)'),
    )
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measure', queryset=ComplianceMeasure.objects.all(), label=_('Measure (ID)'),
    )
    measure = django_filters.ModelMultipleChoiceFilter(
        field_name='measure__slug', queryset=ComplianceMeasure.objects.all(),
        to_field_name='slug', label=_('Measure (slug)'),
    )
    status = django_filters.MultipleChoiceFilter(choices=ComplianceResultStatusChoices)
    timestamp = django_filters.DateTimeFromToRangeFilter()

    class Meta:
        model = ComplianceResultHistory
        fields = ('id', 'source', 'device_name', 'measure_slug')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(source__icontains=value) | Q(device_name__icontains=value) | Q(measure_slug__icontains=value)
        )


class ComplianceSnapshotFilterSet(NetBoxModelFilterSet):
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device'),
    )
    period = django_filters.DateFilter()
    period__gte = django_filters.DateFilter(field_name='period', lookup_expr='gte')
    period__lte = django_filters.DateFilter(field_name='period', lookup_expr='lte')
    compliant = django_filters.BooleanFilter()

    class Meta:
        model = ComplianceSnapshot
        fields = ('id', 'device_name')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(device_name__icontains=value))


class CompliancePackageReportFilterSet(NetBoxModelFilterSet):
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device'),
    )
    package_id = django_filters.ModelMultipleChoiceFilter(
        field_name='package', queryset=CompliancePackage.objects.all(), label=_('Package'),
    )

    class Meta:
        model = CompliancePackageReport
        fields = ('id', 'device_name', 'package_slug')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(device_name__icontains=value) | Q(package_slug__icontains=value))
