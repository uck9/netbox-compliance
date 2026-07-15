from dcim.models import Device, DeviceRole, Platform, Site, SiteGroup
from extras.models import Tag
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ...models import ComplianceMeasure, CompliancePackage, MeasureAssignment, PackageAssignment

__all__ = (
    'PackageAssignmentSerializer',
    'MeasureAssignmentSerializer',
)


class PackageAssignmentSerializer(NetBoxModelSerializer):
    package = serializers.PrimaryKeyRelatedField(queryset=CompliancePackage.objects.all())
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), required=False, allow_null=True)
    device_role = serializers.PrimaryKeyRelatedField(queryset=DeviceRole.objects.all(), required=False, allow_null=True)
    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.all(), required=False, allow_null=True)
    site_group = serializers.PrimaryKeyRelatedField(queryset=SiteGroup.objects.all(), required=False, allow_null=True)
    platform = serializers.PrimaryKeyRelatedField(queryset=Platform.objects.all(), required=False, allow_null=True)
    tag = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), required=False, allow_null=True)

    class Meta:
        model = PackageAssignment
        fields = (
            'id', 'url', 'display', 'package', 'device', 'device_role', 'site',
            'site_group', 'platform', 'tag', 'description', 'tags', 'custom_fields',
            'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'package')


class MeasureAssignmentSerializer(NetBoxModelSerializer):
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all())
    measure = serializers.PrimaryKeyRelatedField(queryset=ComplianceMeasure.objects.all())

    class Meta:
        model = MeasureAssignment
        fields = (
            'id', 'url', 'display', 'device', 'measure', 'weight', 'description',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'device', 'measure')
