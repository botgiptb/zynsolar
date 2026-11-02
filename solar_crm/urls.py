from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('customers/', include('customers.urls')),
    path('bookings/', include('bookings.urls')),
    path('tasks/', RedirectView.as_view(pattern_name='bookings:task_list', permanent=False), name='tasks_shortcut'),
    path('calendar/', RedirectView.as_view(pattern_name='bookings:calendar', permanent=False), name='calendar_shortcut'),
    path('reports/', include('reports.urls')),
]

# Custom HTTP Error Handlers
handler404 = 'core.views.custom_page_not_found_view'
handler500 = 'core.views.custom_server_error_view'
handler403 = 'core.views.custom_permission_denied_view'
handler400 = 'core.views.custom_bad_request_view'

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
