from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

__all__ = ('ComplianceSnapshot', 'ComplianceSnapshotMeasureResult')


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
    site = models.ForeignKey(
        to='dcim.Site',
        on_delete=models.SET_NULL,
        related_name='compliance_snapshots',
        null=True,
        blank=True,
        verbose_name=_('site'),
        help_text=_("The device's site as of this period, not its current one -- lets "
                     'trend reporting group by site historically even after a device moves.'),
    )
    site_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('site name'),
        help_text=_('Denormalised for posterity'),
    )
    role = models.ForeignKey(
        to='dcim.DeviceRole',
        on_delete=models.SET_NULL,
        related_name='compliance_snapshots',
        null=True,
        blank=True,
        verbose_name=_('role'),
        help_text=_("The device's role as of this period, not its current one -- same "
                     'rationale as `site`.'),
    )
    role_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('role name'),
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


class ComplianceSnapshotMeasureResult(models.Model):
    """
    One row per effective measure captured in a ComplianceSnapshot's frozen
    `data` -- exists purely so per-measure pass/fail can be filtered and
    aggregated across periods/sites/roles (see
    services.measure_adherence_matrix) without parsing every snapshot's JSON
    blob to answer "is adherence to measure X improving". Unlike every other
    model in this app, this is a plain (non-NetBoxModel) side table: rows
    have no standalone meaning outside the aggregate, so there's no
    tags/custom-fields/changelog/journal and no list or detail view --
    ComplianceSnapshot.data remains the single readable source of truth for
    "what did this device look like", this table is just an index over it.
    Regenerated whenever generate_snapshots_for_period() replaces a period's
    snapshots; cascades with its parent snapshot.
    """
    snapshot = models.ForeignKey(
        to='netbox_compliance.ComplianceSnapshot',
        on_delete=models.CASCADE,
        related_name='measure_results',
    )
    measure = models.CharField(max_length=100, db_index=True)
    measure_name = models.CharField(max_length=200)
    package = models.CharField(
        max_length=100, blank=True,
        help_text=_('Blank for a directly-assigned measure'),
    )
    package_name = models.CharField(max_length=200, blank=True)
    severity = models.CharField(max_length=30)
    status = models.CharField(max_length=30)
    required = models.BooleanField(default=True)
    weight = models.PositiveIntegerField(default=1)
    credit = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        indexes = (
            models.Index(fields=('measure', 'status')),
        )

    def __str__(self):
        return f'{self.snapshot_id}:{self.measure}'
