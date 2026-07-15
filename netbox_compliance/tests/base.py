from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Platform, Site, SiteGroup

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

    def make_device(self, name=None, **kwargs):
        _counter['n'] += 1
        name = name or f'device{_counter["n"]}'
        kwargs.setdefault('device_type', self.device_type)
        kwargs.setdefault('role', self.device_role)
        kwargs.setdefault('site', self.site)
        return Device.objects.create(name=name, **kwargs)
