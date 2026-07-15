from django.template.loader import render_to_string

from extras.dashboard.utils import register_widget
from extras.dashboard.widgets import DashboardWidget

__all__ = ('ComplianceFleetWidget',)


@register_widget
class ComplianceFleetWidget(DashboardWidget):
    default_title = 'Fleet Compliance'
    description = 'Current fleet-wide compliance percentage and count of failing devices.'
    template_name = 'netbox_compliance/widgets/fleet_compliance.html'
    width = 4
    height = 3

    def render(self, request):
        from .services import devices_with_effective_measures, score_device

        devices = devices_with_effective_measures()
        total = devices.count()
        compliant = 0
        for device in devices:
            if score_device(device)['compliant']:
                compliant += 1
        failing = total - compliant
        pct = round(100 * compliant / total, 1) if total else None

        return render_to_string(self.template_name, {
            'total': total,
            'compliant': compliant,
            'failing': failing,
            'pct': pct,
        })
