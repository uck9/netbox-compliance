import django_tables2 as tables

from netbox.tables import NetBoxTable, columns

from ..models import ComplianceSnapshot

__all__ = ('ComplianceSnapshotTable',)


class ComplianceSnapshotTable(NetBoxTable):
    device = tables.Column(linkify=True)
    device_name = tables.Column()
    period = columns.DateColumn()
    overall_score = tables.Column(verbose_name='Score')
    compliant = columns.BooleanColumn()
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:compliancesnapshot_list')
    actions = columns.ActionsColumn(actions=('delete', 'changelog'))

    class Meta(NetBoxTable.Meta):
        model = ComplianceSnapshot
        fields = (
            'pk', 'id', 'device', 'device_name', 'period', 'overall_score',
            'compliant', 'created', 'tags', 'actions',
        )
        default_columns = ('pk', 'device_name', 'period', 'overall_score', 'compliant')
