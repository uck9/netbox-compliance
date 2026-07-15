from datetime import date, timedelta

from core.choices import JobIntervalChoices
from netbox.jobs import JobRunner, system_job
from netbox.plugins import get_plugin_config

from ..services import generate_snapshots_for_period

__all__ = ('GenerateComplianceSnapshots',)


def previous_month_period(today=None):
    today = today or date.today()
    first_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_of_this_month - timedelta(days=1)
    return last_day_of_prev_month.replace(day=1)


@system_job(interval=JobIntervalChoices.INTERVAL_DAILY)
class GenerateComplianceSnapshots(JobRunner):
    """
    NetBox's system_job scheduler only supports fixed-minute intervals (no
    day-of-month concept), so this runs daily and no-ops unless today
    matches the configured `snapshot_day_of_month` setting -- at which
    point it (re)generates snapshots for the previous month. Resilient to
    missed runs/restarts since it just checks the calendar each day.
    """
    class Meta:
        name = 'NetBox Compliance - Generate Monthly Snapshots'
        description = 'Generates compliance snapshots for the previous month on the configured day of month.'

    def run(self, *args, **kwargs):
        snapshot_day = get_plugin_config('netbox_compliance', 'snapshot_day_of_month')
        today = date.today()
        if today.day != snapshot_day:
            self.logger.debug(
                f'Today ({today.isoformat()}) is not the configured snapshot day ({snapshot_day}); skipping.'
            )
            return

        period = previous_month_period(today)
        count = generate_snapshots_for_period(period)
        self.logger.info(f'Generated {count} compliance snapshots for {period:%Y-%m}.')
