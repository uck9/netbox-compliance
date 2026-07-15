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
    'ComplianceResultListView',
    'ComplianceResultView',
    'ComplianceResultEditView',
    'ComplianceResultDeleteView',
    'ComplianceResultBulkDeleteView',
)


@register_model_view(models.ComplianceResult, 'list', path='', detail=False)
class ComplianceResultListView(ObjectListView):
    queryset = models.ComplianceResult.objects.select_related('device', 'measure')
    table = tables.ComplianceResultTable
    filterset = filtersets.ComplianceResultFilterSet
    filterset_form = forms.ComplianceResultFilterForm


@register_model_view(models.ComplianceResult)
class ComplianceResultView(ObjectView):
    queryset = models.ComplianceResult.objects.all()


@register_model_view(models.ComplianceResult, 'add', detail=False)
@register_model_view(models.ComplianceResult, 'edit')
class ComplianceResultEditView(ObjectEditView):
    queryset = models.ComplianceResult.objects.all()
    form = forms.ComplianceResultForm


@register_model_view(models.ComplianceResult, 'delete')
class ComplianceResultDeleteView(ObjectDeleteView):
    queryset = models.ComplianceResult.objects.all()


@register_model_view(models.ComplianceResult, 'bulk_delete', detail=False)
class ComplianceResultBulkDeleteView(BulkDeleteView):
    queryset = models.ComplianceResult.objects.all()
    filterset = filtersets.ComplianceResultFilterSet
    table = tables.ComplianceResultTable
