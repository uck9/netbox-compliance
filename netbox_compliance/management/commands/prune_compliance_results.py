from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from netbox.plugins import get_plugin_config
from netbox_compliance.models import ComplianceResult, ComplianceSnapshot


class Command(BaseCommand):
    help = (
        'Delete raw compliance results older than --keep-days that fall within an '
        'already-snapshotted period (results not yet captured in a snapshot are never pruned).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-days',
            type=int,
            default=None,
            help='Override the result_retention_days plugin setting.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report how many results would be deleted without deleting them.',
        )

    def handle(self, *args, **options):
        keep_days = options['keep_days']
        if keep_days is None:
            keep_days = get_plugin_config('netbox_compliance', 'result_retention_days')
        cutoff = timezone.now() - timedelta(days=keep_days)

        snapshotted_periods = set(
            ComplianceSnapshot.objects.exclude(device__isnull=True).values_list('device_id', 'period')
        )

        to_delete_ids = [
            result.pk for result in ComplianceResult.objects.filter(timestamp__lt=cutoff).only('id', 'device_id', 'timestamp')
            if (result.device_id, result.timestamp.date().replace(day=1)) in snapshotted_periods
        ]
        count = len(to_delete_ids)

        if options['dry_run']:
            self.stdout.write(f'Would delete {count} compliance results older than {keep_days} days (dry run).')
            return

        ComplianceResult.objects.filter(pk__in=to_delete_ids).delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {count} compliance results older than {keep_days} days.'))
