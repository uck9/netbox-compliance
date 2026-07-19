from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from netbox.views.generic import (
    BulkDeleteView,
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
)
from utilities.permissions import get_permission_for_model
from utilities.views import ObjectPermissionRequiredMixin, register_model_view

from .. import filtersets, forms, models, tables

__all__ = (
    'PackageAssignmentListView',
    'PackageAssignmentView',
    'PackageAssignmentEditView',
    'PackageAssignmentDeleteView',
    'PackageAssignmentBulkDeleteView',
    'PackageAssignmentBulkAssignView',
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


@register_model_view(models.PackageAssignment, 'bulk_assign', path='bulk-assign', detail=False)
class PackageAssignmentBulkAssignView(ObjectPermissionRequiredMixin, View):
    """
    Assigns one package to many scope values (e.g. several platforms) at
    once, creating one PackageAssignment row per selected value.
    """
    queryset = models.PackageAssignment.objects.all()
    template_name = 'netbox_compliance/packageassignment_bulk_assign.html'

    def get_required_permission(self):
        return get_permission_for_model(models.PackageAssignment, 'add')

    def get(self, request):
        form = forms.PackageAssignmentBulkAssignForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = forms.PackageAssignmentBulkAssignForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        package = form.cleaned_data['package']
        description = form.cleaned_data['description']
        scope_field = form.cleaned_data['scope_field']
        values = form.cleaned_data[scope_field]

        created, skipped = 0, 0
        for value in values:
            _, was_created = models.PackageAssignment.objects.get_or_create(
                package=package, **{scope_field: value},
                defaults={'description': description},
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        if created:
            messages.success(request, f'Created {created} package assignment(s).')
        if skipped:
            messages.info(request, f'Skipped {skipped} assignment(s) that already existed.')

        return redirect(reverse('plugins:netbox_compliance:packageassignment_list') + f'?package_id={package.pk}')


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
