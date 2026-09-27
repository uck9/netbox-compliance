from django.test import TestCase

from tenancy.models import Tenant

from ..choices import CompliancePackageStatusChoices
from ..forms import PackageAssignmentForm
from ..models import CompliancePackage, PackageAssignment
from .base import ComplianceTestMixin


class PackageAssignmentFormTest(ComplianceTestMixin, TestCase):
    """PackageAssignmentForm.clean() used to do `cleaned_data = super().clean()`.
    On an *add*, NetBoxModelForm's clean chain runs through CheckLastUpdatedMixin.clean(),
    which returns None (not the dict) for an unsaved instance -- so `cleaned_data` came
    back None and `cleaned_data.get('tenants')` raised
    `AttributeError: 'NoneType' object has no attribute 'get'`. clean() now reads
    self.cleaned_data instead."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.package = CompliancePackage.objects.create(
            name='Package1', slug='package1', status=CompliancePackageStatusChoices.ACTIVE,
        )
        cls.tenant = Tenant.objects.create(name='Tenant1', slug='tenant1')

    def test_add_with_single_scope_is_valid(self):
        form = PackageAssignmentForm(data={'package': self.package.pk, 'site': self.site.pk})

        self.assertTrue(form.is_valid(), form.errors)

    def test_add_saves(self):
        form = PackageAssignmentForm(data={'package': self.package.pk, 'platform': self.platform.pk})

        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(PackageAssignment.objects.get(pk=obj.pk).platform_id, self.platform.pk)

    def test_add_no_scope_is_invalid(self):
        form = PackageAssignmentForm(data={'package': self.package.pk})

        self.assertFalse(form.is_valid())

    def test_add_tenant_narrowing_with_device_scope_is_invalid(self):
        device = self.make_device()
        form = PackageAssignmentForm(data={
            'package': self.package.pk,
            'device': device.pk,
            'tenants': [self.tenant.pk],
        })

        self.assertFalse(form.is_valid())
        self.assertIn('tenants', form.errors)

    def test_edit_existing_assignment_is_valid(self):
        obj = PackageAssignment.objects.create(package=self.package, site=self.site)
        form = PackageAssignmentForm(
            data={'package': self.package.pk, 'site': self.site.pk, 'description': 'updated'},
            instance=obj,
        )

        self.assertTrue(form.is_valid(), form.errors)
