from django.db.models import Count

from dcim.filtersets import DeviceFilterSet
from dcim.forms import DeviceFilterForm
from dcim.models import Device
from dcim.tables import DeviceTable
from netbox.views.generic import (
    BulkDeleteView,
    ObjectChildrenView,
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
)
from utilities.views import ViewTab, register_model_view

from .. import filtersets, forms, models, tables
from ..services import devices_for_package

__all__ = (
    'ComplianceMeasureListView',
    'ComplianceMeasureView',
    'ComplianceMeasureEditView',
    'ComplianceMeasureDeleteView',
    'ComplianceMeasureBulkDeleteView',
    'CompliancePackageListView',
    'CompliancePackageView',
    'CompliancePackageEditView',
    'CompliancePackageDeleteView',
    'CompliancePackageBulkDeleteView',
    'CompliancePackageMeasuresView',
    'CompliancePackageDevicesView',
    'PackageMeasureListView',
    'PackageMeasureView',
    'PackageMeasureEditView',
    'PackageMeasureDeleteView',
    'PackageMeasureBulkDeleteView',
)


#
# ComplianceMeasure
#

@register_model_view(models.ComplianceMeasure, 'list', path='', detail=False)
class ComplianceMeasureListView(ObjectListView):
    queryset = models.ComplianceMeasure.objects.annotate(package_count=Count('packages', distinct=True))
    table = tables.ComplianceMeasureTable
    filterset = filtersets.ComplianceMeasureFilterSet
    filterset_form = forms.ComplianceMeasureFilterForm


@register_model_view(models.ComplianceMeasure)
class ComplianceMeasureView(ObjectView):
    queryset = models.ComplianceMeasure.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'packages': instance.packages.all(),
        }


@register_model_view(models.ComplianceMeasure, 'add', detail=False)
@register_model_view(models.ComplianceMeasure, 'edit')
class ComplianceMeasureEditView(ObjectEditView):
    queryset = models.ComplianceMeasure.objects.all()
    form = forms.ComplianceMeasureForm


@register_model_view(models.ComplianceMeasure, 'delete')
class ComplianceMeasureDeleteView(ObjectDeleteView):
    queryset = models.ComplianceMeasure.objects.all()


@register_model_view(models.ComplianceMeasure, 'bulk_delete', detail=False)
class ComplianceMeasureBulkDeleteView(BulkDeleteView):
    queryset = models.ComplianceMeasure.objects.all()
    filterset = filtersets.ComplianceMeasureFilterSet
    table = tables.ComplianceMeasureTable


#
# CompliancePackage
#

@register_model_view(models.CompliancePackage, 'list', path='', detail=False)
class CompliancePackageListView(ObjectListView):
    queryset = models.CompliancePackage.objects.annotate(measure_count=Count('measures', distinct=True))
    table = tables.CompliancePackageTable
    filterset = filtersets.CompliancePackageFilterSet
    filterset_form = forms.CompliancePackageFilterForm


@register_model_view(models.CompliancePackage)
class CompliancePackageView(ObjectView):
    queryset = models.CompliancePackage.objects.all()

    def get_extra_context(self, request, instance):
        try:
            device_count = devices_for_package(instance).count()
        except Exception:
            device_count = 0

        return {
            'package_measures': instance.package_measures.select_related('measure').order_by('display_order', 'measure__name'),
            'assignments': instance.assignments.all(),
            'device_count': device_count,
        }


@register_model_view(models.CompliancePackage, 'add', detail=False)
@register_model_view(models.CompliancePackage, 'edit')
class CompliancePackageEditView(ObjectEditView):
    queryset = models.CompliancePackage.objects.all()
    form = forms.CompliancePackageForm


@register_model_view(models.CompliancePackage, 'delete')
class CompliancePackageDeleteView(ObjectDeleteView):
    queryset = models.CompliancePackage.objects.all()


@register_model_view(models.CompliancePackage, 'bulk_delete', detail=False)
class CompliancePackageBulkDeleteView(BulkDeleteView):
    queryset = models.CompliancePackage.objects.all()
    filterset = filtersets.CompliancePackageFilterSet
    table = tables.CompliancePackageTable


@register_model_view(models.CompliancePackage, name='measures')
class CompliancePackageMeasuresView(ObjectChildrenView):
    template_name = 'netbox_compliance/compliancepackage/measures.html'
    queryset = models.CompliancePackage.objects.all()
    child_model = models.PackageMeasure
    table = tables.PackageMeasureTable
    filterset = filtersets.PackageMeasureFilterSet
    actions = {
        'add': {'add'},
        'edit': {'change'},
        'delete': {'delete'},
        'bulk_delete': {'delete'},
        'export': {'view'},
    }
    tab = ViewTab(
        label='Measures',
        badge=lambda obj: models.PackageMeasure.objects.filter(package=obj).count(),
    )

    def get_children(self, request, parent):
        return (
            self.child_model.objects.filter(package=parent)
            .select_related('measure')
            .order_by('display_order', 'measure__name')
        )


@register_model_view(models.CompliancePackage, name='devices')
class CompliancePackageDevicesView(ObjectChildrenView):
    """Every device currently in this package's scope (see `devices_for_package` -- the union of
    all its PackageAssignment rows, platform-hierarchy-aware, minus any device covered by a
    currently-active package-level exemption for this package). View-only: devices aren't
    created/edited/deleted from a compliance package's context."""
    queryset = models.CompliancePackage.objects.all()
    child_model = Device
    table = DeviceTable
    filterset = DeviceFilterSet
    filterset_form = DeviceFilterForm
    actions = {'export': {'view'}}
    tab = ViewTab(
        label='Devices',
        badge=lambda obj: devices_for_package(obj).count(),
    )

    def get_children(self, request, parent):
        return devices_for_package(parent)


#
# PackageMeasure
#

@register_model_view(models.PackageMeasure, 'list', path='', detail=False)
class PackageMeasureListView(ObjectListView):
    queryset = models.PackageMeasure.objects.select_related('package', 'measure')
    table = tables.PackageMeasureTable
    filterset = filtersets.PackageMeasureFilterSet
    filterset_form = forms.PackageMeasureFilterForm


@register_model_view(models.PackageMeasure)
class PackageMeasureView(ObjectView):
    queryset = models.PackageMeasure.objects.all()


@register_model_view(models.PackageMeasure, 'add', detail=False)
@register_model_view(models.PackageMeasure, 'edit')
class PackageMeasureEditView(ObjectEditView):
    queryset = models.PackageMeasure.objects.all()
    form = forms.PackageMeasureForm


@register_model_view(models.PackageMeasure, 'delete')
class PackageMeasureDeleteView(ObjectDeleteView):
    queryset = models.PackageMeasure.objects.all()


@register_model_view(models.PackageMeasure, 'bulk_delete', detail=False)
class PackageMeasureBulkDeleteView(BulkDeleteView):
    queryset = models.PackageMeasure.objects.all()
    filterset = filtersets.PackageMeasureFilterSet
    table = tables.PackageMeasureTable
