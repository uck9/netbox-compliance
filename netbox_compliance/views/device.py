from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View

from dcim.models import Device
from netbox.views import generic
from utilities.views import ViewTab

from .. import services
from ..choices import EffectiveStatusChoices
from ..models import CompliancePackageReport

__all__ = ('DeviceComplianceTabView', 'DeviceComplianceExportView')


def _build_device_compliance_context(device):
    """
    Shared by the Compliance tab and the standalone export document -- both show
    the same resolved data, just presented differently (interactive/collapsible
    tab vs. one flat printable document), so the resolution/grouping logic lives
    in exactly one place.
    """
    scoring = services.score_device(device)
    effective = scoring['effective']

    package_reports_by_id = {
        report.package_id: report
        for report in CompliancePackageReport.objects.filter(
            device=device, package_id__in=[p.pk for p in effective['packages']],
        )
    }

    packages = []
    for package in sorted(effective['packages'], key=lambda p: p.name):
        rows = sorted(effective['packages'][package], key=lambda r: (r.display_order, r.measure.name))
        for row in rows:
            row.value_display = services.render_display_template(row)
        passing_rows = [row for row in rows if row.status == EffectiveStatusChoices.PASS]
        not_applicable_rows = [row for row in rows if row.status == EffectiveStatusChoices.NOT_APPLICABLE]
        failing_rows = [
            row for row in rows
            if row.status not in (EffectiveStatusChoices.PASS, EffectiveStatusChoices.NOT_APPLICABLE)
        ]
        packages.append({
            'package': package,
            'score': scoring['package_scores'][package],
            'traffic_light': services.package_traffic_light(device, package, rows=rows),
            'package_report': package_reports_by_id.get(package.pk),
            'rows': rows,
            'passing_rows': passing_rows,
            'failing_rows': failing_rows,
            'not_applicable_rows': not_applicable_rows,
            'passing_count': len(passing_rows),
            'failing_count': len(failing_rows),
            'not_applicable_count': len(not_applicable_rows),
        })

    direct_rows = sorted(effective['direct'], key=lambda r: r.measure.name)
    for row in direct_rows:
        row.value_display = services.render_display_template(row)

    return {
        'packages': packages,
        'direct_rows': direct_rows,
        'exemptions_applied': effective['exemptions_applied'],
        'overall_score': scoring['overall_score'],
        'compliant': scoring['compliant'],
    }


class DeviceComplianceTabView(generic.ObjectView):
    """
    "Compliance" tab on the core Device detail page: resolved effective
    measures, current status, and per-package/overall scores.

    Registered against dcim.Device in NetBoxComplianceConfig.ready() (see
    netbox_compliance/__init__.py) rather than via a decorator here: dcim's
    urls.py is imported before this plugin's urls.py in netbox/urls.py, so
    registering only when this module is imported would be too late for
    dcim's get_model_urls('dcim', 'device') call to pick it up.
    """
    queryset = Device.objects.all()
    template_name = 'netbox_compliance/device/compliance.html'

    tab = ViewTab(
        label='Compliance',
        weight=4000,
    )

    def get_extra_context(self, request, instance):
        return _build_device_compliance_context(instance)


class DeviceComplianceExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    One combined, self-contained, printable/downloadable compliance document
    for a single device -- every package (with its stored raw
    CompliancePackageReport embedded verbatim when one exists, alongside our
    own always-present summary table so nothing's missing just because an
    external report was never posted for that package), every direct
    measure, and applied exemptions, as one flat document instead of the
    tab's collapsible per-package cards.

    Deliberately does NOT extend base/layout.html or use NetBox's {% badge %}
    tag (whose `text-bg-<color>` classes only resolve when NetBox's own
    compiled CSS is loaded) -- this needs to render correctly even after
    being downloaded and opened offline or emailed, the same "self-contained"
    posture CompliancePackageReport.html itself already has. Colors are
    inlined via the compliance_export templatetag instead.

    Pass ?download=1 to force a file download instead of viewing inline (the
    same query-param convention this plugin's other reports use for CSV,
    e.g. PackageTestStatusReportView's ?format=csv).
    """
    permission_required = 'dcim.view_device'
    template_name = 'netbox_compliance/device/compliance_export.html'

    def get(self, request, pk):
        device = get_object_or_404(Device.objects.select_related('site', 'tenant', 'role', 'platform'), pk=pk)
        context = _build_device_compliance_context(device)
        context.update({'device': device, 'generated_at': timezone.now()})

        response = render(request, self.template_name, context, content_type='text/html')
        if request.GET.get('download'):
            filename = f'{device.name}-compliance-report.html'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
