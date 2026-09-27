from django.urls import include, path

from utilities.urls import get_model_urls

from . import views

urlpatterns = [
    # ComplianceMeasure
    path('measures/', include(get_model_urls('netbox_compliance', 'compliancemeasure', detail=False))),
    path('measures/<int:pk>/', include(get_model_urls('netbox_compliance', 'compliancemeasure'))),

    # CompliancePackage
    path('packages/', include(get_model_urls('netbox_compliance', 'compliancepackage', detail=False))),
    path('packages/<int:pk>/', include(get_model_urls('netbox_compliance', 'compliancepackage'))),

    # PackageMeasure
    path('package-measures/', include(get_model_urls('netbox_compliance', 'packagemeasure', detail=False))),
    path('package-measures/<int:pk>/', include(get_model_urls('netbox_compliance', 'packagemeasure'))),

    # PackageAssignment
    path('package-assignments/', include(get_model_urls('netbox_compliance', 'packageassignment', detail=False))),
    path('package-assignments/<int:pk>/', include(get_model_urls('netbox_compliance', 'packageassignment'))),

    # MeasureAssignment
    path('measure-assignments/', include(get_model_urls('netbox_compliance', 'measureassignment', detail=False))),
    path('measure-assignments/<int:pk>/', include(get_model_urls('netbox_compliance', 'measureassignment'))),

    # ComplianceExemption
    path('exemptions/', include(get_model_urls('netbox_compliance', 'complianceexemption', detail=False))),
    path('exemptions/<int:pk>/', include(get_model_urls('netbox_compliance', 'complianceexemption'))),

    # ComplianceResult
    path('results/', include(get_model_urls('netbox_compliance', 'complianceresult', detail=False))),
    path('results/<int:pk>/', include(get_model_urls('netbox_compliance', 'complianceresult'))),

    # ComplianceResultHistory (read-only + delete)
    path('result-history/', include(get_model_urls('netbox_compliance', 'complianceresulthistory', detail=False))),
    path('result-history/<int:pk>/', include(get_model_urls('netbox_compliance', 'complianceresulthistory'))),

    # ComplianceSnapshot (read-only + delete)
    path('snapshots/', include(get_model_urls('netbox_compliance', 'compliancesnapshot', detail=False))),
    path('snapshots/<int:pk>/', include(get_model_urls('netbox_compliance', 'compliancesnapshot'))),

    # CompliancePackageReport (read-only + delete)
    path('package-reports/', include(get_model_urls('netbox_compliance', 'compliancepackagereport', detail=False))),
    path('package-reports/<int:pk>/', include(get_model_urls('netbox_compliance', 'compliancepackagereport'))),
    path(
        'package-reports/<int:pk>/raw/',
        views.CompliancePackageReportRawView.as_view(),
        name='compliancepackagereport_raw',
    ),

    # Monthly report
    path('reports/', views.MonthlyReportView.as_view(), name='monthly_report'),

    # Package / test status report
    path('reports/status/', views.PackageTestStatusReportView.as_view(), name='status_report'),

    # Measure adherence trend report
    path('reports/trend/', views.MeasureAdherenceTrendView.as_view(), name='measure_trend_report'),
]
