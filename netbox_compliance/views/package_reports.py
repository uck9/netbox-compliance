from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from netbox.views.generic import BulkDeleteView, ObjectDeleteView, ObjectListView, ObjectView
from utilities.views import register_model_view

from .. import filtersets, forms, models, tables

__all__ = (
    'CompliancePackageReportListView',
    'CompliancePackageReportView',
    'CompliancePackageReportDeleteView',
    'CompliancePackageReportBulkDeleteView',
    'CompliancePackageReportRawView',
)


@register_model_view(models.CompliancePackageReport, 'list', path='', detail=False)
class CompliancePackageReportListView(ObjectListView):
    queryset = models.CompliancePackageReport.objects.select_related('device', 'package')
    table = tables.CompliancePackageReportTable
    filterset = filtersets.CompliancePackageReportFilterSet
    filterset_form = forms.CompliancePackageReportFilterForm
    actions = {
        'export': {'view'},
        'bulk_delete': {'delete'},
    }


@register_model_view(models.CompliancePackageReport)
class CompliancePackageReportView(ObjectView):
    queryset = models.CompliancePackageReport.objects.all()


@register_model_view(models.CompliancePackageReport, 'delete')
class CompliancePackageReportDeleteView(ObjectDeleteView):
    queryset = models.CompliancePackageReport.objects.all()


@register_model_view(models.CompliancePackageReport, 'bulk_delete', detail=False)
class CompliancePackageReportBulkDeleteView(BulkDeleteView):
    queryset = models.CompliancePackageReport.objects.all()
    filterset = filtersets.CompliancePackageReportFilterSet
    table = tables.CompliancePackageReportTable


class CompliancePackageReportRawView(View):
    """Serves a report's stored HTML back verbatim -- it's already a self-contained document
    (the same renderer config-compliance-engine's `--report-html`/`smoke-test` produce locally),
    not something to re-wrap in NetBox's own page chrome."""

    def get(self, request, pk):
        report = get_object_or_404(models.CompliancePackageReport, pk=pk)
        return HttpResponse(report.html, content_type='text/html')
