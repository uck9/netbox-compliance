from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

from ..choices import ComplianceResultStatusChoices
from .measures import ComplianceMeasure

__all__ = ('ComplianceResult',)


class ComplianceResult(NetBoxModel):
    """
    A single result, posted by an external analysis script, for one
    (device, measure) pair at a point in time.
    """
    device = models.ForeignKey(
        to='dcim.Device',
        on_delete=models.CASCADE,
        related_name='compliance_results',
        verbose_name=_('device'),
    )
    measure = models.ForeignKey(
        to=ComplianceMeasure,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name=_('measure'),
    )
    status = models.CharField(
        max_length=30,
        choices=ComplianceResultStatusChoices,
        verbose_name=_('status'),
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('timestamp'),
        help_text=_('When the check ran'),
    )
    source = models.CharField(
        max_length=100,
        verbose_name=_('source'),
        help_text=_('Which script/system produced this result'),
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('details'),
        help_text=_('Evidence: expected vs actual, raw output snippets, etc.'),
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = (
            models.Index(fields=('device', 'measure', '-timestamp')),
        )
        verbose_name = _('compliance result')
        verbose_name_plural = _('compliance results')

    def __str__(self):
        return f'{self.device}: {self.measure} = {self.status} ({self.timestamp:%Y-%m-%d})'

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:complianceresult', args=[self.pk])

    def get_status_color(self):
        return ComplianceResultStatusChoices.colors.get(self.status)
