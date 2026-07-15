from datetime import date, timedelta

import django_tables2 as tables

from netbox.tables import NetBoxTable, columns

from ..models import ComplianceExemption

__all__ = ('ComplianceExemptionTable',)

EXPIRING_SOON_DAYS = 30


class ComplianceExemptionTable(NetBoxTable):
    measure = tables.Column(linkify=True)
    device = tables.Column(linkify=True)
    site = tables.Column(linkify=True)
    site_group = tables.Column(linkify=True)
    tag = tables.TemplateColumn(
        template_code='{% if value %}<span class="badge" style="background-color: {{ value.color|default:"9e9e9e" }}">{{ value }}</span>{% endif %}',
        verbose_name='Tag',
    )
    valid_from = columns.DateColumn()
    valid_until = columns.DateColumn()
    is_active = columns.BooleanColumn(verbose_name='Active')
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:complianceexemption_list')

    class Meta(NetBoxTable.Meta):
        model = ComplianceExemption
        fields = (
            'pk', 'id', 'measure', 'device', 'site', 'site_group', 'tag',
            'justification', 'approved_by', 'valid_from', 'valid_until', 'is_active',
            'tags', 'created', 'last_updated', 'actions',
        )
        default_columns = (
            'pk', 'measure', 'device', 'site', 'site_group', 'tag',
            'valid_from', 'valid_until', 'is_active',
        )
        row_attrs = {
            'class': lambda record: (
                'text-warning'
                if record.is_active and record.valid_until and record.valid_until <= date.today() + timedelta(days=EXPIRING_SOON_DAYS)
                else ''
            ),
        }
