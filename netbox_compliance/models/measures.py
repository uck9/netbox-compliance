from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel

from ..choices import (
    ComplianceMeasureCategoryChoices,
    ComplianceMeasureResultTypeChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceMeasureStatusChoices,
    CompliancePackageStatusChoices,
    VALUE_MAP_COLORS,
)

__all__ = (
    'ComplianceMeasure',
    'CompliancePackage',
    'PackageMeasure',
)


def _validate_value_map(value_map):
    """
    Validate a ComplianceMeasure.value_map dict of the shape
    {key: {label, color, credit}}. Returns a list of human-readable error
    strings; an empty list means the value_map is valid. Shared by
    ComplianceMeasure.clean() and the API serializer so the rule lives in
    exactly one place.
    """
    errors = []
    if not isinstance(value_map, dict):
        return ['value_map must be an object mapping keys to state definitions.']
    for key, entry in value_map.items():
        if not isinstance(entry, dict):
            errors.append(f'{key!r}: entry must be an object.')
            continue
        if not isinstance(entry.get('label'), str) or not entry.get('label'):
            errors.append(f'{key!r}: missing or invalid "label".')
        if entry.get('color') not in VALUE_MAP_COLORS:
            errors.append(f'{key!r}: "color" must be one of {sorted(VALUE_MAP_COLORS)}.')
        credit = entry.get('credit')
        if isinstance(credit, bool) or not isinstance(credit, (int, float)) or not (0 <= credit <= 100):
            errors.append(f'{key!r}: "credit" must be a number between 0 and 100.')
    return errors


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
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('title'),
        help_text=_('Short human-readable label, if different from name (e.g. name/slug are a '
                    'code like "AAA-004", title is a descriptive label for display)'),
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
    result_type = models.CharField(
        max_length=20,
        choices=ComplianceMeasureResultTypeChoices,
        default=ComplianceMeasureResultTypeChoices.BOOLEAN,
        verbose_name=_('result type'),
    )
    pass_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_('pass threshold'),
        help_text=_('Percentage type only: value >= threshold counts as pass'),
    )
    value_map = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('value map'),
        help_text=_('Enum type only: {"key": {"label": ..., "color": "green|orange|red|grey", "credit": 0-100}}'),
    )
    show_on_device_panel = models.BooleanField(
        default=False,
        verbose_name=_('show on device panel'),
        help_text=_('Pin this measure to the main device-page compliance panel'),
    )
    panel_display_order = models.PositiveSmallIntegerField(
        default=100,
        verbose_name=_('panel display order'),
        help_text=_('Sort order within the device panel\'s pinned-measures section'),
    )
    display_template = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('display template'),
        help_text=_('Optional Django-template snippet rendered against {value, label, details}, '
                     'e.g. "{{ details.running }} (target {{ details.target }})"'),
    )
    required_detail_keys = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('required detail keys'),
        help_text=_('Keys that must be present in a posted result\'s details, e.g. ["running", "target"]'),
    )

    clone_fields = (
        'category', 'severity', 'max_result_age_days', 'status', 'result_type', 'pass_threshold',
        'value_map', 'show_on_device_panel', 'panel_display_order', 'display_template', 'required_detail_keys',
    )

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

    def get_result_type_color(self):
        return ComplianceMeasureResultTypeChoices.colors.get(self.result_type)

    def clean(self):
        super().clean()
        if self.result_type == ComplianceMeasureResultTypeChoices.ENUM:
            if not self.value_map:
                raise ValidationError({'value_map': _('Enum measures require a non-empty value_map.')})
            errors = _validate_value_map(self.value_map)
            if errors:
                raise ValidationError({'value_map': errors})
            if self.pass_threshold is not None:
                raise ValidationError({'pass_threshold': _('Enum measures must not set pass_threshold.')})
        elif self.result_type == ComplianceMeasureResultTypeChoices.PERCENTAGE:
            if self.pass_threshold is None:
                raise ValidationError({'pass_threshold': _('Percentage measures require pass_threshold.')})
            if self.value_map:
                raise ValidationError({'value_map': _('Percentage measures must not set value_map.')})
        else:  # boolean
            if self.pass_threshold is not None:
                raise ValidationError({'pass_threshold': _('Boolean measures must not set pass_threshold.')})
            if self.value_map:
                raise ValidationError({'value_map': _('Boolean measures must not set value_map.')})


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
    show_on_device_panel = models.BooleanField(
        default=False,
        verbose_name=_('show on device panel'),
        help_text=_('Pin this package to the main device-page compliance panel'),
    )
    panel_display_order = models.PositiveSmallIntegerField(
        default=100,
        verbose_name=_('panel display order'),
        help_text=_('Sort order within the device panel\'s package-rows section'),
    )
    amber_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('80.00'),
        verbose_name=_('amber threshold'),
        help_text=_('Package score at/above which a non-green package shows amber rather than red'),
    )
    red_on_critical_fail = models.BooleanField(
        default=True,
        verbose_name=_('red on critical fail'),
        help_text=_('Any failing critical/high-severity measure forces red regardless of score'),
    )

    clone_fields = ('status', 'show_on_device_panel', 'panel_display_order', 'amber_threshold', 'red_on_critical_fail')

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
