import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, DeviceRole, Platform, Site, SiteGroup
from extras.models import Tag
from netbox.filtersets import NetBoxModelFilterSet

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
    ComplianceResult,
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
    'ComplianceSnapshotFilterSet',
)


class ComplianceMeasureFilterSet(NetBoxModelFilterSet):
    category = django_filters.MultipleChoiceFilter(choices=ComplianceMeasureCategoryChoices)
    severity = django_filters.MultipleChoiceFilter(choices=ComplianceMeasureSeverityChoices)
    status = django_filters.MultipleChoiceFilter(choices=ComplianceMeasureStatusChoices)

    class Meta:
        model = ComplianceMeasure
        fields = ('id', 'name', 'slug', 'max_result_age_days')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(slug__icontains=value) | Q(description__icontains=value)
        )


class CompliancePackageFilterSet(NetBoxModelFilterSet):
    status = django_filters.MultipleChoiceFilter(choices=CompliancePackageStatusChoices)
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measures', queryset=ComplianceMeasure.objects.all(), label=_('Measure'),
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
        field_name='package', queryset=CompliancePackage.objects.all(), label=_('Package'),
    )
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measure', queryset=ComplianceMeasure.objects.all(), label=_('Measure'),
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
        field_name='package', queryset=CompliancePackage.objects.all(), label=_('Package'),
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device'),
    )
    device_role_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device_role', queryset=DeviceRole.objects.all(), label=_('Device Role'),
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site', queryset=Site.objects.all(), label=_('Site'),
    )
    site_group_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site_group', queryset=SiteGroup.objects.all(), label=_('Site Group'),
    )
    platform_id = django_filters.ModelMultipleChoiceFilter(
        field_name='platform', queryset=Platform.objects.all(), label=_('Platform'),
    )
    tag_id = django_filters.ModelMultipleChoiceFilter(
        field_name='tag', queryset=Tag.objects.all(), label=_('Tag'),
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
        field_name='device', queryset=Device.objects.all(), label=_('Device'),
    )
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measure', queryset=ComplianceMeasure.objects.all(), label=_('Measure'),
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
        field_name='measure', queryset=ComplianceMeasure.objects.all(), label=_('Measure'),
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device'),
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site', queryset=Site.objects.all(), label=_('Site'),
    )
    site_group_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site_group', queryset=SiteGroup.objects.all(), label=_('Site Group'),
    )
    tag_id = django_filters.ModelMultipleChoiceFilter(
        field_name='tag', queryset=Tag.objects.all(), label=_('Tag'),
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
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label=_('Device'),
    )
    measure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='measure', queryset=ComplianceMeasure.objects.all(), label=_('Measure'),
    )
    measure = django_filters.ModelMultipleChoiceFilter(
        field_name='measure__slug', queryset=ComplianceMeasure.objects.all(),
        to_field_name='slug', label=_('Measure (slug)'),
    )
    status = django_filters.MultipleChoiceFilter(choices=ComplianceResultStatusChoices)
    timestamp = django_filters.DateTimeFromToRangeFilter()
    latest = django_filters.BooleanFilter(method='filter_latest', label=_('Latest result per device/measure'))

    class Meta:
        model = ComplianceResult
        fields = ('id', 'source')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(source__icontains=value))

    def filter_latest(self, queryset, name, value):
        if not value:
            return queryset
        latest_pks = (
            queryset.order_by('device_id', 'measure_id', '-timestamp')
            .distinct('device_id', 'measure_id')
            .values_list('pk', flat=True)
        )
        return queryset.filter(pk__in=list(latest_pks))


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
