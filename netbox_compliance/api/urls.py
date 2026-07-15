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
router.register('snapshots', views.ComplianceSnapshotViewSet)

urlpatterns = [
    path('results/bulk/', views.BulkResultIngestView.as_view(), name='result-bulk'),
    path('devices/<int:pk>/status/', views.DeviceComplianceStatusView.as_view(), name='device-status'),
    path('reports/<str:period>/', views.MonthlyReportView.as_view(), name='monthly-report'),
]

urlpatterns += router.urls
