from netbox.plugins import PluginConfig

from .version import __version__


class NetBoxComplianceConfig(PluginConfig):
    name = 'netbox_compliance'
    verbose_name = 'NetBox Compliance'
    version = __version__
    description = 'Device compliance measure tracking, scoring, and monthly snapshot reporting'
    author = 'Nathan Reeves'
    author_email = ''
    base_url = 'compliance'
    min_version = '4.5.0'
    default_settings = {
        'result_retention_days': 90,
        'default_max_result_age_days': 35,
        'snapshot_day_of_month': 1,
    }

    def register_device_compliance_tab(self) -> None:
        """
        Register the Compliance tab on dcim.Device. Must happen here (during
        app loading) rather than relying on this plugin's own urls.py, since
        dcim's urls.py is imported before this plugin's urls.py in
        netbox/urls.py -- by then dcim's get_model_urls('dcim', 'device')
        call has already run and would miss a registration done later.
        """
        from dcim.models import Device
        from utilities.views import register_model_view

        register_model_view(Device, 'compliance')(
            'netbox_compliance.views.DeviceComplianceTabView',
        )

    def ready(self):
        super().ready()
        from . import dashboard, jobs  # noqa: F401

        self.register_device_compliance_tab()


config = NetBoxComplianceConfig
