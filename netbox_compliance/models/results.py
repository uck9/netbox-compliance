from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

from ..choices import ComplianceResultStatusChoices
from .measures import ComplianceMeasure

__all__ = ('ComplianceResult', 'ComplianceResultHistory')


class ComplianceResult(NetBoxModel):
    """
    The current, latest-known result for one (device, measure) pair.
    Exactly one row per (device, measure) -- a repeat post for the same pair
    (bulk ingest, the software-version signal, a manual admin correction)
    updates this row in place rather than adding another one. Every write
    is mirrored into ComplianceResultHistory (see that model, and the
    post_save signal in __init__.py) so history is never lost even though
    this table itself only ever holds "the current answer."
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
    value = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('value'),
        help_text=_('Observed value as posted by the script: "true"/"false", a percentage, or an enum key'),
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('timestamp'),
        help_text=_('When this result was last (re)posted'),
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
        constraints = (
            models.UniqueConstraint(
                fields=('device', 'measure'),
                name='%(app_label)s_%(class)s_unique_device_measure',
                violation_error_message=_('A result already exists for this device and measure -- update it instead.'),
            ),
        )
        verbose_name = _('compliance result')
        verbose_name_plural = _('compliance results')

    def __str__(self):
        return f'{self.device}: {self.measure}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:complianceresult', args=[self.pk])

    def get_status_color(self):
        return ComplianceResultStatusChoices.colors.get(self.status)


class ComplianceResultHistory(NetBoxModel):
    """
    Immutable log of every observation ever recorded for a (device, measure)
    pair -- one row per ComplianceResult write, appended automatically by a
    post_save signal (see __init__.py's register_result_history_logging),
    never updated or collapsed. This is where "what did this measure look
    like over time" questions get answered; ComplianceResult itself only
    ever holds the current answer. Deliberately not derived from NetBox's
    built-in changelog (ObjectChange) -- that's a generic before/after diff
    blob subject to CHANGELOG_RETENTION (default 90 days, shared across the
    whole NetBox install), not a good fit for compliance-specific queries
    like "every FAIL for this measure in the last 90 days" and not
    something we control the retention of independently. See
    prune_compliance_results for this table's own, purpose-built retention.

    device/measure are SET_NULL (not CASCADE, unlike ComplianceResult) with
    the name/slug denormalized alongside -- same "immune to later changes,
    survives the source object being deleted" design as ComplianceSnapshot.
    """
    device = models.ForeignKey(
        to='dcim.Device',
        on_delete=models.SET_NULL,
        related_name='compliance_result_history',
        null=True,
        blank=True,
        verbose_name=_('device'),
    )
    device_name = models.CharField(
        max_length=100,
        verbose_name=_('device name'),
        help_text=_('Denormalised for posterity'),
    )
    measure = models.ForeignKey(
        to=ComplianceMeasure,
        on_delete=models.SET_NULL,
        related_name='result_history',
        null=True,
        blank=True,
        verbose_name=_('measure'),
    )
    measure_slug = models.CharField(
        max_length=100,
        verbose_name=_('measure slug'),
        help_text=_('Denormalised for posterity'),
    )
    status = models.CharField(
        max_length=30,
        choices=ComplianceResultStatusChoices,
        verbose_name=_('status'),
    )
    value = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('value'),
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('timestamp'),
        help_text=_('When this observation was recorded'),
    )
    source = models.CharField(
        max_length=100,
        verbose_name=_('source'),
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('details'),
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = (
            models.Index(fields=('device', 'measure', '-timestamp')),
        )
        verbose_name = _('compliance result history entry')
        verbose_name_plural = _('compliance result history')

    def __str__(self):
        return f'{self.device_name}: {self.measure_slug} @ {self.timestamp:%Y-%m-%d %H:%M}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:complianceresulthistory', args=[self.pk])

    def get_status_color(self):
        return ComplianceResultStatusChoices.colors.get(self.status)
