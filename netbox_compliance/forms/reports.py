from django import forms

from dcim.models import DeviceRole, Site
from tenancy.models import Tenant

from ..models import CompliancePackage, ComplianceMeasure

__all__ = ('StatusReportFilterForm', 'TrendReportFilterForm')

_MULTI = {"class": "form-select form-select-sm", "size": "6"}
_SINGLE = {"class": "form-select form-select-sm"}


class StatusReportFilterForm(forms.Form):
    site = forms.ModelMultipleChoiceField(
        queryset=Site.objects.order_by("name"),
        required=False,
        label="Site",
        widget=forms.SelectMultiple(attrs=_MULTI),
    )
    tenant = forms.ModelMultipleChoiceField(
        queryset=Tenant.objects.order_by("name"),
        required=False,
        label="Tenant",
        widget=forms.SelectMultiple(attrs=_MULTI),
    )
    package = forms.ModelMultipleChoiceField(
        queryset=CompliancePackage.objects.order_by("name"),
        required=False,
        label="Package",
        help_text="Leave blank to show every active package (By Package tab) or every active test (By Test tab)",
        widget=forms.SelectMultiple(attrs=_MULTI),
    )
    measure = forms.ModelMultipleChoiceField(
        queryset=ComplianceMeasure.objects.order_by("name"),
        required=False,
        label="Test",
        help_text="Narrows the By Test tab's columns. If Package is set and Test is left blank, only that package's tests are shown",
        widget=forms.SelectMultiple(attrs=_MULTI),
    )


class TrendReportFilterForm(forms.Form):
    site = forms.ModelChoiceField(
        queryset=Site.objects.order_by("name"),
        required=False,
        label="Site",
        widget=forms.Select(attrs=_SINGLE),
        help_text="Scopes to devices at this site as of each snapshotted period, not their current site",
    )
    role = forms.ModelChoiceField(
        queryset=DeviceRole.objects.order_by("name"),
        required=False,
        label="Role",
        widget=forms.Select(attrs=_SINGLE),
    )
    package = forms.ModelChoiceField(
        queryset=CompliancePackage.objects.order_by("name"),
        required=False,
        label="Package",
        help_text="Leave blank to show every measure across every package plus direct assignments",
        widget=forms.Select(attrs=_SINGLE),
    )
    months = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=36,
        initial=12,
        label="Months",
        widget=forms.NumberInput(attrs={"class": "form-control form-control-sm"}),
    )
