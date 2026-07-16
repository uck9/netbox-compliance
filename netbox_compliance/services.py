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

from django.core.cache import cache
from django.db.models import Q
from django.template import Context, Template
from django.utils import timezone

from .choices import (
    ComplianceMeasureResultTypeChoices,
    ComplianceMeasureSeverityChoices,
    ComplianceMeasureStatusChoices,
    CompliancePackageStatusChoices,
    ComplianceResultStatusChoices,
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

PANEL_CACHE_TTL = 300
PANEL_CACHE_KEY = 'compliance:panel:{device_id}'

_EFFECTIVE_STATUS_LABELS = {value: label for value, label, *_rest in EffectiveStatusChoices.CHOICES}


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
    value: str = None
    display_label: str = ''
    display_color: str = 'grey'
    credit: int = 0


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
        row.value = None
        _apply_display(row)
        return
    max_age = timedelta(days=row.measure.max_result_age_days)
    row.result = result
    row.stale = (now - result.timestamp) > max_age
    row.value = result.value
    row.status = EffectiveStatusChoices.STALE if row.stale else result.status
    _apply_display(row)


def enum_credit_status(entry):
    """
    pass/fail derivation shared by bulk ingestion and the custom-field import
    command: an enum value_map entry counts as a pass only at full credit.
    """
    return (
        ComplianceResultStatusChoices.PASS if int(entry.get('credit', 0)) == 100
        else ComplianceResultStatusChoices.FAIL
    )


def _apply_display(row):
    """
    Resolve display_label/display_color/credit from row.measure.result_type,
    row.value, and row.status. Pure function of already-set row fields -- no
    DB access. Boolean-type rows derive credit from `status` alone (not
    `value`), so direct-model-creation fixtures that never set `value` (as
    the pre-existing test suite does) keep scoring correctly.
    """
    measure = row.measure

    if row.status in (EffectiveStatusChoices.PENDING, EffectiveStatusChoices.STALE):
        row.display_label = _EFFECTIVE_STATUS_LABELS.get(row.status, row.status)
        row.display_color = EffectiveStatusChoices.colors.get(row.status, 'grey')
        row.credit = 0
        return
    if row.status == EffectiveStatusChoices.ERROR:
        row.display_label = _EFFECTIVE_STATUS_LABELS.get(row.status, 'Error')
        row.display_color = EffectiveStatusChoices.colors.get(row.status, 'dark-red')
        row.credit = 0
        return
    if row.status == EffectiveStatusChoices.NOT_APPLICABLE:
        row.display_label = _EFFECTIVE_STATUS_LABELS.get(row.status, 'Not Applicable')
        row.display_color = 'grey'
        row.credit = 0
        return

    if measure.result_type == ComplianceMeasureResultTypeChoices.PERCENTAGE:
        try:
            pct = Decimal(row.value) if row.value is not None else Decimal(0)
        except Exception:
            pct = Decimal(0)
        pct = max(Decimal(0), min(Decimal(100), pct))
        row.credit = int(pct)
        row.display_label = f'{pct}%'
        threshold = measure.pass_threshold if measure.pass_threshold is not None else Decimal(100)
        if pct >= threshold:
            row.display_color = 'green'
        elif pct >= (threshold - 20):
            row.display_color = 'orange'
        else:
            row.display_color = 'red'
    elif measure.result_type == ComplianceMeasureResultTypeChoices.ENUM:
        entry = measure.value_map.get(row.value, {})
        row.display_label = entry.get('label', row.value or '')
        row.display_color = entry.get('color', 'grey')
        row.credit = int(entry.get('credit', 0))
    else:  # boolean
        is_pass = row.status == EffectiveStatusChoices.PASS
        row.display_label = 'Pass' if is_pass else 'Fail'
        row.display_color = 'green' if is_pass else 'red'
        row.credit = 100 if is_pass else 0


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
    score = 100 * sum(weight * credit for required, non-N/A rows)
                / sum(weight * 100 for required, non-N/A rows)

    Every row resolves to a credit of 0-100 (see _apply_display); this is
    numerically identical to the old binary pass-count formula whenever
    every row's credit is 0 or 100 (i.e. boolean-only packages).

    Returns (score, total_weight). An empty/zero-weight scoreable set
    (all N/A, or informational-only) is vacuously 100% compliant and
    contributes zero weight to any enclosing weighted average.
    """
    scored = [r for r in rows if r.required and r.status != EffectiveStatusChoices.NOT_APPLICABLE]
    total_weight = sum(r.weight for r in scored)
    if total_weight == 0:
        return ZERO_SCORE_GUARD, 0
    numerator = sum(Decimal(r.weight) * Decimal(r.credit) for r in scored)
    denominator = Decimal(total_weight) * Decimal(100)
    score = (Decimal(100) * numerator / denominator).quantize(Decimal('0.01'))
    return score, total_weight


def score_device(device, effective=None):
    """
    Overall device score = weighted mean of package scores (each weighted
    by its total required-measure weight) combined with the direct-measures
    set treated as one pseudo-package. Compliant iff overall_score == 100,
    which (a weighted average of per-row credits, each <=100, only reaches
    100 if every included row's credit is 100) is equivalent to "every
    effective required measure is pass, with full credit, or not_applicable"
    given not_applicable is excluded from scoring.
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


def package_traffic_light(device, package, rows=None):
    """
    Single traffic-light resolution used by the device panel, tab section
    header, and reports (spec B2). Returns one of 'grey'/'green'/'red'/'amber'.

    `rows` may be passed pre-resolved (list[EffectiveMeasure]) to avoid
    re-querying when the caller already has get_effective_measures() output;
    otherwise resolved via get_effective_measures(device).
    """
    if rows is None:
        rows = get_effective_measures(device)['packages'].get(package, [])

    required_rows = [r for r in rows if r.required]
    if not required_rows:
        return 'grey'
    if all(r.status in (EffectiveStatusChoices.PENDING, EffectiveStatusChoices.STALE) for r in required_rows):
        return 'grey'
    if all(r.status in (EffectiveStatusChoices.PASS, EffectiveStatusChoices.NOT_APPLICABLE) for r in required_rows):
        return 'green'

    critical_fail = any(
        r.status == EffectiveStatusChoices.FAIL
        and r.measure.severity in (ComplianceMeasureSeverityChoices.CRITICAL, ComplianceMeasureSeverityChoices.HIGH)
        for r in required_rows
    )
    if package.red_on_critical_fail and critical_fail:
        return 'red'

    score, _ = score_group(rows)
    return 'red' if score < package.amber_threshold else 'amber'


def render_display_template(row):
    """
    Render measure.display_template against {value, label, details}, falling
    back to display_label when the template is blank or fails to render.
    Used by the panel, the compliance tab, and the device-status API's
    display_text field.
    """
    if not row.measure.display_template:
        return row.display_label
    context = Context({
        'value': row.value,
        'label': row.display_label,
        'details': row.result.details if row.result else {},
    })
    try:
        return Template(row.measure.display_template).render(context)
    except Exception:
        return row.display_label


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
        'result_type': row.measure.result_type,
        'value': row.value,
        'display_label': row.display_label,
        'display_color': row.display_color,
        'credit': row.credit,
        'display_text': render_display_template(row),
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
            'traffic_light': package_traffic_light(device, package, rows=rows),
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


def get_device_panel_data(device):
    """
    Cached assembly of the device-page compliance panel payload (spec B3/B4):
    pinned package rows (show_on_device_panel=True packages, ordered by
    their own panel_display_order) and pinned measure rows
    (show_on_device_panel=True measures across packages+direct, ordered by
    their own panel_display_order) -- the two sections sort independently of
    each other. A pinned measure is shown even if its source package is also
    pinned (deliberate duplication: the package row is the rollup, the
    measure row is the always-visible live value).
    """
    key = PANEL_CACHE_KEY.format(device_id=device.pk)
    cached = cache.get(key)
    if cached is not None:
        return cached

    effective = get_effective_measures(device)
    scoring = score_device(device, effective=effective)

    package_rows = []
    for package, rows in effective['packages'].items():
        if not package.show_on_device_panel:
            continue
        package_rows.append({
            'package': package,
            'score': scoring['package_scores'][package],
            'traffic_light': package_traffic_light(device, package, rows=rows),
            'oldest_result_age': min((r.result.timestamp for r in rows if r.result), default=None),
        })
    package_rows.sort(key=lambda p: (p['package'].panel_display_order, p['package'].name))

    all_rows = [r for rows in effective['packages'].values() for r in rows] + effective['direct']
    measure_rows = [
        {
            'row': row,
            'display_text': render_display_template(row),
            # Panel-specific override (spec B3): stale/pending rows show a
            # grey badge here even though the shared display_color (used by
            # the tab/API/snapshots) distinguishes stale (orange) from
            # pending (grey) -- the last-known display_text is still shown.
            'display_color': 'grey' if (row.stale or row.status == EffectiveStatusChoices.PENDING) else row.display_color,
        }
        for row in all_rows if row.measure.show_on_device_panel
    ]
    measure_rows.sort(key=lambda m: (m['row'].measure.panel_display_order, m['row'].measure.name))

    payload = {'packages': package_rows, 'measures': measure_rows}
    cache.set(key, payload, PANEL_CACHE_TTL)
    return payload


def invalidate_device_panel_cache(device_id):
    cache.delete(PANEL_CACHE_KEY.format(device_id=device_id))
