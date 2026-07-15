# NetBox Compliance

A [NetBox](https://github.com/netbox-community/netbox) plugin for tracking device compliance measures, grouping
them into weighted packages, assigning them to devices via rules or direct assignment, receiving results from
external analysis scripts via the REST API, and producing monthly point-in-time compliance snapshots for reporting.

External scripts perform all actual checks (config validation, dot1x, STP, local passwords, NTP sync, etc.) and
push results in via `POST /api/plugins/compliance/results/bulk/`. This plugin stores definitions, assignments,
results, exemptions, and snapshots, and computes weighted compliance scores.

## Compatibility

| NetBox Version | Plugin Version |
|-----------------|----------------|
| 4.5+            | 0.1.0          |

## Installation

```bash
pip install -e /opt/dev/netbox-compliance
```

Add to `PLUGINS` in `configuration.py`:

```python
PLUGINS = [
    'netbox_compliance',
]
```

Optionally configure `PLUGINS_CONFIG`:

```python
PLUGINS_CONFIG = {
    'netbox_compliance': {
        'result_retention_days': 90,
        'default_max_result_age_days': 35,
        'snapshot_day_of_month': 1,
    },
}
```

Then run migrations:

```bash
python manage.py migrate netbox_compliance
```

## Management Commands

- `generate_compliance_snapshots [--period YYYY-MM]` — generate (or regenerate) monthly snapshots for every
  device with at least one effective measure. Idempotent.
- `prune_compliance_results [--keep-days N] [--dry-run]` — delete raw results older than `N` days that fall
  within an already-snapshotted period.
