import django_tables2 as tables

from netbox.tables import ChoiceFieldColumn, NetBoxTable, columns

from ..models import ComplianceResult, ComplianceResultHistory

__all__ = ('ComplianceResultTable', 'ComplianceResultHistoryTable')


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


class ComplianceResultHistoryTable(NetBoxTable):
    # device/measure (linkify) plus the denormalized device_name/measure_slug --
    # same pattern as ComplianceSnapshotTable, since either FK can be null (SET_NULL)
    # once the source device/measure is deleted while the denormalized text survives.
    device = tables.Column(linkify=True)
    device_name = tables.Column()
    measure = tables.Column(linkify=True)
    measure_slug = tables.Column()
    status = ChoiceFieldColumn()
    timestamp = columns.DateTimeColumn()
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:complianceresulthistory_list')
    # No edit view exists for this model (system-generated, append-only) -- the
    # inherited NetBoxTable default actions column tries edit/delete/changelog and
    # NoReverseMatch's on the missing edit URL. Same restriction ComplianceSnapshotTable
    # uses for the same reason.
    actions = columns.ActionsColumn(actions=('delete', 'changelog'))

    class Meta(NetBoxTable.Meta):
        model = ComplianceResultHistory
        fields = (
            'pk', 'id', 'device', 'device_name', 'measure', 'measure_slug', 'status', 'value',
            'timestamp', 'source', 'tags', 'created',
        )
        default_columns = ('pk', 'device_name', 'measure_slug', 'status', 'value', 'timestamp', 'source')
