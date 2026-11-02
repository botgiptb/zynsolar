import logging
import traceback
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger('solar_crm')


class GlobalExceptionMiddleware:
    """
    Global exception handling middleware that catches unhandled exceptions,
    logs detailed diagnostics with stack traces, and returns clean JSON responses
    for AJAX/API requests or graceful error responses in production.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Extract user information safely
        user_str = "Anonymous"
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_str = f"{request.user.username} (ID: {request.user.id})"

        # Log full traceback and request details
        logger.error(
            "Unhandled Exception: [%s %s] by User: %s - %s\n%s",
            request.method,
            request.get_full_path(),
            user_str,
            str(exception),
            traceback.format_exc(),
            extra={
                'status_code': 500,
                'request': request,
            }
        )

        # Check if this is an AJAX or API request
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('Accept', '') or
            request.content_type == 'application/json' or
            '/api/' in request.path
        )

        if is_ajax:
            return JsonResponse({
                'status': 'error',
                'code': 500,
                'error': 'InternalServerError',
                'message': 'An unexpected error occurred while processing your request. Please try again later.'
            }, status=500)

        # In development mode (DEBUG=True), return None so Django displays the debug screen
        if settings.DEBUG:
            return None

        # In production mode (DEBUG=False), render the branded 500 error page
        from core.views import custom_server_error_view
        return custom_server_error_view(request)


from django.middleware.csrf import CsrfViewMiddleware


class DynamicDomainCsrfMiddleware(CsrfViewMiddleware):
    """
    Allows requests from any domain/origin while maintaining full CSRF token protection.
    Prevents 'Origin checking failed' and 'Referer checking failed' 403 errors when
    accessing the app from any custom domain, IP, or tunnel.
    """
    def _origin_verified(self, request):
        return True

    def _check_referer(self, request):
        return None

