from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Platform, Site, SiteGroup
from ipam.models import IPAddress

_counter = {'n': 0}


class ComplianceTestMixin:
    """Shared dcim fixture creation for compliance tests."""

    @classmethod
    def setUpTestData(cls):
        cls.manufacturer = Manufacturer.objects.create(name='Manufacturer1', slug='manufacturer1')
        cls.device_type = DeviceType.objects.create(
            manufacturer=cls.manufacturer, model='DeviceType1', slug='devicetype1',
        )
        cls.device_role = DeviceRole.objects.create(name='Role1', slug='role1')
        cls.device_role2 = DeviceRole.objects.create(name='Role2', slug='role2')
        cls.site_group = SiteGroup.objects.create(name='SiteGroup1', slug='sitegroup1')
        cls.site = Site.objects.create(name='Site1', slug='site1', group=cls.site_group)
        cls.site2 = Site.objects.create(name='Site2', slug='site2')
        cls.platform = Platform.objects.create(name='Platform1', slug='platform1')

    def make_device(self, name=None, primary_ip=True, **kwargs):
        """`primary_ip=True` (default) assigns a synthetic primary IPv4 so devices are eligible
        for compliance tracking by default -- see services.is_device_eligible_for_compliance.
        Most tests exercise scoring/resolution behavior unrelated to eligibility itself; tests
        that specifically cover the no-primary-IP/non-master-VC-member gate pass
        `primary_ip=False` (or set one up manually) to build the ineligible case on purpose."""
        _counter['n'] += 1
        name = name or f'device{_counter["n"]}'
        kwargs.setdefault('device_type', self.device_type)
        kwargs.setdefault('role', self.device_role)
        kwargs.setdefault('site', self.site)
        device = Device.objects.create(name=name, **kwargs)
        if primary_ip:
            interface = Interface.objects.create(device=device, name='mgmt0', type='virtual')
            ip = IPAddress.objects.create(
                address=f'10.{(_counter["n"] // 65536) % 256}.{(_counter["n"] // 256) % 256}.{_counter["n"] % 256}/32',
                assigned_object=interface,
            )
            device.primary_ip4 = ip
            device.save()
        return device
