from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

from .measures import ComplianceMeasure

__all__ = ('ComplianceExemption',)

SCOPE_FIELDS = ('device', 'site', 'site_group', 'tag')


class ComplianceExemption(NetBoxModel):
    """
    Removes a measure from a device's effective set, with an audit trail.
    Exactly one of device/site/site_group/tag must be set.
    """
    measure = models.ForeignKey(
        to=ComplianceMeasure,
        on_delete=models.CASCADE,
        related_name='exemptions',
        verbose_name=_('measure'),
    )
    device = models.ForeignKey(
        to='dcim.Device',
        on_delete=models.CASCADE,
        related_name='compliance_exemptions',
        null=True,
        blank=True,
        verbose_name=_('device'),
    )
    site = models.ForeignKey(
        to='dcim.Site',
        on_delete=models.CASCADE,
        related_name='compliance_exemptions',
        null=True,
        blank=True,
        verbose_name=_('site'),
    )
    site_group = models.ForeignKey(
        to='dcim.SiteGroup',
        on_delete=models.CASCADE,
        related_name='compliance_exemptions',
        null=True,
        blank=True,
        verbose_name=_('site group'),
    )
    tag = models.ForeignKey(
        to='extras.Tag',
        on_delete=models.CASCADE,
        related_name='compliance_exemptions',
        null=True,
        blank=True,
        verbose_name=_('tag'),
    )
    justification = models.TextField(
        verbose_name=_('justification'),
    )
    approved_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('approved by'),
    )
    valid_from = models.DateField(
        default=date.today,
        verbose_name=_('valid from'),
    )
    valid_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('valid until'),
        help_text=_('Null = indefinite. Expired exemptions stop applying automatically.'),
    )

    class Meta:
        ordering = ['-valid_from']
        verbose_name = _('compliance exemption')
        verbose_name_plural = _('compliance exemptions')

    def __str__(self):
        return f'{self.measure} exemption ({self.scope})'

    def get_absolute_url(self):
        return reverse('plugins:netbox_compliance:complianceexemption', args=[self.pk])

    @property
    def scope(self):
        for field in SCOPE_FIELDS:
            if value := getattr(self, field):
                return value
        return None

    @property
    def is_active(self):
        today = date.today()
        if self.valid_from > today:
            return False
        if self.valid_until and self.valid_until < today:
            return False
        return True

    def clean(self):
        super().clean()
        set_count = sum(bool(getattr(self, field)) for field in SCOPE_FIELDS)
        if set_count == 0:
            raise ValidationError(
                _('Exactly one of device, site, site group, or tag must be set.')
            )
        if set_count > 1:
            raise ValidationError(
                _('Only one of device, site, site group, or tag may be set.')
            )
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError(
                {'valid_until': _('Valid until date must be on or after the valid from date.')}
            )
