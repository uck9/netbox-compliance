from django.core.management.base import BaseCommand

from netbox_compliance.models import ComplianceSnapshot, ComplianceSnapshotMeasureResult
from netbox_compliance.services import snapshot_measure_result_objects


class Command(BaseCommand):
    help = (
        'One-off backfill for ComplianceSnapshot rows written before the site/role/'
        'ComplianceSnapshotMeasureResult trend-reporting fields existed: fills in site/'
        'role from the snapshot\'s device (skipped where the device has since been '
        'deleted -- that information was never retained) and derives measure_results '
        'rows from each snapshot\'s already-frozen `data`, without recomputing scoring '
        'for past periods. Idempotent -- safe to re-run; only touches what is missing.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing anything.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        site_role_updates = 0
        measure_rows_created = 0

        snapshots = ComplianceSnapshot.objects.select_related('device__site', 'device__role').all()
        for snapshot in snapshots.iterator():
            if snapshot.device_id and (
                snapshot.site_id != snapshot.device.site_id or snapshot.role_id != snapshot.device.role_id
            ):
                site_role_updates += 1
                if not dry_run:
                    snapshot.site = snapshot.device.site
                    snapshot.site_name = str(snapshot.device.site) if snapshot.device.site else ''
                    snapshot.role = snapshot.device.role
                    snapshot.role_name = str(snapshot.device.role) if snapshot.device.role else ''
                    snapshot.save(update_fields=['site', 'site_name', 'role', 'role_name'])

            if not ComplianceSnapshotMeasureResult.objects.filter(snapshot=snapshot).exists():
                rows = snapshot_measure_result_objects(snapshot, snapshot.data)
                measure_rows_created += len(rows)
                if not dry_run and rows:
                    ComplianceSnapshotMeasureResult.objects.bulk_create(rows)

        verb = 'Would update' if dry_run else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} site/role on {site_role_updates} snapshot(s); '
            f'{"would create" if dry_run else "created"} {measure_rows_created} measure result row(s).'
        ))
