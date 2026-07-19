from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import Platform

from ..choices import CompliancePackageStatusChoices
from ..forms import PackageAssignmentBulkAssignForm
from ..models import CompliancePackage, PackageAssignment
from .base import ComplianceTestMixin


class PackageAssignmentBulkAssignFormTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.package = CompliancePackage.objects.create(
            name='Package1', slug='package1', status=CompliancePackageStatusChoices.ACTIVE,
        )
        cls.platform2 = Platform.objects.create(name='Platform2', slug='platform2')

    def test_no_scope_selected_is_invalid(self):
        form = PackageAssignmentBulkAssignForm(data={'package': self.package.pk})
        self.assertFalse(form.is_valid())

    def test_two_scope_fields_selected_is_invalid(self):
        form = PackageAssignmentBulkAssignForm(data={
            'package': self.package.pk,
            'platform': [self.platform.pk],
            'site': [self.site.pk],
        })
        self.assertFalse(form.is_valid())

    def test_multiple_values_in_one_scope_field_is_valid(self):
        form = PackageAssignmentBulkAssignForm(data={
            'package': self.package.pk,
            'platform': [self.platform.pk, self.platform2.pk],
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['scope_field'], 'platform')


class PackageAssignmentBulkAssignViewTest(ComplianceTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.package = CompliancePackage.objects.create(
            name='Package1', slug='package1', status=CompliancePackageStatusChoices.ACTIVE,
        )
        cls.platform2 = Platform.objects.create(name='Platform2', slug='platform2')

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(username='tester', password='pw')
        self.client.force_login(self.user)

    def test_post_creates_one_assignment_per_selected_platform(self):
        response = self.client.post(reverse('plugins:netbox_compliance:packageassignment_bulk_assign'), data={
            'package': self.package.pk,
            'platform': [self.platform.pk, self.platform2.pk],
            'description': 'bulk test',
        })

        self.assertEqual(response.status_code, 302)
        assignments = PackageAssignment.objects.filter(package=self.package)
        self.assertEqual(assignments.count(), 2)
        self.assertEqual(set(assignments.values_list('platform_id', flat=True)), {self.platform.pk, self.platform2.pk})
        self.assertTrue(all(a.description == 'bulk test' for a in assignments))

    def test_post_skips_already_existing_assignment(self):
        PackageAssignment.objects.create(package=self.package, platform=self.platform)

        response = self.client.post(reverse('plugins:netbox_compliance:packageassignment_bulk_assign'), data={
            'package': self.package.pk,
            'platform': [self.platform.pk, self.platform2.pk],
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(PackageAssignment.objects.filter(package=self.package).count(), 2)

    def test_invalid_form_rerenders_with_errors(self):
        response = self.client.post(reverse('plugins:netbox_compliance:packageassignment_bulk_assign'), data={
            'package': self.package.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PackageAssignment.objects.filter(package=self.package).exists())
