from dcim.models import Device, Site, SiteGroup
from extras.models import Tag
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ...models import ComplianceExemption, ComplianceMeasure

__all__ = ('ComplianceExemptionSerializer',)


class ComplianceExemptionSerializer(NetBoxModelSerializer):
    measure = serializers.PrimaryKeyRelatedField(queryset=ComplianceMeasure.objects.all())
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), required=False, allow_null=True)
    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.all(), required=False, allow_null=True)
    site_group = serializers.PrimaryKeyRelatedField(queryset=SiteGroup.objects.all(), required=False, allow_null=True)
    tag = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), required=False, allow_null=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ComplianceExemption
        fields = (
            'id', 'url', 'display', 'measure', 'device', 'site', 'site_group', 'tag',
            'justification', 'approved_by', 'valid_from', 'valid_until', 'is_active',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'measure')
