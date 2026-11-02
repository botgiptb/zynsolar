from .models import CompanySetting, UserProfile


def company_settings(request):
    try:
        settings = CompanySetting.get_settings()
    except Exception:
        settings = None

    pending_approvals_count = 0
    active_orders_count = 0
    overdue_receivables_count = 0
    pending_tasks_count = 0
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        try:
            from bookings.models import SolarBooking, Task
            from decimal import Decimal
            active_orders_count = SolarBooking.objects.filter(
                is_cancelled=False,
                stage__in=[SolarBooking.STAGE_NEW, SolarBooking.STAGE_SURVEY, SolarBooking.STAGE_INSTALLATION]
            ).count()
            overdue_receivables_count = SolarBooking.objects.filter(
                is_cancelled=False,
                balance_amount__gt=Decimal('0.00'),
                stage=SolarBooking.STAGE_COMPLETED
            ).count()
            pending_tasks_count = Task.objects.filter(is_completed=False).count()
        except Exception:
            active_orders_count = 0
            overdue_receivables_count = 0
            pending_tasks_count = 0

        if request.user.is_staff or request.user.is_superuser:
            try:
                pending_approvals_count = UserProfile.objects.filter(status=UserProfile.STATUS_PENDING).count()
            except Exception:
                pending_approvals_count = 0

    return {
        'company_settings': settings,
        'app_name': 'Solar CRM',
        'app_version': '2.4.0',
        'pending_approvals_count': pending_approvals_count,
        'active_orders_count': active_orders_count,
        'overdue_receivables_count': overdue_receivables_count,
        'pending_tasks_count': pending_tasks_count,
    }
