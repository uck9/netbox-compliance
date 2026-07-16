from django import forms
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, DeviceRole, Platform, Site, SiteGroup
from extras.models import Tag
from netbox.forms import NetBoxModelForm
from utilities.forms.fields import CommentField, DynamicModelChoiceField, JSONField, SlugField
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import DatePicker, DateTimePicker

from ..models import (
    ComplianceExemption,
    ComplianceMeasure,
    CompliancePackage,
    ComplianceResult,
    MeasureAssignment,
    PackageAssignment,
    PackageMeasure,
)

__all__ = (
    'ComplianceMeasureForm',
    'CompliancePackageForm',
    'PackageMeasureForm',
    'PackageAssignmentForm',
    'MeasureAssignmentForm',
    'ComplianceExemptionForm',
    'ComplianceResultForm',
)


class ComplianceMeasureForm(NetBoxModelForm):
    slug = SlugField(slug_source='name')
    comments = CommentField()
    value_map = JSONField(
        required=False,
        help_text=_('Enum type only: {"key": {"label": ..., "color": "green|orange|red|grey", "credit": 0-100}}'),
    )
    required_detail_keys = JSONField(required=False, help_text=_('e.g. ["running", "target"]'))

    fieldsets = (
        FieldSet('name', 'slug', 'description', 'category', 'severity', 'status', 'tags', name=_('Measure')),
        FieldSet('result_type', 'pass_threshold', 'value_map', name=_('Result Type')),
        FieldSet('max_result_age_days', name=_('Staleness')),
        FieldSet(
            'show_on_device_panel', 'panel_display_order', 'display_template', 'required_detail_keys',
            name=_('Device Panel'),
        ),
    )

    class Meta:
        model = ComplianceMeasure
        fields = (
            'name', 'slug', 'description', 'category', 'severity',
            'max_result_age_days', 'status', 'comments', 'result_type',
            'pass_threshold', 'value_map', 'show_on_device_panel', 'panel_display_order',
            'display_template', 'required_detail_keys', 'tags',
        )


class CompliancePackageForm(NetBoxModelForm):
    slug = SlugField(slug_source='name')

    fieldsets = (
        FieldSet('name', 'slug', 'description', 'status', 'tags', name=_('Package')),
        FieldSet(
            'show_on_device_panel', 'panel_display_order', 'amber_threshold', 'red_on_critical_fail',
            name=_('Device Panel'),
        ),
    )

    class Meta:
        model = CompliancePackage
        fields = (
            'name', 'slug', 'description', 'status', 'show_on_device_panel',
            'panel_display_order', 'amber_threshold', 'red_on_critical_fail', 'tags',
        )


class PackageMeasureForm(NetBoxModelForm):
    package = DynamicModelChoiceField(queryset=CompliancePackage.objects.all())
    measure = DynamicModelChoiceField(queryset=ComplianceMeasure.objects.all())

    fieldsets = (
        FieldSet('package', 'measure', 'weight', 'required', 'display_order', 'tags', name=_('Package Measure')),
    )

    class Meta:
        model = PackageMeasure
        fields = ('package', 'measure', 'weight', 'required', 'display_order', 'tags')


class PackageAssignmentForm(NetBoxModelForm):
    package = DynamicModelChoiceField(queryset=CompliancePackage.objects.all())
    device = DynamicModelChoiceField(queryset=Device.objects.all(), required=False, selector=True, label=_('Device'))
    device_role = DynamicModelChoiceField(queryset=DeviceRole.objects.all(), required=False, label=_('Device Role'))
    site = DynamicModelChoiceField(queryset=Site.objects.all(), required=False, selector=True, label=_('Site'))
    site_group = DynamicModelChoiceField(queryset=SiteGroup.objects.all(), required=False, label=_('Site Group'))
    platform = DynamicModelChoiceField(queryset=Platform.objects.all(), required=False, label=_('Platform'))
    tag = DynamicModelChoiceField(queryset=Tag.objects.all(), required=False, label=_('Tag'))

    fieldsets = (
        FieldSet('package', 'description', 'tags', name=_('Package Assignment')),
        FieldSet('device', 'device_role', 'site', 'site_group', 'platform', 'tag', name=_('Scope (exactly one)')),
    )

    class Meta:
        model = PackageAssignment
        fields = (
            'package', 'device', 'device_role', 'site', 'site_group',
            'platform', 'tag', 'description', 'tags',
        )


class MeasureAssignmentForm(NetBoxModelForm):
    device = DynamicModelChoiceField(queryset=Device.objects.all(), selector=True, label=_('Device'))
    measure = DynamicModelChoiceField(queryset=ComplianceMeasure.objects.all())

    fieldsets = (
        FieldSet('device', 'measure', 'weight', 'description', 'tags', name=_('Measure Assignment')),
    )

    class Meta:
        model = MeasureAssignment
        fields = ('device', 'measure', 'weight', 'description', 'tags')


class ComplianceExemptionForm(NetBoxModelForm):
    measure = DynamicModelChoiceField(queryset=ComplianceMeasure.objects.all())
    device = DynamicModelChoiceField(queryset=Device.objects.all(), required=False, selector=True, label=_('Device'))
    site = DynamicModelChoiceField(queryset=Site.objects.all(), required=False, selector=True, label=_('Site'))
    site_group = DynamicModelChoiceField(queryset=SiteGroup.objects.all(), required=False, label=_('Site Group'))
    tag = DynamicModelChoiceField(queryset=Tag.objects.all(), required=False, label=_('Tag'))

    fieldsets = (
        FieldSet('measure', name=_('Measure')),
        FieldSet('device', 'site', 'site_group', 'tag', name=_('Scope (exactly one)')),
        FieldSet('justification', 'approved_by', 'valid_from', 'valid_until', 'tags', name=_('Approval')),
    )

    class Meta:
        model = ComplianceExemption
        fields = (
            'measure', 'device', 'site', 'site_group', 'tag',
            'justification', 'approved_by', 'valid_from', 'valid_until', 'tags',
        )
        widgets = {
            'valid_from': DatePicker(),
            'valid_until': DatePicker(),
            'justification': forms.Textarea(attrs={'rows': 4}),
        }


class ComplianceResultForm(NetBoxModelForm):
    device = DynamicModelChoiceField(queryset=Device.objects.all(), selector=True, label=_('Device'))
    measure = DynamicModelChoiceField(queryset=ComplianceMeasure.objects.all())
    details = JSONField(required=False)

    fieldsets = (
        FieldSet('device', 'measure', 'status', 'value', 'timestamp', 'source', 'details', 'tags', name=_('Result')),
    )

    class Meta:
        model = ComplianceResult
        fields = ('device', 'measure', 'status', 'value', 'timestamp', 'source', 'details', 'tags')
        widgets = {
            'timestamp': DateTimePicker(),
        }
