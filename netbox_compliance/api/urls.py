from django.urls import path

from netbox.api.routers import NetBoxRouter

from . import views

app_name = 'netbox_compliance'

router = NetBoxRouter()
router.register('measures', views.ComplianceMeasureViewSet)
router.register('packages', views.CompliancePackageViewSet)
router.register('package-measures', views.PackageMeasureViewSet)
router.register('package-assignments', views.PackageAssignmentViewSet)
router.register('measure-assignments', views.MeasureAssignmentViewSet)
router.register('exemptions', views.ComplianceExemptionViewSet)
router.register('results', views.ComplianceResultViewSet)
router.register('result-history', views.ComplianceResultHistoryViewSet)
router.register('snapshots', views.ComplianceSnapshotViewSet)
router.register('package-reports', views.CompliancePackageReportViewSet)

urlpatterns = [
    path('results/bulk/', views.BulkResultIngestView.as_view(), name='result-bulk'),
    path('package-reports/bulk/', views.PackageReportBulkIngestView.as_view(), name='package-report-bulk'),
    path('devices/<int:pk>/status/', views.DeviceComplianceStatusView.as_view(), name='device-status'),
    path(
        'devices/<int:pk>/effective-measures/',
        views.DeviceEffectiveMeasuresView.as_view(),
        name='device-effective-measures',
    ),
    path('reports/<str:period>/', views.MonthlyReportView.as_view(), name='monthly-report'),
]

urlpatterns += router.urls
