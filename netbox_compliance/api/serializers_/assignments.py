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
    package_name = serializers.CharField(source='package.name', read_only=True)
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), required=False, allow_null=True)
    device_name = serializers.SerializerMethodField()
    device_role = serializers.PrimaryKeyRelatedField(queryset=DeviceRole.objects.all(), required=False, allow_null=True)
    device_role_name = serializers.SerializerMethodField()
    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.all(), required=False, allow_null=True)
    site_name = serializers.SerializerMethodField()
    site_group = serializers.PrimaryKeyRelatedField(queryset=SiteGroup.objects.all(), required=False, allow_null=True)
    site_group_name = serializers.SerializerMethodField()
    platform = serializers.PrimaryKeyRelatedField(queryset=Platform.objects.all(), required=False, allow_null=True)
    platform_name = serializers.SerializerMethodField()
    tag = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), required=False, allow_null=True)
    tag_name = serializers.SerializerMethodField()

    class Meta:
        model = PackageAssignment
        fields = (
            'id', 'url', 'display', 'package', 'package_name', 'device', 'device_name',
            'device_role', 'device_role_name', 'site', 'site_name', 'site_group', 'site_group_name',
            'platform', 'platform_name', 'tag', 'tag_name', 'description', 'tags', 'custom_fields',
            'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'package', 'package_name')

    def get_device_name(self, obj):
        return obj.device.name if obj.device else None

    def get_device_role_name(self, obj):
        return obj.device_role.name if obj.device_role else None

    def get_site_name(self, obj):
        return obj.site.name if obj.site else None

    def get_site_group_name(self, obj):
        return obj.site_group.name if obj.site_group else None

    def get_platform_name(self, obj):
        return obj.platform.name if obj.platform else None

    def get_tag_name(self, obj):
        return obj.tag.name if obj.tag else None


class MeasureAssignmentSerializer(NetBoxModelSerializer):
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all())
    device_name = serializers.CharField(source='device.name', read_only=True)
    measure = serializers.PrimaryKeyRelatedField(queryset=ComplianceMeasure.objects.all())
    measure_name = serializers.CharField(source='measure.name', read_only=True)

    class Meta:
        model = MeasureAssignment
        fields = (
            'id', 'url', 'display', 'device', 'device_name', 'measure', 'measure_name',
            'weight', 'description', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'device', 'device_name', 'measure', 'measure_name')
