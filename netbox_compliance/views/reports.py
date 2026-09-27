import csv
from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from ..models import ComplianceSnapshot
from ..services import measure_adherence_matrix, overall_compliance_trend
from ..tables import ComplianceSnapshotTable

__all__ = ('MonthlyReportView', 'MeasureAdherenceTrendView')


class MonthlyReportView(View):
    """
    Pick a period -> fleet summary (compliant/non-compliant/score
    distribution), per-device table filterable by site/role/tag/package,
    CSV export. Drill into an individual device's snapshot via the standard
    ComplianceSnapshot detail view (linked from the table).
    """

    def get(self, request):
        periods = list(
            ComplianceSnapshot.objects.order_by('-period').values_list('period', flat=True).distinct()
        )

        period = None
        period_param = request.GET.get('period')
        if period_param:
            try:
                period = datetime.strptime(period_param, '%Y-%m').date().replace(day=1)
            except ValueError:
                period = None
        if period is None and periods:
            period = periods[0]

        snapshots_qs = ComplianceSnapshot.objects.filter(period=period).select_related('device') if period else ComplianceSnapshot.objects.none()

        site_id = request.GET.get('site_id')
        role_id = request.GET.get('role_id')
        tag_id = request.GET.get('tag_id')
        package_slug = request.GET.get('package')

        if site_id:
            snapshots_qs = snapshots_qs.filter(site_id=site_id)
        if role_id:
            snapshots_qs = snapshots_qs.filter(role_id=role_id)
        if tag_id:
            snapshots_qs = snapshots_qs.filter(device__tags__id=tag_id)

        snapshots = list(snapshots_qs.order_by('device_name'))
        if package_slug:
            snapshots = [
                snap for snap in snapshots
                if any(pkg.get('package') == package_slug for pkg in snap.data.get('packages', []))
            ]

        if 'export' in request.GET:
            return self._export_csv(snapshots, period)

        total = len(snapshots)
        compliant_count = sum(1 for snap in snapshots if snap.compliant)

        table = ComplianceSnapshotTable(snapshots)
        table.configure(request)

        return render(request, 'netbox_compliance/report.html', {
            'period': period,
            'periods': periods,
            'table': table,
            'total': total,
            'compliant_count': compliant_count,
            'non_compliant_count': total - compliant_count,
            'compliance_pct': round(100 * compliant_count / total, 1) if total else None,
        })

    @staticmethod
    def _export_csv(snapshots, period):
        response = HttpResponse(content_type='text/csv')
        period_label = period.strftime('%Y-%m') if period else 'none'
        response['Content-Disposition'] = f'attachment; filename="compliance-report-{period_label}.csv"'

        writer = csv.writer(response)
        writer.writerow(['device', 'period', 'overall_score', 'compliant'])
        for snap in snapshots:
            writer.writerow([snap.device_name, snap.period, snap.overall_score, snap.compliant])

        return response


class MeasureAdherenceTrendView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    "Is adherence to our measures actually improving" report: one row per
    measure, one column per month, each cell the fleet-wide (or site/role-
    scoped) pass rate for that measure that period -- so a run of cells
    going grey/red -> amber -> green reads as visible progress. Paired with
    a headline %-fully-compliant-devices trend from overall_compliance_trend.
    Built entirely off ComplianceSnapshotMeasureResult/ComplianceSnapshot
    (see measure_adherence_matrix), so it's fast even over a year of history
    -- unlike PackageTestStatusReportView, which resolves live per device.
    """
    permission_required = 'netbox_compliance.view_compliancesnapshot'
    template_name = 'netbox_compliance/measure_trend_report.html'
    DEFAULT_MONTHS = 12

    def get(self, request):
        from ..forms.reports import TrendReportFilterForm

        form = TrendReportFilterForm(request.GET or None)
        site_id = role_id = package_slug = None
        months = self.DEFAULT_MONTHS
        if form.is_valid():
            site_id = form.cleaned_data['site'].pk if form.cleaned_data.get('site') else None
            role_id = form.cleaned_data['role'].pk if form.cleaned_data.get('role') else None
            package_slug = form.cleaned_data['package'].slug if form.cleaned_data.get('package') else None
            months = form.cleaned_data.get('months') or self.DEFAULT_MONTHS

        all_periods = list(
            ComplianceSnapshot.objects.order_by('-period').values_list('period', flat=True).distinct()
        )
        # all_periods is newest-first; take the most recent `months` then flip to
        # oldest-first so the matrix/template read left-to-right as a timeline.
        window = list(reversed(all_periods[:months]))

        periods, measure_rows = measure_adherence_matrix(
            site_id=site_id, role_id=role_id, package=package_slug, periods=window,
        )
        overall_trend = overall_compliance_trend(site_id=site_id, role_id=role_id, periods=window)

        if 'export' in request.GET:
            return self._export_csv(periods, measure_rows)

        export_params = request.GET.copy()
        export_params['export'] = 'csv'

        return render(request, self.template_name, {
            'form': form,
            'periods': periods,
            'measure_rows': measure_rows,
            'overall_trend': overall_trend,
            'has_history': bool(all_periods),
            'export_url': '?' + export_params.urlencode(),
        })

    @staticmethod
    def _export_csv(periods, measure_rows):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="compliance-measure-trend.csv"'

        writer = csv.writer(response)
        writer.writerow(['package', 'measure'] + [p.strftime('%Y-%m') for p in periods])
        for row in measure_rows:
            writer.writerow(
                [row['package_name'], row['measure_name']]
                + [cell['pct'] if cell['pct'] is not None else '' for cell in row['cells']]
            )

        return response
