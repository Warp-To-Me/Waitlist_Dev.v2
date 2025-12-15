import logging
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound

logger = logging.getLogger(__name__)

def frontend_app(request):
    """
    Serves the compiled React app (index.html).
    In development, this might not be hit if Vite dev server is used,
    but in production or 'django-serving' mode, this handles client-side routes.
    """

    # Noise Reduction: Block obvious bot/script patterns
    path = request.path.lower()
    suspicious_patterns = [
        '.php',
        'cgi-bin',
        '../',
        '..\\',
        '/etc/passwd',
        '.env',
        '.git',
        'wp-admin',
        'wp-login',
        'setup.php',
    ]

    if any(pattern in path for pattern in suspicious_patterns):
        # Log the attempt
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        logger.warning(f"SUSPICIOUS BOT REQUEST BLOCKED: Path='{request.path}' IP='{ip}' UserAgent='{request.META.get('HTTP_USER_AGENT', 'Unknown')}'")
        return HttpResponseNotFound("Not Found")

    try:
        with open(settings.BASE_DIR / 'static/dist/index.html', 'r') as f:
            return HttpResponse(f.read())
    except FileNotFoundError:
        return HttpResponse(
            """
            React Build Not Found. 
            Please run 'npm run build' in the frontend directory.
            """,
            status=501
        )
