from dcim.models import Device
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ...models import CompliancePackage, CompliancePackageReport

__all__ = ('CompliancePackageReportSerializer',)


class CompliancePackageReportSerializer(NetBoxModelSerializer):
    device = serializers.PrimaryKeyRelatedField(queryset=Device.objects.all(), required=False, allow_null=True)
    package = serializers.PrimaryKeyRelatedField(queryset=CompliancePackage.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CompliancePackageReport
        # Deliberately excludes `html` -- unlike ComplianceSnapshot's `data` (structured JSON,
        # genuinely useful to an API consumer), `html` is a self-contained document meant to be
        # rendered directly, not JSON-wrapped, and can be tens of KB+ -- fetch it via the
        # dedicated raw-HTML view (CompliancePackageReportRawView) instead.
        fields = (
            'id', 'url', 'display', 'device', 'device_name', 'package', 'package_slug', 'source',
            'timestamp', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'device_name', 'package_slug', 'timestamp')
