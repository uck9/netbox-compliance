from django.core.management.base import BaseCommand, CommandError

from netbox_compliance.models import ComplianceMeasure, ComplianceResult
from netbox_compliance.services import (
    SOFTWARE_VERSION_MEASURE_SLUG,
    compute_software_version_result,
    evaluate_software_version,
)


class Command(BaseCommand):
    help = (
        'Audit: for every device with an existing software-version ComplianceResult, recompute the '
        'expected result from the current platform policy and report any device whose stored '
        'status/value/target no longer matches. Read-only by default; pass --fix to write a fresh '
        'corrected ComplianceResult for every mismatch found (including devices whose result is '
        'currently a manually-set "exempted" value -- --fix always writes the real computed state, '
        'overriding it).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose', action='store_true',
            help='Also list devices that already match (default: only mismatches are printed).',
        )
        parser.add_argument(
            '--fix', action='store_true',
            help='Write a fresh ComplianceResult (via evaluate_software_version) for every mismatch found.',
        )

    def handle(self, *args, **options):
        measure = ComplianceMeasure.objects.filter(slug=SOFTWARE_VERSION_MEASURE_SLUG).first()
        if measure is None:
            raise CommandError(f"No ComplianceMeasure with slug {SOFTWARE_VERSION_MEASURE_SLUG!r} exists.")

        latest_results = (
            ComplianceResult.objects
            .filter(measure=measure)
            .select_related('device', 'device__platform', 'device__role', 'device__device_type')
            .order_by('device_id', '-timestamp')
            .distinct('device_id')
        )

        checked = 0
        mismatches = []
        for result in latest_results:
            checked += 1
            device = result.device
            if device is None:
                continue  # device deleted since this result was recorded

            expected_status, expected_value, expected_details = compute_software_version_result(device, measure)
            expected_target = expected_details.get('target')
            stored_target = result.details.get('target') if isinstance(result.details, dict) else None

            if (result.status, result.value, stored_target) != (expected_status, expected_value, expected_target):
                mismatches.append({
                    'device': device,
                    'stored': (result.status, result.value, stored_target),
                    'expected': (expected_status, expected_value, expected_target),
                })
            elif options['verbose']:
                self.stdout.write(f'{device}: OK ({result.status}/{result.value}, target={stored_target})')

        for m in mismatches:
            stored_status, stored_value, stored_target = m['stored']
            exp_status, exp_value, exp_target = m['expected']
            self.stdout.write(self.style.WARNING(
                f"{m['device']}: stored status={stored_status!r} value={stored_value!r} target={stored_target!r} "
                f"-- expected status={exp_status!r} value={exp_value!r} target={exp_target!r}"
            ))

        self.stdout.write(self.style.SUCCESS(
            f'Checked {checked} device(s) with a software-version result: {len(mismatches)} mismatch(es).'
        ))

        if options['fix'] and mismatches:
            for m in mismatches:
                evaluate_software_version(m['device'])
            self.stdout.write(self.style.SUCCESS(f'Wrote {len(mismatches)} corrected ComplianceResult row(s).'))
