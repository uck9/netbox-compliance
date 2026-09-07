import csv
from collections import Counter, OrderedDict

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from ..choices import ComplianceMeasureSeverityChoices, EffectiveStatusChoices
from ..services import (
    eligible_devices_qs,
    get_effective_measures,
    package_traffic_light,
    score_device,
    score_group,
)

__all__ = ('PackageTestStatusReportView',)

# "Something is wrong and it counts": Fail / Error / Stale. Pass, Exempt,
# Not Applicable and Pending never contribute to a severity counter.
_FAILING_STATUSES = (
    EffectiveStatusChoices.FAIL,
    EffectiveStatusChoices.ERROR,
    EffectiveStatusChoices.STALE,
)
_PASSING_STATUSES = (EffectiveStatusChoices.PASS, EffectiveStatusChoices.EXEMPT)

_SEVERITY_ORDER = [value for value, *_ in ComplianceMeasureSeverityChoices.CHOICES]
_SEVERITY_LABELS = {value: label for value, label, *_ in ComplianceMeasureSeverityChoices.CHOICES}
_SEVERITY_COLORS = {
    value: (rest[0] if rest else 'grey')
    for value, _label, *rest in ComplianceMeasureSeverityChoices.CHOICES
}
# Compact labels for the counter badges so a full row of severities fits on one line.
_SEVERITY_SHORT = {
    ComplianceMeasureSeverityChoices.CRITICAL: 'Crit',
    ComplianceMeasureSeverityChoices.HIGH: 'High',
    ComplianceMeasureSeverityChoices.MEDIUM: 'Med',
    ComplianceMeasureSeverityChoices.LOW: 'Low',
    ComplianceMeasureSeverityChoices.INFORMATIONAL: 'Info',
}


def _filtered_devices_qs(site_ids=None, tenant_ids=None):
    qs = eligible_devices_qs().select_related('site', 'tenant', 'role', 'device_type')
    if site_ids:
        qs = qs.filter(site_id__in=site_ids)
    if tenant_ids:
        qs = qs.filter(tenant_id__in=tenant_ids)
    return qs.order_by('name')


def _grouped_by_site(devices):
    """Group a name-sorted device iterable into (site, [devices]) pairs: named sites
    alphabetically, then the 'no site' bucket (if any) last. Device order within each
    group is preserved from the queryset (already name-sorted)."""
    groups = OrderedDict()
    for device in devices:
        groups.setdefault(device.site, []).append(device)
    named = sorted((s for s in groups if s is not None), key=lambda s: s.name.lower())
    ordered = [(s, groups[s]) for s in named]
    if None in groups:
        ordered.append((None, groups[None]))
    return ordered


def _severity_counters(rows, allowed=None):
    """(counters, total) where counters is [{severity,label,short,color,count}] for the
    rows in a Fail/Error/Stale state, in severity order, non-zero entries only.
    `allowed`, if given, restricts the tally to those severities (the Criticality filter)."""
    counts = Counter(
        r.measure.severity for r in rows
        if r.status in _FAILING_STATUSES and (allowed is None or r.measure.severity in allowed)
    )
    counters = [
        {
            'severity': sev,
            'label': _SEVERITY_LABELS.get(sev, sev),
            'short': _SEVERITY_SHORT.get(sev, _SEVERITY_LABELS.get(sev, sev)),
            'color': _SEVERITY_COLORS.get(sev, 'grey'),
            'count': counts[sev],
        }
        for sev in _SEVERITY_ORDER
        if counts.get(sev)
    ]
    return counters, sum(counts.values())


def _score_color(score):
    """Display-only chip colour. 100 (== compliant) is the only threshold the model
    defines fleet-wide; below that we just split 'close' from 'poor' for triage."""
    if score is None:
        return 'grey'
    if score >= 100:
        return 'green'
    if score >= 80:
        return 'amber'
    return 'red'


def _device_score_display(device, effective):
    """(score, color) for a device's overall score chip."""
    score = score_device(device, effective=effective)['overall_score']
    return score, _score_color(score)


def _group_score(rows):
    """(score, color) rolled up over an arbitrary bag of EffectiveMeasure rows via the
    same credit maths as a package/device -- used for the per-site score. None when
    nothing scorable was listed."""
    score, weight = score_group(rows)
    if not weight:
        return None, _score_color(None)
    return score, _score_color(score)


def _counter_summary(counters):
    """'Critical:1, High:2' -- compact one-cell form of _severity_counters output, for CSV."""
    return ', '.join(f"{c['label']}:{c['count']}" for c in counters)


# ══════════════════════════════════════════════════════════════════════════════
# By Package
# ══════════════════════════════════════════════════════════════════════════════

def _build_by_package(site_ids=None, tenant_ids=None, package_ids=None, measure_ids=None,
                      severity_values=None):
    package_filter = set(package_ids or ())
    severity_filter = set(severity_values) if severity_values else None
    sites = []
    total_devices = 0
    for site, devices in _grouped_by_site(_filtered_devices_qs(site_ids, tenant_ids)):
        device_entries = []
        noncompliant = 0
        site_rows = []
        for device in devices:
            effective = get_effective_measures(device)
            applicable = [
                (package, rows)
                for package, rows in effective['packages'].items()
                if not package_filter or package.pk in package_filter
            ]
            if not applicable:
                # Every package row for this device was excluded -- drop the device.
                continue
            applicable.sort(key=lambda pr: pr[0].name.lower())

            rows = []
            device_measure_rows = []
            for package, package_rows in applicable:
                score, _weight = score_group(package_rows)
                color = package_traffic_light(device, package, rows=package_rows)
                counters, _total = _severity_counters(package_rows, severity_filter)
                rows.append({
                    'package': package,
                    'color': color,
                    'score': score,
                    'counters': counters,
                })
                device_measure_rows.extend(package_rows)

            if any(r['color'] == 'red' for r in rows):
                noncompliant += 1
            site_rows.extend(device_measure_rows)
            dev_score, dev_color = _device_score_display(device, effective)
            dev_counters, dev_total = _severity_counters(device_measure_rows, severity_filter)
            device_entries.append({
                'device': device,
                'score': dev_score,
                'score_color': dev_color,
                'counters': dev_counters,
                'total_fail': dev_total,
                'rows': rows,
            })

        if device_entries:
            total_devices += len(device_entries)
            site_score, site_score_color = _group_score(site_rows)
            sites.append({
                'site': site,
                'devices': device_entries,
                'device_count': len(device_entries),
                'noncompliant_count': noncompliant,
                'score': site_score,
                'score_color': site_score_color,
            })
    return {'sites': sites, 'total_devices': total_devices, 'tab': 'by_package'}


def _by_package_csv(data):
    response, writer = _csv_response('compliance_package_status.csv')
    writer.writerow([
        'Device', 'Site', 'Site Score', 'Tenant', 'Role', 'Device Score', 'Device Failing Tests',
        'Package', 'Traffic Light', 'Package Score', 'Package Failing Tests',
    ])
    for site_entry in data['sites']:
        site_score = site_entry['score'] if site_entry['score'] is not None else ''
        for entry in site_entry['devices']:
            device = entry['device']
            for row in entry['rows']:
                writer.writerow([
                    device.name,
                    device.site.name if device.site else '',
                    site_score,
                    device.tenant.name if device.tenant else '',
                    device.role.name if device.role else '',
                    entry['score'] if entry['score'] is not None else '',
                    _counter_summary(entry['counters']),
                    row['package'].name,
                    row['color'],
                    row['score'] if row['score'] is not None else '',
                    _counter_summary(row['counters']),
                ])
    return response


# ══════════════════════════════════════════════════════════════════════════════
# By Test
# ══════════════════════════════════════════════════════════════════════════════

def _build_by_test(site_ids=None, tenant_ids=None, package_ids=None, measure_ids=None,
                   severity_values=None):
    measure_filter = set(measure_ids or ())
    package_filter = set(package_ids or ())
    severity_filter = set(severity_values) if severity_values else None
    sites = []
    total_devices = 0
    for site, devices in _grouped_by_site(_filtered_devices_qs(site_ids, tenant_ids)):
        device_entries = []
        failing_tests = 0
        site_rows = []
        for device in devices:
            effective = get_effective_measures(device)
            all_rows = [r for prows in effective['packages'].values() for r in prows] + effective['direct']

            rows = []
            seen = set()
            for row in all_rows:
                if row.measure.pk in seen:
                    continue
                seen.add(row.measure.pk)
                if measure_filter:
                    if row.measure.pk not in measure_filter:
                        continue
                elif package_filter:
                    # Package set, Test blank: narrow to that package's own tests
                    # (direct measures have no source package, so they drop out here).
                    if not any(p.pk in package_filter for p in row.source_packages):
                        continue
                if severity_filter and row.measure.severity not in severity_filter:
                    continue
                if row.status == EffectiveStatusChoices.NOT_APPLICABLE:
                    continue
                rows.append(row)

            if not rows:
                continue
            rows.sort(key=lambda r: (_SEVERITY_ORDER.index(r.measure.severity), r.measure.name.lower()))

            cells = [{
                'measure': row.measure,
                'severity': row.measure.severity,
                'color': row.display_color,
                'status_label': row.display_label,
                'value': row.value,
                'passing': row.status in _PASSING_STATUSES,
            } for row in rows]

            site_rows.extend(rows)
            counters, total = _severity_counters(rows)
            failing_tests += total
            dev_score, dev_color = _device_score_display(device, effective)
            device_entries.append({
                'device': device,
                'score': dev_score,
                'score_color': dev_color,
                'counters': counters,
                'total_fail': total,
                'rows': cells,
            })

        if device_entries:
            total_devices += len(device_entries)
            site_score, site_score_color = _group_score(site_rows)
            sites.append({
                'site': site,
                'devices': device_entries,
                'device_count': len(device_entries),
                'failing_test_count': failing_tests,
                'score': site_score,
                'score_color': site_score_color,
            })
    return {'sites': sites, 'total_devices': total_devices, 'tab': 'by_test'}


def _by_test_csv(data):
    response, writer = _csv_response('compliance_test_status.csv')
    writer.writerow([
        'Device', 'Site', 'Site Score', 'Tenant', 'Role', 'Device Score', 'Device Failing Tests',
        'Test', 'Severity', 'Status', 'Value',
    ])
    for site_entry in data['sites']:
        site_score = site_entry['score'] if site_entry['score'] is not None else ''
        for entry in site_entry['devices']:
            device = entry['device']
            for cell in entry['rows']:
                writer.writerow([
                    device.name,
                    device.site.name if device.site else '',
                    site_score,
                    device.tenant.name if device.tenant else '',
                    device.role.name if device.role else '',
                    entry['score'] if entry['score'] is not None else '',
                    _counter_summary(entry['counters']),
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
    'by_package': ('By Package', _build_by_package, _by_package_csv),
    'by_test': ('By Test', _build_by_test, _by_test_csv),
}


class PackageTestStatusReportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Filterable (site/tenant/package/test) dynamic status report, in two tabs.
    Both group devices into a box per site; under each device only the
    packages (By Package) or tests (By Test) that actually apply to it are
    listed -- non-applicable rows are omitted entirely. Each device shows
    its overall score plus a Fail/Error/Stale count by severity, and on the
    By Package tab each package row carries its own such count.

    Everything is resolved live off services.get_effective_measures per
    device (the same resolution the device compliance tab uses), not off
    monthly snapshots -- gated behind an explicit Apply/submitted flag since
    that per-device resolution isn't free across a large fleet.
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
            severities = form.cleaned_data.get('severity') or []
            # All (or none) selected == no restriction; a partial selection filters.
            if severities and len(severities) < len(_SEVERITY_ORDER):
                filters['severity_values'] = list(severities)

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
