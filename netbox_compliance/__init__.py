from netbox.plugins import PluginConfig

from .version import __version__


def _invalidate_device_panel_cache_on_result_change(sender, instance, **kwargs):
    from .services import invalidate_device_panel_cache
    invalidate_device_panel_cache(instance.device_id)


def _log_result_history_on_save(sender, instance, **kwargs):
    """
    Mirror every ComplianceResult save into an immutable ComplianceResultHistory
    row. A signal (not something baked into record_result()) so this can't be
    bypassed by whichever path did the write -- record_result()'s upsert, the
    plain REST viewset/admin form (manual corrections), or any future direct
    .save() -- all of them call Model.save() eventually, this is the one place
    that's guaranteed to see it.
    """
    from .models import ComplianceResultHistory

    ComplianceResultHistory.objects.create(
        device_id=instance.device_id,
        device_name=str(instance.device) if instance.device_id else '',
        measure_id=instance.measure_id,
        measure_slug=instance.measure.slug if instance.measure_id else '',
        status=instance.status,
        value=instance.value,
        details=instance.details,
        source=instance.source,
        timestamp=instance.timestamp,
    )


class NetBoxComplianceConfig(PluginConfig):
    name = 'netbox_compliance'
    verbose_name = 'NetBox Compliance'
    version = __version__
    description = 'Device compliance measure tracking, scoring, and monthly snapshot reporting'
    author = 'Nathan Reeves'
    author_email = ''
    base_url = 'compliance'
    min_version = '4.5.0'
    default_settings = {
        'result_retention_days': 90,
        'default_max_result_age_days': 35,
        'snapshot_day_of_month': 1,
    }

    def register_device_compliance_tab(self) -> None:
        """
        Register the Compliance tab on dcim.Device. Must happen here (during
        app loading) rather than relying on this plugin's own urls.py, since
        dcim's urls.py is imported before this plugin's urls.py in
        netbox/urls.py -- by then dcim's get_model_urls('dcim', 'device')
        call has already run and would miss a registration done later.
        """
        from dcim.models import Device
        from utilities.views import register_model_view

        register_model_view(Device, 'compliance')(
            'netbox_compliance.views.DeviceComplianceTabView',
        )

    def register_device_compliance_export(self) -> None:
        """
        Register the standalone per-device compliance export/download endpoint on
        dcim.Device (resolves to dcim:device_compliance_export) -- same "must
        happen here, not this plugin's own urls.py" reason as
        register_device_compliance_tab above. Deliberately not a ViewTab (no
        `tab` attribute on DeviceComplianceExportView) -- it's a document to
        download/print, not another tab in the device page's nav bar; it's
        linked from the Compliance tab template instead.
        """
        from dcim.models import Device
        from utilities.views import register_model_view

        register_model_view(Device, 'compliance_export')(
            'netbox_compliance.views.DeviceComplianceExportView',
        )

    def register_software_version_evaluation(self) -> None:
        """
        Recompute the `software-version` ComplianceResult whenever a Device's
        software_version custom field changes -- covers manual UI/bulk edits,
        CSV import, and REST/pynetbox writes uniformly, since all of them
        ultimately call Device.save(). pre_save snapshots the prior value so
        post_save can skip devices where an unrelated field changed.

        Same weak-reference caveat as register_result_cache_invalidation:
        receivers must be module-level functions, defined in signals.py.
        """
        from django.db.models.signals import post_save, pre_save
        from dcim.models import Device

        from .signals import evaluate_software_version_on_change, snapshot_prior_software_version

        pre_save.connect(
            snapshot_prior_software_version, sender=Device,
            dispatch_uid='compliance_snapshot_prior_software_version',
        )
        post_save.connect(
            evaluate_software_version_on_change, sender=Device,
            dispatch_uid='compliance_evaluate_software_version_on_change',
        )

    def register_result_cache_invalidation(self) -> None:
        """
        Invalidate the device-page compliance panel cache (services.py's
        get_device_panel_data, keyed compliance:panel:{device_id}) whenever
        a ComplianceResult is written or deleted -- covers both bulk
        ingestion and manual admin edits in one place. Scoped only to
        ComplianceResult (not PackageAssignment/MeasureAssignment/
        ComplianceExemption/PackageMeasure): those changes rely on the
        panel's 300s TTL instead, since resolving "which devices does this
        scope change affect" is the expensive query the cache exists to
        avoid doing eagerly.

        The receiver must be a module-level function, not a local closure:
        Signal.connect() defaults to a weak reference, and a closure with no
        other strong reference gets garbage-collected almost immediately
        after ready() returns, silently unregistering the handler.
        """
        from django.db.models.signals import post_delete, post_save

        from .models import ComplianceResult

        post_save.connect(
            _invalidate_device_panel_cache_on_result_change, sender=ComplianceResult,
            dispatch_uid='compliance_result_panel_cache_invalidate_save',
        )
        post_delete.connect(
            _invalidate_device_panel_cache_on_result_change, sender=ComplianceResult,
            dispatch_uid='compliance_result_panel_cache_invalidate_delete',
        )

    def register_result_history_logging(self) -> None:
        """
        Append a ComplianceResultHistory row every time a ComplianceResult is
        saved -- covers record_result()'s upsert (bulk ingest, the
        software-version signal, the custom-field import command) and manual
        admin edits via the plain viewset/form uniformly, same rationale as
        register_result_cache_invalidation above. Not post_delete: deleting
        the current-state row doesn't erase what was observed, so history is
        never touched by a ComplianceResult delete.

        Same weak-reference caveat as the other signals in this file:
        receivers must be module-level functions.
        """
        from django.db.models.signals import post_save

        from .models import ComplianceResult

        post_save.connect(
            _log_result_history_on_save, sender=ComplianceResult,
            dispatch_uid='compliance_result_history_log_save',
        )

    def ready(self):
        super().ready()
        from . import dashboard, jobs  # noqa: F401

        self.register_device_compliance_tab()
        self.register_device_compliance_export()
        self.register_software_version_evaluation()
        self.register_result_cache_invalidation()
        self.register_result_history_logging()


config = NetBoxComplianceConfig
