from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

from .measures import CompliancePackage

__all__ = ('CompliancePackageReport',)


class CompliancePackageReport(NetBoxModel):
    """
    The current, latest-known raw evaluation report for one (device,
    package) pair -- exactly one row per pair, upserted in place on every
    run (see services.record_package_report), same "current row" posture
    as ComplianceResult. Unlike ComplianceResult there is deliberately no
    history table: storage here is bounded by (#devices x #packages)
    regardless of run frequency, since a repost always overwrites rather
    than appends, so no pruning is needed either.

    device/package are SET_NULL (not CASCADE) with the name/slug
    denormalized alongside -- same "immune to later changes, survives the
    source object being deleted" design as ComplianceSnapshot -- so a
    device or package deletion doesn't silently delete a report a user
    might still want to view. Unassigning a package from a device (a
    PackageAssignment removal, without deleting the device/package
    themselves) leaves this row completely untouched -- it's "last known
    raw dump for that package's last run," not derived from current
    assignment state.
    """
    device = models.ForeignKey(
        to='dcim.Device',
        on_delete=models.SET_NULL,
        related_name='compliance_package_reports',
        null=True,
        blank=True,
        verbose_name=_('device'),
    )
    device_name = models.CharField(
        max_length=100,
        verbose_name=_('device name'),
        help_text=_('Denormalised for posterity'),
    )
    package = models.ForeignKey(
        to=CompliancePackage,
        on_delete=models.SET_NULL,
        related_name='reports',
        null=True,
        blank=True,
        verbose_name=_('package'),
    )
    package_slug = models.CharField(
        max_length=100,
        verbose_name=_('package slug'),
        help_text=_('Denormalised for posterity'),
    )
    html = models.TextField(
        verbose_name=_('HTML'),
        help_text=_('Raw self-contained report rendered by the last evaluation run'),
    )
    source = models.CharField(
        max_length=100,
        verbose_name=_('source'),
        help_text=_('Which script/system produced this report'),
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('timestamp'),
        help_text=_('When this report was last (re)generated'),
    )

    class Meta:
        ordering = ['device_name', 'package_slug']
        constraints = (
            models.UniqueConstraint(
                fields=('device', 'package'),
                name='%(app_label)s_%(class)s_unique_device_package',
                violation_error_message=_('A report already exists for this device and package -- update it instead.'),
            ),
        )
        verbose_name = _('compliance package report')
        verbose_name_plural = _('compliance package reports')

    def __str__(self):
        return f'{self.device_name}: {self.package_slug} @ {self.timestamp:%Y-%m-%d %H:%M}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:compliancepackagereport', args=[self.pk])

    def get_raw_url(self):
        return reverse('plugins:netbox_compliance:compliancepackagereport_raw', args=[self.pk])
