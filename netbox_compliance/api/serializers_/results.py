from dcim.models import Device
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ...models import ComplianceMeasure, ComplianceResult

__all__ = ('ComplianceResultSerializer',)


class ComplianceResultSerializer(NetBoxModelSerializer):
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all())
    measure = serializers.PrimaryKeyRelatedField(queryset=ComplianceMeasure.objects.all())

    class Meta:
        model = ComplianceResult
        fields = (
            'id', 'url', 'display', 'device', 'measure', 'status', 'value', 'timestamp',
            'source', 'details', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'device', 'measure', 'status')
