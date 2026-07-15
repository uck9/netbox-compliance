import django_tables2 as tables

from netbox.tables import ChoiceFieldColumn, NetBoxTable, columns

from ..models import ComplianceResult

__all__ = ('ComplianceResultTable',)


class ComplianceResultTable(NetBoxTable):
    device = tables.Column(linkify=True)
    measure = tables.Column(linkify=True)
    status = ChoiceFieldColumn()
    timestamp = columns.DateTimeColumn()
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:complianceresult_list')

    class Meta(NetBoxTable.Meta):
        model = ComplianceResult
        fields = (
            'pk', 'id', 'device', 'measure', 'status', 'timestamp', 'source',
            'tags', 'created', 'last_updated', 'actions',
        )
        default_columns = ('pk', 'device', 'measure', 'status', 'timestamp', 'source')
