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

SOFTWARE_VERSION_MEASURE_SLUG = 'software-version'
SOFTWARE_VERSION_SOURCE = 'software_version_signal'
SOFTWARE_VERSION_CF = 'software_version'
SOFTWARE_VERSION_MANAGEMENT_CF = 'software_version_management'

# The live `software-version` ComplianceMeasure's value_map keys -- these are
# the legacy nb_sw_currency_calculation script's own vocabulary (carried over
# when results were first ingested), NOT the aspirational key names in
# compliance-plugin-naming-conventions.md's "Standard: software-version"
# table (on_target/accepted/upgrade_required/unsupported/unknown_version),
# which were never actually implemented against this measure. With 1000+
# real ComplianceResult rows already using these keys, renaming them is a
# breaking change per the naming doc's own immutability rule -- so this
# module targets what's actually live, not what the doc describes.
SOFTWARE_VERSION_KEY_ON_TARGET = 'target_active_version'
SOFTWARE_VERSION_KEY_ACCEPTED = 'accepted_active_version'
SOFTWARE_VERSION_KEY_UPGRADE_REQUIRED = 'required_upgrade'
SOFTWARE_VERSION_KEY_RETIRED = 'required_upgrade_retired'

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
        ancestor_ids = device.platform.get_ancestors(include_self=True).values_list('id', flat=True)
        filters |= Q(platform__in=ancestor_ids)
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


def _software_version_policy_for_device(platform_data, device):
    """
    Resolve the effective version_policy dict for a device from its
    platform's `software_version_management` JSON (schema_version "1.0"):
    a child-platform-scoped object with a `defaults.version_policy`
    baseline, optionally overridden -- in full, not merged field-by-field --
    by a `device_type_overrides[device_type.model]` entry (most specific,
    since it pins an exact hardware model) or else a `roles[device_role.slug]`
    entry, in that precedence order.

    Parent-level platforms (`policy_scope: "parent_platform"`, e.g. plain
    "IOS XE") carry no version_policy at all -- only `eol`/`parser`/
    `vulnerabilities`, which feed separate EOL/vulnerability measures, not
    software-version. Devices are expected to be assigned a child platform.
    """
    if not isinstance(platform_data, dict):
        return None

    device_type_overrides = platform_data.get('device_type_overrides') or {}
    dt_override = device_type_overrides.get(device.device_type.model) if device.device_type_id else None
    if isinstance(dt_override, dict) and isinstance(dt_override.get('version_policy'), dict):
        return dt_override['version_policy']

    roles = platform_data.get('roles') or {}
    role_override = roles.get(device.role.slug) if device.role_id else None
    if isinstance(role_override, dict) and isinstance(role_override.get('version_policy'), dict):
        return role_override['version_policy']

    defaults = platform_data.get('defaults') or {}
    version_policy = defaults.get('version_policy')
    return version_policy if isinstance(version_policy, dict) else None


def _is_valid_version_policy(version_policy):
    if not isinstance(version_policy, dict):
        return False
    if not isinstance(version_policy.get('accepted_active_versions'), list):
        return False
    if not isinstance(version_policy.get('retired_versions'), dict):
        return False
    target = version_policy.get('target_active_versions')
    return isinstance(target, list) and len(target) > 0


def compute_software_version_result(device, measure):
    """
    Pure computation (no DB write) of the `software-version` result for a
    device: resolves `device.platform`'s `software_version_management` JSON
    (device_type is never consulted -- see `_software_version_policy_for_device`)
    and classifies `device.custom_field_data['software_version']` against it.

    Returns (status, value, details). `value` is None whenever the outcome
    isn't one of the measure's own value_map keys (not_applicable / error
    cases) -- see `evaluate_software_version`'s docstring for what each
    outcome means. Split out from `evaluate_software_version` so validation/
    audit tooling (e.g. `validate_software_version_results`) can recompute
    the expected result for a device without creating a new ComplianceResult
    every time it checks.
    """
    running_version = device.custom_field_data.get(SOFTWARE_VERSION_CF) or None

    if device.platform_id is None:
        return (
            ComplianceResultStatusChoices.NOT_APPLICABLE, None,
            {'running': running_version, 'target': None, 'note': 'Device has no platform assigned'},
        )

    platform_data = device.platform.custom_field_data.get(SOFTWARE_VERSION_MANAGEMENT_CF)
    version_policy = _software_version_policy_for_device(platform_data, device)
    if not _is_valid_version_policy(version_policy):
        return (
            ComplianceResultStatusChoices.ERROR, None,
            {
                'running': running_version, 'target': None,
                'note': f'No valid version_policy resolved from platform {device.platform.name!r}',
            },
        )

    target_versions = version_policy['target_active_versions']
    target = target_versions[0] if len(target_versions) == 1 else ', '.join(target_versions)

    if not running_version:
        return (
            ComplianceResultStatusChoices.ERROR, None,
            {'running': None, 'target': target, 'note': 'Device has no software_version reported'},
        )

    if running_version in version_policy['retired_versions']:
        value = SOFTWARE_VERSION_KEY_RETIRED
    elif running_version in version_policy['accepted_active_versions']:
        value = SOFTWARE_VERSION_KEY_ACCEPTED
    elif running_version in target_versions:
        value = SOFTWARE_VERSION_KEY_ON_TARGET
    else:
        value = SOFTWARE_VERSION_KEY_UPGRADE_REQUIRED

    entry = measure.value_map.get(value)
    if entry is None:
        return (
            ComplianceResultStatusChoices.ERROR, None,
            {'running': running_version, 'target': target, 'note': f'Measure value_map missing key {value!r}'},
        )

    return enum_credit_status(entry), value, {'running': running_version, 'target': target}


def evaluate_software_version(device):
    """
    Resolve and write the `software-version` ComplianceResult for a device
    (see `compute_software_version_result` for the resolution itself).

    Called from the Device post_save signal whenever the software_version
    custom field actually changes (see signals.py). Idempotent and cheap to
    call redundantly -- a pure resolve-and-write with no other side effects.

    Returns None (writes nothing) only when there's no `software-version`
    measure configured at all. Every other outcome -- no platform assigned,
    missing/invalid platform version data, or no running version reported --
    is itself a meaningful compliance signal and is written as a result
    (status not_applicable / error / error respectively -- there's no enum
    value for "no version reported" since the live measure's value_map has
    no key for it; see the module-level SOFTWARE_VERSION_KEY_* comment),
    rather than silently doing nothing.
    """
    measure = ComplianceMeasure.objects.filter(slug=SOFTWARE_VERSION_MEASURE_SLUG).first()
    if measure is None:
        return None

    status, value, details = compute_software_version_result(device, measure)
    return ComplianceResult.objects.create(
        device=device, measure=measure, status=status, value=value, details=details,
        source=SOFTWARE_VERSION_SOURCE,
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
    Used by the panel, the compliance tab's Value column, and the
    device-status API's display_text field.
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
            descendant_ids = assignment.platform.get_descendants(include_self=True).values_list('id', flat=True)
            qs = qs.filter(platform_id__in=descendant_ids)
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
            device_name=str(device),
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
