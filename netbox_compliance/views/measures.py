from django.db.models import Count

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
        device_count = 0
        try:
            from dcim.models import Device

            device_ids = set()
            for assignment in instance.assignments.all():
                qs = Device.objects.all()
                if assignment.device_id:
                    qs = qs.filter(pk=assignment.device_id)
                elif assignment.device_role_id:
                    qs = qs.filter(role_id=assignment.device_role_id)
                elif assignment.site_id:
                    qs = qs.filter(site_id=assignment.site_id)
                elif assignment.site_group_id:
                    qs = qs.filter(site__group_id=assignment.site_group_id)
                elif assignment.platform_id:
                    qs = qs.filter(platform_id=assignment.platform_id)
                elif assignment.tag_id:
                    qs = qs.filter(tags=assignment.tag_id)
                else:
                    continue
                device_ids.update(qs.values_list('pk', flat=True))
            device_count = len(device_ids)
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
        return self.child_model.objects.filter(package=parent).order_by('display_order', 'measure__name')


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
