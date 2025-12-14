from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse

def frontend_app(request):
    """
    Serves the compiled React app (index.html).
    In development, this might not be hit if Vite dev server is used,
    but in production or 'django-serving' mode, this handles client-side routes.
    """
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
