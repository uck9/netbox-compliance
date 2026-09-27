import django_tables2 as tables

from netbox.tables import NetBoxTable, columns

from ..models import CompliancePackageReport

__all__ = ('CompliancePackageReportTable',)


class CompliancePackageReportTable(NetBoxTable):
    device = tables.Column(linkify=True)
    device_name = tables.Column()
    package = tables.Column(linkify=True)
    package_slug = tables.Column()
    source = tables.Column()
    timestamp = columns.DateTimeColumn()
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:compliancepackagereport_list')
    actions = columns.ActionsColumn(actions=('delete', 'changelog'))

    class Meta(NetBoxTable.Meta):
        model = CompliancePackageReport
        fields = (
            'pk', 'id', 'device', 'device_name', 'package', 'package_slug', 'source',
            'timestamp', 'created', 'tags', 'actions',
        )
        default_columns = ('pk', 'device_name', 'package_slug', 'source', 'timestamp')
