from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import Platform

from ..choices import CompliancePackageStatusChoices
from ..models import CompliancePackage, PackageAssignment
from .base import ComplianceTestMixin


class CompliancePackageDevicesViewTest(ComplianceTestMixin, TestCase):
    """The 'Devices' tab on a CompliancePackage -- shows devices_for_package()'s result (see
    test_services.py's AssignmentScopeDeviceResolutionTest for the underlying resolution logic),
    including devices that only match via a child platform of a platform-scoped assignment."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.package = CompliancePackage.objects.create(
            name='Package1', slug='package1', status=CompliancePackageStatusChoices.ACTIVE,
        )
        cls.child_platform = Platform.objects.create(name='ChildPlatform', slug='child-platform', parent=cls.platform)
        PackageAssignment.objects.create(package=cls.package, platform=cls.platform)

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(username='tester', password='pw')
        self.client.force_login(self.user)

    def test_devices_tab_lists_child_platform_device(self):
        device = self.make_device(platform=self.child_platform)

        response = self.client.get(reverse('plugins:netbox_compliance:compliancepackage_devices', args=[self.package.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, device.name)

    def test_devices_tab_excludes_unrelated_device(self):
        device = self.make_device(platform=self.child_platform)
        unrelated = self.make_device(name='unrelated-device')

        response = self.client.get(reverse('plugins:netbox_compliance:compliancepackage_devices', args=[self.package.pk]))

        self.assertContains(response, device.name)
        self.assertNotContains(response, unrelated.name)
