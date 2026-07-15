import csv
from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from ..models import ComplianceSnapshot
from ..tables import ComplianceSnapshotTable

__all__ = ('MonthlyReportView',)


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
            snapshots_qs = snapshots_qs.filter(device__site_id=site_id)
        if role_id:
            snapshots_qs = snapshots_qs.filter(device__role_id=role_id)
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
