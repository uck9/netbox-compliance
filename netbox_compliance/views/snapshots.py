from netbox.views.generic import BulkDeleteView, ObjectDeleteView, ObjectListView, ObjectView
from utilities.views import register_model_view

from .. import filtersets, forms, models, tables

__all__ = (
    'ComplianceSnapshotListView',
    'ComplianceSnapshotView',
    'ComplianceSnapshotDeleteView',
    'ComplianceSnapshotBulkDeleteView',
)


@register_model_view(models.ComplianceSnapshot, 'list', path='', detail=False)
class ComplianceSnapshotListView(ObjectListView):
    queryset = models.ComplianceSnapshot.objects.select_related('device')
    table = tables.ComplianceSnapshotTable
    filterset = filtersets.ComplianceSnapshotFilterSet
    filterset_form = forms.ComplianceSnapshotFilterForm
    actions = {
        'export': {'view'},
        'bulk_delete': {'delete'},
    }


@register_model_view(models.ComplianceSnapshot)
class ComplianceSnapshotView(ObjectView):
    queryset = models.ComplianceSnapshot.objects.all()


@register_model_view(models.ComplianceSnapshot, 'delete')
class ComplianceSnapshotDeleteView(ObjectDeleteView):
    queryset = models.ComplianceSnapshot.objects.all()


@register_model_view(models.ComplianceSnapshot, 'bulk_delete', detail=False)
class ComplianceSnapshotBulkDeleteView(BulkDeleteView):
    queryset = models.ComplianceSnapshot.objects.all()
    filterset = filtersets.ComplianceSnapshotFilterSet
    table = tables.ComplianceSnapshotTable
