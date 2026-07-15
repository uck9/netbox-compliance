from netbox.views.generic import (
    BulkDeleteView,
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
)
from utilities.views import register_model_view

from .. import filtersets, forms, models, tables

__all__ = (
    'ComplianceExemptionListView',
    'ComplianceExemptionView',
    'ComplianceExemptionEditView',
    'ComplianceExemptionDeleteView',
    'ComplianceExemptionBulkDeleteView',
)


@register_model_view(models.ComplianceExemption, 'list', path='', detail=False)
class ComplianceExemptionListView(ObjectListView):
    queryset = models.ComplianceExemption.objects.select_related('measure', 'device', 'site', 'site_group', 'tag')
    table = tables.ComplianceExemptionTable
    filterset = filtersets.ComplianceExemptionFilterSet
    filterset_form = forms.ComplianceExemptionFilterForm


@register_model_view(models.ComplianceExemption)
class ComplianceExemptionView(ObjectView):
    queryset = models.ComplianceExemption.objects.all()


@register_model_view(models.ComplianceExemption, 'add', detail=False)
@register_model_view(models.ComplianceExemption, 'edit')
class ComplianceExemptionEditView(ObjectEditView):
    queryset = models.ComplianceExemption.objects.all()
    form = forms.ComplianceExemptionForm


@register_model_view(models.ComplianceExemption, 'delete')
class ComplianceExemptionDeleteView(ObjectDeleteView):
    queryset = models.ComplianceExemption.objects.all()


@register_model_view(models.ComplianceExemption, 'bulk_delete', detail=False)
class ComplianceExemptionBulkDeleteView(BulkDeleteView):
    queryset = models.ComplianceExemption.objects.all()
    filterset = filtersets.ComplianceExemptionFilterSet
    table = tables.ComplianceExemptionTable
