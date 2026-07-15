from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

from .measures import ComplianceMeasure, CompliancePackage

__all__ = (
    'PackageAssignment',
    'MeasureAssignment',
)

SCOPE_FIELDS = ('device', 'device_role', 'site', 'site_group', 'platform', 'tag')


class PackageAssignment(NetBoxModel):
    """
    Assigns a CompliancePackage to a scope. Exactly one scope field must be
    set. A device's assigned packages are the union of all PackageAssignment
    rows whose scope matches the device.
    """
    package = models.ForeignKey(
        to=CompliancePackage,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name=_('package'),
    )
    device = models.ForeignKey(
        to='dcim.Device',
        on_delete=models.CASCADE,
        related_name='compliance_package_assignments',
        null=True,
        blank=True,
        verbose_name=_('device'),
    )
    device_role = models.ForeignKey(
        to='dcim.DeviceRole',
        on_delete=models.CASCADE,
        related_name='compliance_package_assignments',
        null=True,
        blank=True,
        verbose_name=_('device role'),
    )
    site = models.ForeignKey(
        to='dcim.Site',
        on_delete=models.CASCADE,
        related_name='compliance_package_assignments',
        null=True,
        blank=True,
        verbose_name=_('site'),
    )
    site_group = models.ForeignKey(
        to='dcim.SiteGroup',
        on_delete=models.CASCADE,
        related_name='compliance_package_assignments',
        null=True,
        blank=True,
        verbose_name=_('site group'),
    )
    platform = models.ForeignKey(
        to='dcim.Platform',
        on_delete=models.CASCADE,
        related_name='compliance_package_assignments',
        null=True,
        blank=True,
        verbose_name=_('platform'),
    )
    tag = models.ForeignKey(
        to='extras.Tag',
        on_delete=models.CASCADE,
        related_name='compliance_package_assignments',
        null=True,
        blank=True,
        verbose_name=_('tag'),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('description'),
        help_text=_('Why this assignment exists'),
    )

    class Meta:
        ordering = ['package', 'id']
        verbose_name = _('package assignment')
        verbose_name_plural = _('package assignments')

    def __str__(self):
        return f'{self.package} -> {self.scope}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:packageassignment', args=[self.pk])

    @property
    def scope(self):
        for field in SCOPE_FIELDS:
            if value := getattr(self, field):
                return value
        return None

    def clean(self):
        super().clean()
        set_count = sum(bool(getattr(self, field)) for field in SCOPE_FIELDS)
        if set_count == 0:
            raise ValidationError(
                _('Exactly one of device, device role, site, site group, platform, or tag must be set.')
            )
        if set_count > 1:
            raise ValidationError(
                _('Only one of device, device role, site, site group, platform, or tag may be set.')
            )


class MeasureAssignment(NetBoxModel):
    """
    A direct, one-off measure assignment on a single device.
    """
    device = models.ForeignKey(
        to='dcim.Device',
        on_delete=models.CASCADE,
        related_name='compliance_measure_assignments',
        verbose_name=_('device'),
    )
    measure = models.ForeignKey(
        to=ComplianceMeasure,
        on_delete=models.CASCADE,
        related_name='direct_assignments',
        verbose_name=_('measure'),
    )
    weight = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_('weight'),
        help_text=_('Used in the direct-measures score component'),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('description'),
    )

    class Meta:
        ordering = ['device', 'measure__name']
        constraints = (
            models.UniqueConstraint(
                fields=('device', 'measure'),
                name='%(app_label)s_%(class)s_unique_device_measure',
                violation_error_message=_('This measure is already directly assigned to this device.'),
            ),
        )
        verbose_name = _('measure assignment')
        verbose_name_plural = _('measure assignments')

    def __str__(self):
        return f'{self.device}: {self.measure}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:measureassignment', args=[self.pk])
