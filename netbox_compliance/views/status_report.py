import csv

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from ..choices import ComplianceMeasureStatusChoices, CompliancePackageStatusChoices
from ..models import CompliancePackage, ComplianceMeasure
from ..services import eligible_devices_qs, get_effective_measures, package_traffic_light, score_group

__all__ = ('PackageTestStatusReportView',)

_NA_COLOR = 'grey'


def _filtered_devices_qs(site_ids=None, tenant_ids=None):
    qs = eligible_devices_qs().select_related('site', 'tenant')
    if site_ids:
        qs = qs.filter(site_id__in=site_ids)
    if tenant_ids:
        qs = qs.filter(tenant_id__in=tenant_ids)
    return qs.order_by('name')


def _resolve_package_columns(package_ids):
    """Explicit package selection wins; otherwise every active package is a column --
    mirrors _resolve_measure_columns' fallback so an empty filter bar still shows
    something meaningful instead of an empty table."""
    qs = CompliancePackage.objects.all()
    if package_ids:
        qs = qs.filter(pk__in=package_ids)
    else:
        qs = qs.filter(status=CompliancePackageStatusChoices.ACTIVE)
    return list(qs.order_by('name'))


def _resolve_measure_columns(measure_ids, package_ids):
    """Explicit test selection wins. Otherwise, if a package filter is set, narrow to
    that package's own tests (the common "how is package X doing per-test" case) --
    only falling back to every active test when neither filter is set, since that can
    be a wide column set (see the template's horizontal-scroll/sticky-column handling)."""
    if measure_ids:
        qs = ComplianceMeasure.objects.filter(pk__in=measure_ids)
    elif package_ids:
        qs = ComplianceMeasure.objects.filter(package_measures__package_id__in=package_ids).distinct()
    else:
        qs = ComplianceMeasure.objects.filter(status=ComplianceMeasureStatusChoices.ACTIVE)
    return list(qs.order_by('name'))


# ══════════════════════════════════════════════════════════════════════════════
# By Package
# ══════════════════════════════════════════════════════════════════════════════

def _build_by_package(site_ids=None, tenant_ids=None, package_ids=None, measure_ids=None):
    packages = _resolve_package_columns(package_ids)
    rows = []
    for device in _filtered_devices_qs(site_ids, tenant_ids):
        effective = get_effective_measures(device)
        cells = []
        for package in packages:
            package_rows = effective['packages'].get(package)
            if package_rows is None:
                cells.append({
                    'package': package, 'applicable': False, 'color': _NA_COLOR, 'score': None,
                })
                continue
            score, _weight = score_group(package_rows)
            cells.append({
                'package': package, 'applicable': True,
                'color': package_traffic_light(device, package, rows=package_rows),
                'score': score,
            })
        rows.append({'device': device, 'cells': cells})
    return {'packages': packages, 'rows': rows}


def _by_package_csv(data):
    response, writer = _csv_response('compliance_package_status.csv')
    writer.writerow(['Device', 'Site', 'Tenant', 'Package', 'Applicable', 'Traffic Light', 'Score'])
    for row in data['rows']:
        device = row['device']
        for cell in row['cells']:
            writer.writerow([
                device.name,
                device.site.name if device.site else '',
                device.tenant.name if device.tenant else '',
                cell['package'].name,
                'Yes' if cell['applicable'] else 'No',
                cell['color'],
                cell['score'] if cell['score'] is not None else '',
            ])
    return response


# ══════════════════════════════════════════════════════════════════════════════
# By Test
# ══════════════════════════════════════════════════════════════════════════════

def _build_by_test(site_ids=None, tenant_ids=None, package_ids=None, measure_ids=None):
    measures = _resolve_measure_columns(measure_ids, package_ids)
    rows = []
    for device in _filtered_devices_qs(site_ids, tenant_ids):
        effective = get_effective_measures(device)
        all_rows = [r for prows in effective['packages'].values() for r in prows] + effective['direct']
        row_by_measure = {r.measure.pk: r for r in all_rows}

        cells = []
        for measure in measures:
            row = row_by_measure.get(measure.pk)
            if row is None:
                cells.append({
                    'measure': measure, 'applicable': False, 'color': _NA_COLOR,
                    'status_label': 'Not Applicable', 'value': None,
                })
                continue
            cells.append({
                'measure': measure, 'applicable': True, 'color': row.display_color,
                'status_label': row.display_label, 'value': row.value,
            })
        rows.append({'device': device, 'cells': cells})
    return {'measures': measures, 'rows': rows}


def _by_test_csv(data):
    response, writer = _csv_response('compliance_test_status.csv')
    writer.writerow(['Device', 'Site', 'Tenant', 'Test', 'Severity', 'Applicable', 'Status', 'Value'])
    for row in data['rows']:
        device = row['device']
        for cell in row['cells']:
            writer.writerow([
                device.name,
                device.site.name if device.site else '',
                device.tenant.name if device.tenant else '',
                cell['measure'].name,
                cell['measure'].get_severity_display(),
                'Yes' if cell['applicable'] else 'No',
                cell['status_label'],
                cell['value'] or '',
            ])
    return response


def _csv_response(filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response, csv.writer(response)


_STATUS_REPORT_CONFIG = {
    'by_package': ('By Package', _build_by_package, _by_package_csv),
    'by_test': ('By Test', _build_by_test, _by_test_csv),
}


class PackageTestStatusReportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Filterable (site/tenant/package/test) dynamic status report, in two tabs:
    By Package shows each device's traffic light per package; By Test shows
    each device's resolved status per individual test. Both are built live off
    services.get_effective_measures per device (the same resolution used by
    the device compliance tab), not off monthly snapshots, so this always
    reflects current data -- gated behind an explicit Apply/submitted flag
    since that per-device resolution isn't free across a large fleet.
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

        filters = {}
        if form.is_valid():
            if sites := form.cleaned_data.get('site'):
                filters['site_ids'] = [s.pk for s in sites]
            if tenants := form.cleaned_data.get('tenant'):
                filters['tenant_ids'] = [t.pk for t in tenants]
            if packages := form.cleaned_data.get('package'):
                filters['package_ids'] = [p.pk for p in packages]
            if measures := form.cleaned_data.get('measure'):
                filters['measure_ids'] = [m.pk for m in measures]

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
