from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from netbox_compliance.jobs.generate_snapshots import previous_month_period
from netbox_compliance.services import generate_snapshots_for_period


class Command(BaseCommand):
    help = (
        'Generate (or regenerate) compliance snapshots for a period. Idempotent -- '
        're-running for a period replaces any existing snapshots for that period.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            default=None,
            help='Period to snapshot, as YYYY-MM. Defaults to the previous calendar month.',
        )

    def handle(self, *args, **options):
        period_str = options['period']
        if period_str:
            try:
                period = datetime.strptime(period_str, '%Y-%m').date().replace(day=1)
            except ValueError:
                raise CommandError('--period must be in YYYY-MM format')
        else:
            period = previous_month_period()

        count = generate_snapshots_for_period(period)
        self.stdout.write(self.style.SUCCESS(f'Generated {count} compliance snapshots for {period:%Y-%m}.'))
