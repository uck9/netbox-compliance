"""
Device signal handlers. Registered from NetBoxComplianceConfig.ready() --
receivers here must stay module-level functions (never closures defined
inside ready()) since Signal.connect() defaults to a weak reference and a
closure with no other strong reference is garbage-collected almost
immediately, silently unregistering the handler.
"""
from .services import SOFTWARE_VERSION_CF


def snapshot_prior_software_version(sender, instance, **kwargs):
    """
    pre_save: stash the currently-persisted software_version custom field
    value on the instance so post_save can tell whether it actually changed.
    A new (unsaved) instance has no prior value to fetch.
    """
    prior = None
    if instance.pk:
        prior = (
            sender.objects
            .filter(pk=instance.pk)
            .values_list(f'custom_field_data__{SOFTWARE_VERSION_CF}', flat=True)
            .first()
        )
    instance._compliance_prior_software_version = prior or None


def guard_package_assignment_tenant_narrowing(sender, instance, action, reverse, pk_set, **kwargs):
    """
    m2m_changed on PackageAssignment.tenants: reject adding tenants to a
    device-scoped assignment. Last-resort guard behind the form and API
    serializer checks -- catches direct shell/admin writes that bypass both.
    Only the forward direction ('pre_add' on a PackageAssignment instance)
    can produce the bad combination.
    """
    if action != 'pre_add' or reverse:
        return
    if instance.device_id and pk_set:
        from django.core.exceptions import ValidationError

        raise ValidationError(
            'Tenant narrowing does not apply to a device-scoped assignment.'
        )


def evaluate_software_version_on_change(sender, instance, **kwargs):
    """
    post_save: (re)evaluate the software-version compliance measure only
    when the software_version custom field actually changed -- avoids
    recomputing on every unrelated device save (bulk site moves, etc.).
    """
    from .services import evaluate_software_version

    prior = getattr(instance, '_compliance_prior_software_version', None)
    current = instance.custom_field_data.get(SOFTWARE_VERSION_CF) or None
    if prior != current:
        evaluate_software_version(instance)
