from django import forms

from dcim.models import Site
from tenancy.models import Tenant

from ..models import CompliancePackage, ComplianceMeasure

__all__ = ('StatusReportFilterForm',)

_MULTI = {"class": "form-select form-select-sm", "size": "6"}


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
