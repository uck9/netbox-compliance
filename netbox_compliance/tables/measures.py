import django_tables2 as tables

from netbox.tables import ChoiceFieldColumn, NetBoxTable, columns

from ..models import ComplianceMeasure, CompliancePackage, PackageMeasure

__all__ = (
    'ComplianceMeasureTable',
    'CompliancePackageTable',
    'PackageMeasureTable',
)


class ComplianceMeasureTable(NetBoxTable):
    name = tables.Column(linkify=True)
    category = ChoiceFieldColumn()
    severity = ChoiceFieldColumn()
    status = ChoiceFieldColumn()
    package_count = tables.Column(
        accessor='package_count',
        verbose_name='Packages',
    )
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:compliancemeasure_list')

    class Meta(NetBoxTable.Meta):
        model = ComplianceMeasure
        fields = (
            'pk', 'id', 'name', 'slug', 'category', 'severity', 'status',
            'max_result_age_days', 'package_count', 'description', 'comments',
            'tags', 'created', 'last_updated', 'actions',
        )
        default_columns = ('pk', 'name', 'category', 'severity', 'status', 'max_result_age_days', 'package_count')


class CompliancePackageTable(NetBoxTable):
    name = tables.Column(linkify=True)
    status = ChoiceFieldColumn()
    measure_count = tables.Column(
        accessor='measure_count',
        verbose_name='Measures',
    )
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:compliancepackage_list')

    class Meta(NetBoxTable.Meta):
        model = CompliancePackage
        fields = (
            'pk', 'id', 'name', 'slug', 'status', 'measure_count', 'description',
            'tags', 'created', 'last_updated', 'actions',
        )
        default_columns = ('pk', 'name', 'status', 'measure_count', 'description')


class PackageMeasureTable(NetBoxTable):
    package = tables.Column(linkify=True)
    measure = tables.Column(linkify=True)
    required = columns.BooleanColumn()
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:packagemeasure_list')

    class Meta(NetBoxTable.Meta):
        model = PackageMeasure
        fields = (
            'pk', 'id', 'package', 'measure', 'weight', 'required', 'display_order',
            'tags', 'created', 'last_updated', 'actions',
        )
        default_columns = ('pk', 'package', 'measure', 'weight', 'required', 'display_order')
