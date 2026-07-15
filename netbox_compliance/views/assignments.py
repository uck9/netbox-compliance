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
    'PackageAssignmentListView',
    'PackageAssignmentView',
    'PackageAssignmentEditView',
    'PackageAssignmentDeleteView',
    'PackageAssignmentBulkDeleteView',
    'MeasureAssignmentListView',
    'MeasureAssignmentView',
    'MeasureAssignmentEditView',
    'MeasureAssignmentDeleteView',
    'MeasureAssignmentBulkDeleteView',
)


#
# PackageAssignment
#

@register_model_view(models.PackageAssignment, 'list', path='', detail=False)
class PackageAssignmentListView(ObjectListView):
    queryset = models.PackageAssignment.objects.select_related(
        'package', 'device', 'device_role', 'site', 'site_group', 'platform', 'tag',
    )
    table = tables.PackageAssignmentTable
    filterset = filtersets.PackageAssignmentFilterSet
    filterset_form = forms.PackageAssignmentFilterForm


@register_model_view(models.PackageAssignment)
class PackageAssignmentView(ObjectView):
    queryset = models.PackageAssignment.objects.all()


@register_model_view(models.PackageAssignment, 'add', detail=False)
@register_model_view(models.PackageAssignment, 'edit')
class PackageAssignmentEditView(ObjectEditView):
    queryset = models.PackageAssignment.objects.all()
    form = forms.PackageAssignmentForm


@register_model_view(models.PackageAssignment, 'delete')
class PackageAssignmentDeleteView(ObjectDeleteView):
    queryset = models.PackageAssignment.objects.all()


@register_model_view(models.PackageAssignment, 'bulk_delete', detail=False)
class PackageAssignmentBulkDeleteView(BulkDeleteView):
    queryset = models.PackageAssignment.objects.all()
    filterset = filtersets.PackageAssignmentFilterSet
    table = tables.PackageAssignmentTable


#
# MeasureAssignment
#

@register_model_view(models.MeasureAssignment, 'list', path='', detail=False)
class MeasureAssignmentListView(ObjectListView):
    queryset = models.MeasureAssignment.objects.select_related('device', 'measure')
    table = tables.MeasureAssignmentTable
    filterset = filtersets.MeasureAssignmentFilterSet
    filterset_form = forms.MeasureAssignmentFilterForm


@register_model_view(models.MeasureAssignment)
class MeasureAssignmentView(ObjectView):
    queryset = models.MeasureAssignment.objects.all()


@register_model_view(models.MeasureAssignment, 'add', detail=False)
@register_model_view(models.MeasureAssignment, 'edit')
class MeasureAssignmentEditView(ObjectEditView):
    queryset = models.MeasureAssignment.objects.all()
    form = forms.MeasureAssignmentForm


@register_model_view(models.MeasureAssignment, 'delete')
class MeasureAssignmentDeleteView(ObjectDeleteView):
    queryset = models.MeasureAssignment.objects.all()


@register_model_view(models.MeasureAssignment, 'bulk_delete', detail=False)
class MeasureAssignmentBulkDeleteView(BulkDeleteView):
    queryset = models.MeasureAssignment.objects.all()
    filterset = filtersets.MeasureAssignmentFilterSet
    table = tables.MeasureAssignmentTable
