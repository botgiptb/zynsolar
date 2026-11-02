from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.ReportDashboardView.as_view(), name='dashboard'),
    path('staff/', views.StaffPerformanceReportView.as_view(), name='staff_performance'),
    path('teams/', views.TeamPerformanceReportView.as_view(), name='team_performance'),
    path('export/csv/', views.ExportCSVReportView.as_view(), name='export_csv'),
    path('export/excel/', views.ExportExcelReportView.as_view(), name='export_excel'),
    path('print/', views.PrintableReportView.as_view(), name='printable'),
]
