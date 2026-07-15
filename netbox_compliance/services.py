"""
Core compliance resolution logic: effective-measure resolution, staleness,
and scoring. This is the single source of truth used by the device
compliance tab, the REST API convenience endpoints, and monthly snapshot
generation -- keep all three in sync by only changing scoring/resolution
logic here.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from .choices import (
    ComplianceMeasureStatusChoices,
    CompliancePackageStatusChoices,
    EffectiveStatusChoices,
)
from .models import (
    ComplianceExemption,
    ComplianceMeasure,
    ComplianceResult,
    MeasureAssignment,
    PackageAssignment,
    PackageMeasure,
)

ZERO_SCORE_GUARD = Decimal('100.00')


@dataclass
class EffectiveMeasure:
    measure: ComplianceMeasure
    weight: int
    required: bool
    display_order: int
    source_packages: list = field(default_factory=list)
    status: str = EffectiveStatusChoices.PENDING
    result: ComplianceResult = None
    stale: bool = False


def _matching_package_assignments(device):
    """
    PackageAssignment rows whose scope matches this device, restricted to
    active packages. Scope fields are only OR'd in when the device actually
    has a value for that dimension, since comparing a nullable scope column
    to None/NULL would otherwise incorrectly match assignments scoped by a
    *different* dimension.
    """
    filters = Q(device=device)
    if device.role_id:
        filters |= Q(device_role=device.role_id)
    if device.site_id:
        filters |= Q(site=device.site_id)
        if device.site.group_id:
            filters |= Q(site_group=device.site.group_id)
    if device.platform_id:
        filters |= Q(platform=device.platform_id)
    tag_ids = list(device.tags.values_list('id', flat=True))
    if tag_ids:
        filters |= Q(tag__in=tag_ids)

    return (
        PackageAssignment.objects
        .filter(filters, package__status=CompliancePackageStatusChoices.ACTIVE)
        .select_related('package')
        .distinct()
    )


def _matching_exemptions(device, today=None):
    """
    ComplianceExemption rows whose scope matches this device and which are
    currently within their valid date range. Same None-safety concern as
    `_matching_package_assignments` applies here.
    """
    today = today or date.today()
    filters = Q(device=device)
    if device.site_id:
        filters |= Q(site=device.site_id)
        if device.site.group_id:
            filters |= Q(site_group=device.site.group_id)
    tag_ids = list(device.tags.values_list('id', flat=True))
    if tag_ids:
        filters |= Q(tag__in=tag_ids)

    return (
        ComplianceExemption.objects
        .filter(filters, valid_from__lte=today)
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))
        .select_related('measure')
    )


def _latest_results_for(device, measure_ids):
    """Most recent ComplianceResult per measure, for this device."""
    if not measure_ids:
        return {}
    latest = {}
    results = (
        ComplianceResult.objects
        .filter(device=device, measure_id__in=measure_ids)
        .order_by('measure_id', '-timestamp')
    )
    for result in results:
        latest.setdefault(result.measure_id, result)
    return latest


def _apply_status(row, result, now):
    if result is None:
        row.status = EffectiveStatusChoices.PENDING
        row.result = None
        row.stale = False
        return
    max_age = timedelta(days=row.measure.max_result_age_days)
    row.result = result
    row.stale = (now - result.timestamp) > max_age
    row.status = EffectiveStatusChoices.STALE if row.stale else result.status


def get_effective_measures(device):
    """
    Resolve a device's effective measure set:

        effective = (package_measures U direct_measures) - exempted measures

    Returns a dict:
        {
            'packages': {CompliancePackage: [EffectiveMeasure, ...]},
            'direct': [EffectiveMeasure, ...],
            'exemptions_applied': [ComplianceExemption, ...],
        }

    Exempted measures are removed from 'packages'/'direct' (and therefore
    from scoring) but any exemption that actually removed a would-be
    effective measure is reported in 'exemptions_applied' for audit/display
    purposes.
    """
    exemptions = list(_matching_exemptions(device))
    exempted_measure_ids = {e.measure_id for e in exemptions}

    assignments = list(_matching_package_assignments(device))
    package_measure_qs = list(
        PackageMeasure.objects
        .filter(package_id__in=[a.package_id for a in assignments])
        .filter(measure__status=ComplianceMeasureStatusChoices.ACTIVE)
        .select_related('package', 'measure')
        .order_by('display_order', 'measure__name')
    )

    packages = {}
    seen_package_measures = set()
    would_be_measure_ids = set()
    for pm in package_measure_qs:
        key = (pm.package_id, pm.measure_id)
        if key in seen_package_measures:
            continue
        seen_package_measures.add(key)
        would_be_measure_ids.add(pm.measure_id)
        if pm.measure_id in exempted_measure_ids:
            continue
        packages.setdefault(pm.package, []).append(EffectiveMeasure(
            measure=pm.measure,
            weight=pm.weight,
            required=pm.required,
            display_order=pm.display_order,
            source_packages=[pm.package],
        ))

    direct_qs = list(
        MeasureAssignment.objects
        .filter(device=device)
        .filter(measure__status=ComplianceMeasureStatusChoices.ACTIVE)
        .select_related('measure')
        .order_by('measure__name')
    )
    direct = []
    for ma in direct_qs:
        would_be_measure_ids.add(ma.measure_id)
        if ma.measure_id in exempted_measure_ids:
            continue
        direct.append(EffectiveMeasure(
            measure=ma.measure,
            weight=ma.weight,
            required=True,
            display_order=0,
            source_packages=[],
        ))

    exemptions_applied = [e for e in exemptions if e.measure_id in would_be_measure_ids]

    all_measure_ids = {row.measure.pk for rows in packages.values() for row in rows}
    all_measure_ids |= {row.measure.pk for row in direct}
    latest_results = _latest_results_for(device, all_measure_ids)
    now = timezone.now()
    for rows in list(packages.values()) + [direct]:
        for row in rows:
            _apply_status(row, latest_results.get(row.measure.pk), now)

    return {
        'packages': packages,
        'direct': direct,
        'exemptions_applied': exemptions_applied,
    }


def score_group(rows):
    """
    score = 100 * sum(weight for required, non-N/A rows that pass)
                / sum(weight for required, non-N/A rows)

    Returns (score, total_weight). An empty/zero-weight scoreable set
    (all N/A, or informational-only) is vacuously 100% compliant and
    contributes zero weight to any enclosing weighted average.
    """
    scored = [r for r in rows if r.required and r.status != EffectiveStatusChoices.NOT_APPLICABLE]
    total_weight = sum(r.weight for r in scored)
    if total_weight == 0:
        return ZERO_SCORE_GUARD, 0
    passed_weight = sum(r.weight for r in scored if r.status == EffectiveStatusChoices.PASS)
    score = (Decimal(100) * passed_weight / total_weight).quantize(Decimal('0.01'))
    return score, total_weight


def score_device(device, effective=None):
    """
    Overall device score = weighted mean of package scores (each weighted
    by its total required-measure weight) combined with the direct-measures
    set treated as one pseudo-package. Compliant iff overall_score == 100,
    which is equivalent to "every effective required measure is pass or
    not_applicable" given not_applicable is excluded from scoring.
    """
    effective = effective if effective is not None else get_effective_measures(device)

    package_scores = {}
    weighted_groups = []
    for package, rows in effective['packages'].items():
        score, weight = score_group(rows)
        package_scores[package] = score
        weighted_groups.append((score, weight))

    direct_score, direct_weight = score_group(effective['direct'])
    weighted_groups.append((direct_score, direct_weight))

    total_weight = sum(w for _, w in weighted_groups)
    if total_weight == 0:
        overall_score = ZERO_SCORE_GUARD
    else:
        overall_score = (
            sum(s * w for s, w in weighted_groups) / total_weight
        ).quantize(Decimal('0.01'))

    return {
        'overall_score': overall_score,
        'compliant': overall_score == Decimal('100.00'),
        'package_scores': package_scores,
        'direct_score': direct_score,
        'effective': effective,
    }


def _measure_row_dict(row):
    return {
        'measure': row.measure.slug,
        'measure_name': row.measure.name,
        'severity': row.measure.severity,
        'weight': row.weight,
        'display_order': row.display_order,
        'required': row.required,
        'status': row.status,
        'result_timestamp': row.result.timestamp.isoformat() if row.result else None,
        'source': row.result.source if row.result else None,
        'stale': row.stale,
    }


def build_snapshot_data(device):
    """
    Build the frozen JSON payload stored on ComplianceSnapshot.data, plus
    the overall_score/compliant values that accompany it, per the schema
    documented in the plugin spec.
    """
    scoring = score_device(device)
    effective = scoring['effective']

    packages_data = []
    for package in sorted(effective['packages'], key=lambda p: p.name):
        rows = sorted(effective['packages'][package], key=lambda r: (r.display_order, r.measure.name))
        packages_data.append({
            'package': package.slug,
            'package_name': package.name,
            'score': float(scoring['package_scores'][package]),
            'measures': [_measure_row_dict(row) for row in rows],
        })

    direct_data = [
        _measure_row_dict(row)
        for row in sorted(effective['direct'], key=lambda r: r.measure.name)
    ]

    exemptions_data = []
    for exemption in effective['exemptions_applied']:
        exemptions_data.append({
            'measure': exemption.measure.slug,
            'scope': _exemption_scope_label(exemption),
            'justification': exemption.justification,
        })

    data = {
        'packages': packages_data,
        'direct_measures': direct_data,
        'exemptions_applied': exemptions_data,
    }
    return data, scoring['overall_score'], scoring['compliant']


def _exemption_scope_label(exemption):
    for field_name in ('device', 'site', 'site_group', 'tag'):
        value = getattr(exemption, field_name)
        if value:
            return f'{field_name}:{value}'
    return ''


def devices_with_effective_measures():
    """
    Every dcim.Device with at least one PackageAssignment or
    MeasureAssignment that could resolve to an effective measure -- used to
    scope which devices get a monthly snapshot.
    """
    from dcim.models import Device

    package_assignments = PackageAssignment.objects.filter(package__status=CompliancePackageStatusChoices.ACTIVE)
    device_ids = set()

    for assignment in package_assignments.select_related('site__group'):
        qs = Device.objects.all()
        if assignment.device_id:
            qs = qs.filter(pk=assignment.device_id)
        elif assignment.device_role_id:
            qs = qs.filter(role_id=assignment.device_role_id)
        elif assignment.site_id:
            qs = qs.filter(site_id=assignment.site_id)
        elif assignment.site_group_id:
            qs = qs.filter(site__group_id=assignment.site_group_id)
        elif assignment.platform_id:
            qs = qs.filter(platform_id=assignment.platform_id)
        elif assignment.tag_id:
            qs = qs.filter(tags=assignment.tag_id)
        else:
            continue
        device_ids.update(qs.values_list('pk', flat=True))

    device_ids.update(MeasureAssignment.objects.values_list('device_id', flat=True))

    return Device.objects.filter(pk__in=device_ids)


def generate_snapshots_for_period(period):
    """
    Idempotent: replaces any existing snapshots for this period. Snapshots
    every device with at least one effective measure (after exemptions).
    Returns the number of snapshots written. Shared by the monthly system
    job and the `generate_compliance_snapshots` management command.
    """
    from .models import ComplianceSnapshot

    ComplianceSnapshot.objects.filter(period=period).delete()

    count = 0
    for device in devices_with_effective_measures():
        data, overall_score, compliant = build_snapshot_data(device)
        if not data['packages'] and not data['direct_measures']:
            continue
        ComplianceSnapshot.objects.create(
            device=device,
            device_name=device.name,
            period=period,
            overall_score=overall_score,
            compliant=compliant,
            data=data,
        )
        count += 1
    return count
