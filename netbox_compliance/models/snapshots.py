from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

__all__ = ('ComplianceSnapshot',)


class ComplianceSnapshot(NetBoxModel):
    """
    A monthly, point-in-time, self-contained freeze of a device's resolved
    compliance state. Immune to later changes in packages, measures,
    weights, assignments, or exemptions -- do not reconstruct history from
    live tables, read from here instead.
    """
    device = models.ForeignKey(
        to='dcim.Device',
        on_delete=models.SET_NULL,
        related_name='compliance_snapshots',
        null=True,
        blank=True,
        verbose_name=_('device'),
    )
    device_name = models.CharField(
        max_length=100,
        verbose_name=_('device name'),
        help_text=_('Denormalised for posterity'),
    )
    period = models.DateField(
        verbose_name=_('period'),
        help_text=_('First day of the month, e.g. 2026-07-01'),
    )
    overall_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_('overall score'),
        help_text=_('0-100 across all packages plus direct measures'),
    )
    compliant = models.BooleanField(
        default=False,
        verbose_name=_('compliant'),
        help_text=_('True iff overall_score == 100 (all required measures pass)'),
    )
    data = models.JSONField(
        verbose_name=_('data'),
        help_text=_('Full frozen detail: packages, direct measures, exemptions applied'),
    )

    class Meta:
        ordering = ['-period', 'device_name']
        constraints = (
            models.UniqueConstraint(
                fields=('device', 'period'),
                name='%(app_label)s_%(class)s_unique_device_period',
                violation_error_message=_('A snapshot already exists for this device and period.'),
            ),
        )
        verbose_name = _('compliance snapshot')
        verbose_name_plural = _('compliance snapshots')

    def __str__(self):
        return f'{self.device_name} ({self.period:%Y-%m})'

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:compliancesnapshot', args=[self.pk])
