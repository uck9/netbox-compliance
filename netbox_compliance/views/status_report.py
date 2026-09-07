import csv

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from ..reporting import build_by_package, build_by_test, counter_summary, extract_filters

__all__ = ('PackageTestStatusReportView',)


def _by_package_csv(data):
    response, writer = _csv_response('compliance_package_status.csv')
    writer.writerow([
        'Device', 'Site', 'Site Score', 'Tenant', 'Role', 'Device Score', 'Device Failing Tests',
        'Package', 'Traffic Light', 'Package Score', 'Package Failing Tests',
    ])
    for site_entry in data['sites']:
        site_score = site_entry['score'] if site_entry['score'] is not None and site_entry['evaluated'] else ''
        for entry in site_entry['devices']:
            device = entry['device']
            dev_score = entry['score'] if entry['score'] is not None and entry['evaluated'] else ''
            for row in entry['rows']:
                writer.writerow([
                    device.name,
                    device.site.name if device.site else '',
                    site_score,
                    device.tenant.name if device.tenant else '',
                    device.role.name if device.role else '',
                    dev_score,
                    counter_summary(entry['counters']),
                    row['package'].name,
                    row['color'],
                    row['score'] if row['score'] is not None and row['evaluated'] else '',
                    counter_summary(row['counters']),
                ])
    return response


def _by_test_csv(data):
    response, writer = _csv_response('compliance_test_status.csv')
    writer.writerow([
        'Device', 'Site', 'Site Score', 'Tenant', 'Role', 'Device Score', 'Device Failing Tests',
        'Test', 'Severity', 'Status', 'Value',
    ])
    for site_entry in data['sites']:
        site_score = site_entry['score'] if site_entry['score'] is not None and site_entry['evaluated'] else ''
        for entry in site_entry['devices']:
            device = entry['device']
            dev_score = entry['score'] if entry['score'] is not None and entry['evaluated'] else ''
            for cell in entry['rows']:
                writer.writerow([
                    device.name,
                    device.site.name if device.site else '',
                    site_score,
                    device.tenant.name if device.tenant else '',
                    device.role.name if device.role else '',
                    dev_score,
                    counter_summary(entry['counters']),
                    cell['measure'].name,
                    cell['measure'].get_severity_display(),
                    cell['status_label'],
                    cell['value'] or '',
                ])
    return response


def _csv_response(filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response, csv.writer(response)


_STATUS_REPORT_CONFIG = {
    'by_package': ('By Package', build_by_package, _by_package_csv),
    'by_test': ('By Test', build_by_test, _by_test_csv),
}


class PackageTestStatusReportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Filterable (site/tenant/package/test/criticality) dynamic status report, in
    two tabs. Both group devices into a box per site; under each device only the
    packages (By Package) or tests (By Test) that actually apply to it are
    listed -- non-applicable rows are omitted entirely. Each device shows its
    overall score plus a Fail/Error/Stale count by severity, and on the By
    Package tab each package row carries its own such count.

    Resolution lives in ``reporting.build_by_package`` / ``build_by_test`` (also
    used by the REST endpoint) -- gated here behind an explicit Apply/submitted
    flag since that per-device resolution isn't free across a large fleet.
    """
    permission_required = 'netbox_compliance.view_complianceresult'
    template_name = 'netbox_compliance/status_report.html'

    def get(self, request):
        from ..forms.reports import StatusReportFilterForm

        report_key = request.GET.get('report', 'by_package')
        if report_key not in _STATUS_REPORT_CONFIG:
            report_key = 'by_package'

        form = StatusReportFilterForm(request.GET or None)
        submitted = 'submitted' in request.GET

        filters = extract_filters(form.cleaned_data) if form.is_valid() else {}

        label, builder, csv_func = _STATUS_REPORT_CONFIG[report_key]
        data = builder(**filters) if submitted else {}

        if submitted and request.GET.get('format') == 'csv':
            return csv_func(data)

        tab_urls = {}
        for key in _STATUS_REPORT_CONFIG:
            params = request.GET.copy()
            params['report'] = key
            params.pop('format', None)
            tab_urls[key] = '?' + params.urlencode()

        csv_params = request.GET.copy()
        csv_params['format'] = 'csv'

        return render(request, self.template_name, {
            **data,
            'form': form,
            'report_key': report_key,
            'report_label': label,
            'tab_urls': tab_urls,
            'csv_url': '?' + csv_params.urlencode(),
            'submitted': submitted,
        })
