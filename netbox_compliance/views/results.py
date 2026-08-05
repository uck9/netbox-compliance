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
    'ComplianceResultHistoryListView',
    'ComplianceResultHistoryView',
    'ComplianceResultHistoryDeleteView',
    'ComplianceResultHistoryBulkDeleteView',
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

    def get_extra_context(self, request, instance):
        history = models.ComplianceResultHistory.objects.filter(
            device=instance.device, measure=instance.measure,
        )[:25]
        return {'history_table': tables.ComplianceResultHistoryTable(history, orderable=False)}


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


# ComplianceResultHistory is append-only and system-generated (see the
# post_save signal in __init__.py) -- no add/edit view, same as
# ComplianceSnapshot. list/detail/delete are still useful for browsing and
# manual pruning.
@register_model_view(models.ComplianceResultHistory, 'list', path='', detail=False)
class ComplianceResultHistoryListView(ObjectListView):
    queryset = models.ComplianceResultHistory.objects.select_related('device', 'measure')
    table = tables.ComplianceResultHistoryTable
    filterset = filtersets.ComplianceResultHistoryFilterSet
    filterset_form = forms.ComplianceResultHistoryFilterForm
    actions = {
        'export': {'view'},
        'bulk_delete': {'delete'},
    }


@register_model_view(models.ComplianceResultHistory)
class ComplianceResultHistoryView(ObjectView):
    queryset = models.ComplianceResultHistory.objects.all()


@register_model_view(models.ComplianceResultHistory, 'delete')
class ComplianceResultHistoryDeleteView(ObjectDeleteView):
    queryset = models.ComplianceResultHistory.objects.all()


@register_model_view(models.ComplianceResultHistory, 'bulk_delete', detail=False)
class ComplianceResultHistoryBulkDeleteView(BulkDeleteView):
    queryset = models.ComplianceResultHistory.objects.all()
    filterset = filtersets.ComplianceResultHistoryFilterSet
    table = tables.ComplianceResultHistoryTable
