from dcim.models import Device
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ...models import ComplianceMeasure, ComplianceResult, ComplianceResultHistory

__all__ = ('ComplianceResultSerializer', 'ComplianceResultHistorySerializer')


class ComplianceResultSerializer(NetBoxModelSerializer):
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all())
    device_name = serializers.CharField(source='device.name', read_only=True)
    measure = serializers.PrimaryKeyRelatedField(queryset=ComplianceMeasure.objects.all())

    class Meta:
        model = ComplianceResult
        fields = (
            'id', 'url', 'display', 'device', 'device_name', 'measure', 'status', 'value', 'timestamp',
            'source', 'details', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'device', 'device_name', 'measure', 'status')


class ComplianceResultHistorySerializer(NetBoxModelSerializer):
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), allow_null=True)
    measure = serializers.PrimaryKeyRelatedField(queryset=ComplianceMeasure.objects.all(), allow_null=True)

    class Meta:
        model = ComplianceResultHistory
        fields = (
            'id', 'url', 'display', 'device', 'device_name', 'measure', 'measure_slug', 'status', 'value',
            'timestamp', 'source', 'details', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'device_name', 'measure_slug', 'status')
