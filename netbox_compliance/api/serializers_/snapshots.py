from dcim.models import Device
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ...models import ComplianceSnapshot

__all__ = ('ComplianceSnapshotSerializer',)


class ComplianceSnapshotSerializer(NetBoxModelSerializer):
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), required=False, allow_null=True)

    class Meta:
        model = ComplianceSnapshot
        fields = (
            'id', 'url', 'display', 'device', 'device_name', 'period', 'overall_score',
            'compliant', 'data', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'device_name', 'period', 'overall_score', 'compliant')
