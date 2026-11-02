from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('', views.CustomerListView.as_view(), name='list'),
    path('create/', views.CustomerCreateView.as_view(), name='create'),
    path('<int:pk>/', views.CustomerDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='edit'),
    path('<int:pk>/archive/', views.CustomerArchiveToggleView.as_view(), name='archive_toggle'),
    path('<int:pk>/attachments/upload/', views.CustomerAttachmentUploadView.as_view(), name='attachment_upload'),
    path('<int:pk>/attachments/<int:attachment_pk>/delete/', views.CustomerAttachmentDeleteView.as_view(), name='attachment_delete'),
    path('api/quick-create/', views.CustomerQuickCreateAjaxView.as_view(), name='quick_create'),
]
