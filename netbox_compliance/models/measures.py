from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceMeasureStatusChoices,
    CompliancePackageStatusChoices,
)

__all__ = (
    'ComplianceMeasure',
    'CompliancePackage',
    'PackageMeasure',
)


class ComplianceMeasure(NetBoxModel):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('name'),
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_('slug'),
        help_text=_('Used by external scripts when posting results'),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('description'),
        help_text=_('What the check verifies'),
    )
    category = models.CharField(
        max_length=30,
        choices=ComplianceMeasureCategoryChoices,
        verbose_name=_('category'),
    )
    severity = models.CharField(
        max_length=30,
        choices=ComplianceMeasureSeverityChoices,
        verbose_name=_('severity'),
    )
    max_result_age_days = models.PositiveIntegerField(
        default=35,
        verbose_name=_('max result age (days)'),
        help_text=_('Results older than this are treated as stale'),
    )
    status = models.CharField(
        max_length=30,
        choices=ComplianceMeasureStatusChoices,
        default=ComplianceMeasureStatusChoices.ACTIVE,
        verbose_name=_('status'),
    )
    comments = models.TextField(
        blank=True,
        verbose_name=_('comments'),
    )

    clone_fields = ('category', 'severity', 'max_result_age_days', 'status')

    class Meta:
        ordering = ['name']
        verbose_name = _('compliance measure')
        verbose_name_plural = _('compliance measures')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:compliancemeasure', args=[self.pk])

    def get_category_color(self):
        return ComplianceMeasureCategoryChoices.colors.get(self.category)

    def get_severity_color(self):
        return ComplianceMeasureSeverityChoices.colors.get(self.severity)

    def get_status_color(self):
        return ComplianceMeasureStatusChoices.colors.get(self.status)


class CompliancePackage(NetBoxModel):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('name'),
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_('slug'),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('description'),
    )
    status = models.CharField(
        max_length=30,
        choices=CompliancePackageStatusChoices,
        default=CompliancePackageStatusChoices.DRAFT,
        verbose_name=_('status'),
    )
    measures = models.ManyToManyField(
        to=ComplianceMeasure,
        through='PackageMeasure',
        related_name='packages',
        blank=True,
        verbose_name=_('measures'),
    )

    clone_fields = ('status',)

    class Meta:
        ordering = ['name']
        verbose_name = _('compliance package')
        verbose_name_plural = _('compliance packages')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:compliancepackage', args=[self.pk])

    def get_status_color(self):
        return CompliancePackageStatusChoices.colors.get(self.status)


class PackageMeasure(NetBoxModel):
    package = models.ForeignKey(
        to=CompliancePackage,
        on_delete=models.CASCADE,
        related_name='package_measures',
        verbose_name=_('package'),
    )
    measure = models.ForeignKey(
        to=ComplianceMeasure,
        on_delete=models.CASCADE,
        related_name='package_measures',
        verbose_name=_('measure'),
    )
    weight = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_('weight'),
        help_text=_('Relative weight within the package'),
    )
    required = models.BooleanField(
        default=True,
        verbose_name=_('required'),
        help_text=_('If unset, informational only -- reported but excluded from score'),
    )
    display_order = models.PositiveSmallIntegerField(
        default=100,
        verbose_name=_('display order'),
        help_text=_('Sort order for display within the package; use gaps (100, 200, 300...) to allow inserts'),
    )

    class Meta:
        ordering = ['display_order', 'measure__name']
        constraints = (
            models.UniqueConstraint(
                fields=('package', 'measure'),
                name='%(app_label)s_%(class)s_unique_package_measure',
                violation_error_message=_('This measure is already part of this package.'),
            ),
        )
        verbose_name = _('package measure')
        verbose_name_plural = _('package measures')

    def __str__(self):
        return f'{self.package}: {self.measure}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:packagemeasure', args=[self.pk])
