from dcim.models import Device
from netbox.views import generic
from utilities.views import ViewTab

from .. import services

__all__ = ('DeviceComplianceTabView',)


def _device_compliance_badge(obj):
    scoring = services.score_device(obj)
    return f"{scoring['overall_score']}%"


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
        badge=_device_compliance_badge,
        weight=4000,
    )

    def get_extra_context(self, request, instance):
        scoring = services.score_device(instance)
        effective = scoring['effective']

        packages = []
        for package in sorted(effective['packages'], key=lambda p: p.name):
            rows = sorted(effective['packages'][package], key=lambda r: (r.display_order, r.measure.name))
            packages.append({
                'package': package,
                'score': scoring['package_scores'][package],
                'traffic_light': services.package_traffic_light(instance, package, rows=rows),
                'rows': rows,
            })

        direct_rows = sorted(effective['direct'], key=lambda r: r.measure.name)

        return {
            'overall_score': scoring['overall_score'],
            'compliant': scoring['compliant'],
            'packages': packages,
            'direct_rows': direct_rows,
            'exemptions_applied': effective['exemptions_applied'],
        }
