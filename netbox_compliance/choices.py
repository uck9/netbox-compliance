from utilities.choices import ChoiceSet


class ComplianceMeasureCategoryChoices(ChoiceSet):
    key = 'ComplianceMeasure.category'

    CONFIGURATION = 'configuration'
    OPERATIONAL = 'operational'
    SECURITY = 'security'
    OTHER = 'other'

    CHOICES = [
        (CONFIGURATION, 'Configuration', 'blue'),
        (OPERATIONAL, 'Operational', 'cyan'),
        (SECURITY, 'Security', 'red'),
        (OTHER, 'Other', 'grey'),
    ]


class ComplianceMeasureSeverityChoices(ChoiceSet):
    key = 'ComplianceMeasure.severity'

    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'
    INFORMATIONAL = 'informational'

    CHOICES = [
        (CRITICAL, 'Critical', 'red'),
        (HIGH, 'High', 'orange'),
        (MEDIUM, 'Medium', 'yellow'),
        (LOW, 'Low', 'blue'),
        (INFORMATIONAL, 'Informational', 'grey'),
    ]


class ComplianceMeasureResultTypeChoices(ChoiceSet):
    key = 'ComplianceMeasure.result_type'

    BOOLEAN = 'boolean'
    PERCENTAGE = 'percentage'
    ENUM = 'enum'

    CHOICES = [
        (BOOLEAN, 'Boolean', 'blue'),
        (PERCENTAGE, 'Percentage', 'cyan'),
        (ENUM, 'Enum', 'purple'),
    ]


class ComplianceMeasureStatusChoices(ChoiceSet):
    key = 'ComplianceMeasure.status'

    ACTIVE = 'active'
    DEPRECATED = 'deprecated'

    CHOICES = [
        (ACTIVE, 'Active', 'green'),
        (DEPRECATED, 'Deprecated', 'grey'),
    ]


class CompliancePackageStatusChoices(ChoiceSet):
    key = 'CompliancePackage.status'

    DRAFT = 'draft'
    ACTIVE = 'active'
    RETIRED = 'retired'

    CHOICES = [
        (DRAFT, 'Draft', 'grey'),
        (ACTIVE, 'Active', 'green'),
        (RETIRED, 'Retired', 'red'),
    ]


class ComplianceResultStatusChoices(ChoiceSet):
    key = 'ComplianceResult.status'

    PASS = 'pass'
    FAIL = 'fail'
    ERROR = 'error'
    NOT_APPLICABLE = 'not_applicable'

    CHOICES = [
        (PASS, 'Pass', 'green'),
        (FAIL, 'Fail', 'red'),
        (ERROR, 'Error', 'dark-red'),
        (NOT_APPLICABLE, 'Not Applicable', 'gray'),
    ]


class EffectiveStatusChoices(ChoiceSet):
    """
    Not a model field -- represents the resolved, point-in-time status of an
    effective measure on a device (current result, or lack thereof), used to
    colour badges consistently across the device tab, snapshots, and reports.
    """

    PASS = 'pass'
    FAIL = 'fail'
    ERROR = 'error'
    NOT_APPLICABLE = 'not_applicable'
    STALE = 'stale'
    PENDING = 'pending'
    EXEMPT = 'exempt'

    CHOICES = [
        (PASS, 'Pass', 'green'),
        (FAIL, 'Fail', 'red'),
        (ERROR, 'Error', 'dark-red'),
        (STALE, 'Stale', 'orange'),
        (PENDING, 'Pending', 'grey'),
        (NOT_APPLICABLE, 'Not Applicable', 'gray'),
        (EXEMPT, 'Exempt', 'blue'),
    ]


# Machine-checkable vocabulary for ComplianceMeasure.value_map entries (enum result_type).
# Not a ChoiceSet: these are values inside a JSONField, not a model field, so there's no
# get_FOO_display/form-widget to gain from ChoiceSet machinery.
VALUE_MAP_COLORS = {'green', 'orange', 'red', 'grey'}

# Traffic-light values for CompliancePackage resolution (services.package_traffic_light).
# Also plain strings, not a ChoiceSet, for the same reason -- display-only, derived, never
# stored on a model field.
TRAFFIC_LIGHT_COLORS = {'grey', 'green', 'amber', 'red'}
