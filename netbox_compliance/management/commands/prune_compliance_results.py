from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from netbox.plugins import get_plugin_config
from netbox_compliance.models import ComplianceResultHistory, ComplianceSnapshot


class Command(BaseCommand):
    help = (
        'Delete ComplianceResultHistory entries older than --keep-days that fall within an '
        'already-snapshotted period (entries not yet captured in a snapshot are never pruned). '
        'ComplianceResult itself is never touched -- it only ever holds the current result per '
        'device/measure (one row, kept up to date in place), not a growing history, so there is '
        'nothing there to prune by age.'
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
            help='Report how many history entries would be deleted without deleting them.',
        )

    def handle(self, *args, **options):
        keep_days = options['keep_days']
        if keep_days is None:
            keep_days = get_plugin_config('netbox_compliance', 'result_retention_days')
        cutoff = timezone.now() - timedelta(days=keep_days)

        snapshotted_periods = set(
            ComplianceSnapshot.objects.exclude(device__isnull=True).values_list('device_id', 'period')
        )

        old_entries = ComplianceResultHistory.objects.filter(timestamp__lt=cutoff).only('id', 'device_id', 'timestamp')
        to_delete_ids = [
            entry.pk for entry in old_entries
            # device_id is None means the device itself has since been deleted (SET_NULL) --
            # no live device left to protect and no future snapshot will ever cover it, so age
            # alone is enough. Otherwise, same rule as before: only prune once a snapshot has
            # already captured that device+period.
            if entry.device_id is None or (entry.device_id, entry.timestamp.date().replace(day=1)) in snapshotted_periods
        ]
        count = len(to_delete_ids)

        if options['dry_run']:
            self.stdout.write(f'Would delete {count} compliance result history entries older than {keep_days} days (dry run).')
            return

        ComplianceResultHistory.objects.filter(pk__in=to_delete_ids).delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {count} compliance result history entries older than {keep_days} days.'))
