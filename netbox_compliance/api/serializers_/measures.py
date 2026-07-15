from rest_framework import serializers

from netbox.api.serializers import NetBoxModelSerializer

from ...models import ComplianceMeasure, CompliancePackage, PackageMeasure

__all__ = (
    'ComplianceMeasureSerializer',
    'CompliancePackageSerializer',
    'PackageMeasureSerializer',
)


class ComplianceMeasureSerializer(NetBoxModelSerializer):
    class Meta:
        model = ComplianceMeasure
        fields = (
            'id', 'url', 'display', 'name', 'slug', 'description', 'category',
            'severity', 'max_result_age_days', 'status', 'comments', 'tags',
            'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'slug')


class CompliancePackageSerializer(NetBoxModelSerializer):
    measures = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = CompliancePackage
        fields = (
            'id', 'url', 'display', 'name', 'slug', 'description', 'status',
            'measures', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'slug')


class PackageMeasureSerializer(NetBoxModelSerializer):
    package = serializers.PrimaryKeyRelatedField(queryset=CompliancePackage.objects.all())
    measure = serializers.PrimaryKeyRelatedField(queryset=ComplianceMeasure.objects.all())

    class Meta:
        model = PackageMeasure
        fields = (
            'id', 'url', 'display', 'package', 'measure', 'weight', 'required',
            'display_order', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'package', 'measure')
