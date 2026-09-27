from dcim.models import Device, Site, SiteGroup
from extras.models import Tag
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers
from tenancy.models import Tenant

from ...models import ComplianceExemption, ComplianceMeasure, CompliancePackage

__all__ = ('ComplianceExemptionSerializer',)


class ComplianceExemptionSerializer(NetBoxModelSerializer):
    measure = serializers.PrimaryKeyRelatedField(queryset=ComplianceMeasure.objects.all(), required=False, allow_null=True)
    measure_name = serializers.SerializerMethodField()
    package = serializers.PrimaryKeyRelatedField(queryset=CompliancePackage.objects.all(), required=False, allow_null=True)
    package_name = serializers.SerializerMethodField()
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), required=False, allow_null=True)
    device_name = serializers.SerializerMethodField()
    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.all(), required=False, allow_null=True)
    site_name = serializers.SerializerMethodField()
    site_group = serializers.PrimaryKeyRelatedField(queryset=SiteGroup.objects.all(), required=False, allow_null=True)
    site_group_name = serializers.SerializerMethodField()
    tag = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), required=False, allow_null=True)
    tag_name = serializers.SerializerMethodField()
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.all(), required=False, allow_null=True)
    tenant_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ComplianceExemption
        fields = (
            'id', 'url', 'display', 'measure', 'measure_name', 'package', 'package_name',
            'device', 'device_name', 'site', 'site_name', 'site_group', 'site_group_name',
            'tag', 'tag_name', 'tenant', 'tenant_name',
            'justification', 'approved_by', 'valid_from', 'valid_until', 'is_active',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'measure', 'measure_name', 'package', 'package_name')

    def get_measure_name(self, obj):
        return obj.measure.name if obj.measure else None

    def get_package_name(self, obj):
        return obj.package.name if obj.package else None

    def get_device_name(self, obj):
        return obj.device.name if obj.device else None

    def get_site_name(self, obj):
        return obj.site.name if obj.site else None

    def get_site_group_name(self, obj):
        return obj.site_group.name if obj.site_group else None

    def get_tag_name(self, obj):
        return obj.tag.name if obj.tag else None

    def get_tenant_name(self, obj):
        return obj.tenant.name if obj.tenant else None
