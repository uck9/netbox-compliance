from rest_framework import serializers

from netbox.api.serializers import NetBoxModelSerializer

from ...choices import ComplianceMeasureResultTypeChoices
from ...models.measures import _validate_value_map
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
            'id', 'url', 'display', 'name', 'slug', 'title', 'description', 'category',
            'severity', 'max_result_age_days', 'status', 'comments', 'result_type',
            'pass_threshold', 'value_map', 'show_on_device_panel', 'panel_display_order',
            'display_template', 'required_detail_keys', 'tags',
            'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'slug', 'title')

    def validate(self, data):
        data = super().validate(data)
        result_type = data.get('result_type', getattr(self.instance, 'result_type', ComplianceMeasureResultTypeChoices.BOOLEAN))
        value_map = data.get('value_map', getattr(self.instance, 'value_map', {}))
        pass_threshold = data.get('pass_threshold', getattr(self.instance, 'pass_threshold', None))

        if result_type == ComplianceMeasureResultTypeChoices.ENUM:
            if not value_map:
                raise serializers.ValidationError({'value_map': 'Enum measures require a non-empty value_map.'})
            errors = _validate_value_map(value_map)
            if errors:
                raise serializers.ValidationError({'value_map': errors})
            if pass_threshold is not None:
                raise serializers.ValidationError({'pass_threshold': 'Enum measures must not set pass_threshold.'})
        elif result_type == ComplianceMeasureResultTypeChoices.PERCENTAGE:
            if pass_threshold is None:
                raise serializers.ValidationError({'pass_threshold': 'Percentage measures require pass_threshold.'})
            if value_map:
                raise serializers.ValidationError({'value_map': 'Percentage measures must not set value_map.'})
        else:  # boolean
            if pass_threshold is not None:
                raise serializers.ValidationError({'pass_threshold': 'Boolean measures must not set pass_threshold.'})
            if value_map:
                raise serializers.ValidationError({'value_map': 'Boolean measures must not set value_map.'})
        return data


class CompliancePackageSerializer(NetBoxModelSerializer):
    measures = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = CompliancePackage
        fields = (
            'id', 'url', 'display', 'name', 'slug', 'description', 'status',
            'measures', 'show_on_device_panel', 'panel_display_order', 'amber_threshold',
            'red_on_critical_fail', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'slug')


class PackageMeasureSerializer(NetBoxModelSerializer):
    package = serializers.PrimaryKeyRelatedField(queryset=CompliancePackage.objects.all())
    package_name = serializers.CharField(source='package.name', read_only=True)
    measure = serializers.PrimaryKeyRelatedField(queryset=ComplianceMeasure.objects.all())
    measure_name = serializers.CharField(source='measure.name', read_only=True)
    measure_title = serializers.CharField(source='measure.title', read_only=True)

    class Meta:
        model = PackageMeasure
        fields = (
            'id', 'url', 'display', 'package', 'package_name', 'measure', 'measure_name', 'measure_title',
            'weight', 'required', 'display_order', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'package', 'package_name', 'measure', 'measure_name')
