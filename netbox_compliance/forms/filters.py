from django import forms
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, DeviceRole, Platform, Site, SiteGroup
from extras.models import Tag
from netbox.forms import NetBoxModelFilterSetForm
from utilities.forms.fields import DynamicModelMultipleChoiceField, TagFilterField
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import DatePicker

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceMeasureStatusChoices,
    CompliancePackageStatusChoices,
    ComplianceResultStatusChoices,
)
from ..models import (
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
    'ComplianceMeasureFilterForm',
    'CompliancePackageFilterForm',
    'PackageMeasureFilterForm',
    'PackageAssignmentFilterForm',
    'MeasureAssignmentFilterForm',
    'ComplianceExemptionFilterForm',
    'ComplianceResultFilterForm',
    'ComplianceSnapshotFilterForm',
)


class ComplianceMeasureFilterForm(NetBoxModelFilterSetForm):
    model = ComplianceMeasure
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('category', 'severity', 'status', name=_('Attributes')),
    )
    category = forms.MultipleChoiceField(choices=ComplianceMeasureCategoryChoices, required=False)
    severity = forms.MultipleChoiceField(choices=ComplianceMeasureSeverityChoices, required=False)
    status = forms.MultipleChoiceField(choices=ComplianceMeasureStatusChoices, required=False)
    tag = TagFilterField(model)


class CompliancePackageFilterForm(NetBoxModelFilterSetForm):
    model = CompliancePackage
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('status', name=_('Attributes')),
    )
    status = forms.MultipleChoiceField(choices=CompliancePackageStatusChoices, required=False)
    tag = TagFilterField(model)


class PackageMeasureFilterForm(NetBoxModelFilterSetForm):
    model = PackageMeasure
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('package_id', 'measure_id', 'required', name=_('Assignment')),
    )
    package_id = DynamicModelMultipleChoiceField(
        queryset=CompliancePackage.objects.all(), required=False, label=_('Package'),
    )
    measure_id = DynamicModelMultipleChoiceField(
        queryset=ComplianceMeasure.objects.all(), required=False, label=_('Measure'),
    )
    required = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=[('', '---------'), (True, 'Yes'), (False, 'No')]),
    )
    tag = TagFilterField(model)


class PackageAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = PackageAssignment
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('package_id', name=_('Assignment')),
        FieldSet('device_id', 'device_role_id', 'site_id', 'site_group_id', 'platform_id', 'tag_id', name=_('Scope')),
    )
    package_id = DynamicModelMultipleChoiceField(
        queryset=CompliancePackage.objects.all(), required=False, label=_('Package'),
    )
    device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False, selector=True, label=_('Device'),
    )
    device_role_id = DynamicModelMultipleChoiceField(
        queryset=DeviceRole.objects.all(),
        required=False, label=_('Device Role'),
    )
    site_id = DynamicModelMultipleChoiceField(
        queryset=Site.objects.all(),
        required=False, selector=True, label=_('Site'),
    )
    site_group_id = DynamicModelMultipleChoiceField(
        queryset=SiteGroup.objects.all(),
        required=False, label=_('Site Group'),
    )
    platform_id = DynamicModelMultipleChoiceField(
        queryset=Platform.objects.all(),
        required=False, label=_('Platform'),
    )
    tag_id = DynamicModelMultipleChoiceField(
        queryset=Tag.objects.all(), required=False, label=_('Tag'),
    )
    tag = TagFilterField(model)


class MeasureAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = MeasureAssignment
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('device_id', 'measure_id', name=_('Assignment')),
    )
    device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False, selector=True, label=_('Device'),
    )
    measure_id = DynamicModelMultipleChoiceField(
        queryset=ComplianceMeasure.objects.all(), required=False, label=_('Measure'),
    )
    tag = TagFilterField(model)


class ComplianceExemptionFilterForm(NetBoxModelFilterSetForm):
    model = ComplianceExemption
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('measure_id', 'device_id', 'site_id', 'site_group_id', 'tag_id', name=_('Scope')),
        FieldSet('active', 'valid_until__lt', name=_('Validity')),
    )
    measure_id = DynamicModelMultipleChoiceField(
        queryset=ComplianceMeasure.objects.all(), required=False, label=_('Measure'),
    )
    device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False, selector=True, label=_('Device'),
    )
    site_id = DynamicModelMultipleChoiceField(
        queryset=Site.objects.all(),
        required=False, selector=True, label=_('Site'),
    )
    site_group_id = DynamicModelMultipleChoiceField(
        queryset=SiteGroup.objects.all(),
        required=False, label=_('Site Group'),
    )
    tag_id = DynamicModelMultipleChoiceField(
        queryset=Tag.objects.all(), required=False, label=_('Tag'),
    )
    active = forms.NullBooleanField(
        required=False,
        label=_('Currently active'),
        widget=forms.Select(choices=[('', '---------'), (True, 'Yes'), (False, 'No')]),
    )
    valid_until__lt = forms.DateField(required=False, label=_('Expiring before'), widget=DatePicker)
    tag = TagFilterField(model)


class ComplianceResultFilterForm(NetBoxModelFilterSetForm):
    model = ComplianceResult
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('device_id', 'measure_id', 'status', 'source', name=_('Result')),
        FieldSet('timestamp__gte', 'timestamp__lte', name=_('Dates')),
    )
    device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False, selector=True, label=_('Device'),
    )
    measure_id = DynamicModelMultipleChoiceField(
        queryset=ComplianceMeasure.objects.all(), required=False, label=_('Measure'),
    )
    status = forms.MultipleChoiceField(choices=ComplianceResultStatusChoices, required=False)
    source = forms.CharField(required=False)
    timestamp__gte = forms.DateTimeField(required=False, label=_('From'), widget=DatePicker)
    timestamp__lte = forms.DateTimeField(required=False, label=_('Until'), widget=DatePicker)
    tag = TagFilterField(model)


class ComplianceSnapshotFilterForm(NetBoxModelFilterSetForm):
    model = ComplianceSnapshot
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('device_id', 'period', 'compliant', name=_('Snapshot')),
    )
    device_id = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False, selector=True, label=_('Device'),
    )
    period = forms.DateField(required=False, widget=DatePicker)
    compliant = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=[('', '---------'), (True, 'Yes'), (False, 'No')]),
    )
    tag = TagFilterField(model)
