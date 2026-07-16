from django.core.management.base import BaseCommand, CommandError

from dcim.models import Device
from netbox_compliance.choices import ComplianceMeasureResultTypeChoices
from netbox_compliance.models import ComplianceMeasure, ComplianceResult
from netbox_compliance.services import enum_credit_status


class Command(BaseCommand):
    help = (
        'Seed ComplianceResult rows for an enum-type measure from existing device custom '
        'fields, so a device panel/tab has data before the first script run posts real results.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--measure', required=True, help='Slug of the enum-type ComplianceMeasure to populate.')
        parser.add_argument('--value-cf', required=True, help='Custom field name holding the enum key (must match a value_map key).')
        parser.add_argument(
            '--detail-cf', action='append', default=[], metavar='KEY=CFNAME',
            help='Repeatable. Maps a details-dict key to a device custom field, e.g. --detail-cf running=sw_running_version',
        )
        parser.add_argument('--source', default='import_results_from_custom_fields', help='Source label recorded on created results.')
        parser.add_argument('--dry-run', action='store_true', help='Report what would be created without writing.')

    def handle(self, *args, **options):
        measure = ComplianceMeasure.objects.filter(slug=options['measure']).first()
        if not measure:
            raise CommandError(f"Unknown measure slug: {options['measure']!r}")
        if measure.result_type != ComplianceMeasureResultTypeChoices.ENUM:
            raise CommandError(f"{measure.slug!r} is not an enum-type measure.")

        detail_map = {}
        for pair in options['detail_cf']:
            if '=' not in pair:
                raise CommandError(f"--detail-cf must be KEY=CFNAME, got {pair!r}")
            key, cf_name = pair.split('=', 1)
            detail_map[key] = cf_name

        missing_required = set(measure.required_detail_keys) - set(detail_map)
        if missing_required:
            raise CommandError(f"--detail-cf missing mappings for required_detail_keys: {sorted(missing_required)}")

        value_cf = options['value_cf']
        dry_run = options['dry_run']
        created, skipped = 0, 0

        for device in Device.objects.exclude(**{f'custom_field_data__{value_cf}__isnull': True}):
            raw_value = device.custom_field_data.get(value_cf)
            if raw_value not in measure.value_map:
                self.stdout.write(self.style.WARNING(
                    f"{device}: custom field {value_cf!r}={raw_value!r} is not a known value_map "
                    f"key for {measure.slug!r}, skipping"
                ))
                skipped += 1
                continue

            details = {key: device.custom_field_data.get(cf_name) for key, cf_name in detail_map.items()}
            missing_values = [key for key in measure.required_detail_keys if details.get(key) in (None, '')]
            if missing_values:
                self.stdout.write(self.style.WARNING(f"{device}: missing detail values for {missing_values}, skipping"))
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"Would create: {device} -> {measure.slug} = {raw_value!r} {details}")
            else:
                ComplianceResult.objects.create(
                    device=device,
                    measure=measure,
                    status=enum_credit_status(measure.value_map[raw_value]),
                    value=raw_value,
                    details=details,
                    source=options['source'],
                )
            created += 1

        verb = 'Would create' if dry_run else 'Created'
        self.stdout.write(self.style.SUCCESS(f"{verb} {created} results ({skipped} skipped)."))
