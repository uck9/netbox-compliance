from django.urls import reverse

from netbox.plugins import PluginTemplateExtension

from .services import get_device_panel_data

__all__ = ('DeviceCompliancePanel',)


class DeviceCompliancePanel(PluginTemplateExtension):
    """
    Injects a traffic-light Compliance card onto the core dcim.Device detail
    page (spec B3), separate from and in addition to the plugin's own
    Compliance tab. Renders nothing if the device has no pinned
    packages/measures, so devices with no compliance configuration don't get
    an empty card.
    """
    models = ['dcim.device']

    def right_page(self):
        device = self.context.get('object')
        panel = get_device_panel_data(device)
        if not panel['packages'] and not panel['measures']:
            return ''
        tab_url = reverse('dcim:device_compliance', kwargs={'pk': device.pk})
        return self.render(
            'netbox_compliance/inc/device_panel.html',
            extra_context={'panel': panel, 'tab_url': tab_url},
        )


template_extensions = (DeviceCompliancePanel,)
