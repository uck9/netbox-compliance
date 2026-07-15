import django_tables2 as tables

from netbox.tables import NetBoxTable, columns

from ..models import MeasureAssignment, PackageAssignment

__all__ = (
    'PackageAssignmentTable',
    'MeasureAssignmentTable',
)


class PackageAssignmentTable(NetBoxTable):
    package = tables.Column(linkify=True)
    device = tables.Column(linkify=True)
    device_role = tables.Column(linkify=True)
    site = tables.Column(linkify=True)
    site_group = tables.Column(linkify=True)
    platform = tables.Column(linkify=True)
    tag = tables.TemplateColumn(
        template_code='{% if value %}<span class="badge" style="background-color: {{ value.color|default:"9e9e9e" }}">{{ value }}</span>{% endif %}',
        verbose_name='Tag',
    )
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:packageassignment_list')

    class Meta(NetBoxTable.Meta):
        model = PackageAssignment
        fields = (
            'pk', 'id', 'package', 'device', 'device_role', 'site', 'site_group',
            'platform', 'tag', 'description', 'tags', 'created', 'last_updated', 'actions',
        )
        default_columns = ('pk', 'package', 'device', 'device_role', 'site', 'site_group', 'platform', 'tag')


class MeasureAssignmentTable(NetBoxTable):
    device = tables.Column(linkify=True)
    measure = tables.Column(linkify=True)
    tags = columns.TagColumn(url_name='plugins:netbox_compliance:measureassignment_list')

    class Meta(NetBoxTable.Meta):
        model = MeasureAssignment
        fields = (
            'pk', 'id', 'device', 'measure', 'weight', 'description',
            'tags', 'created', 'last_updated', 'actions',
        )
        default_columns = ('pk', 'device', 'measure', 'weight')
