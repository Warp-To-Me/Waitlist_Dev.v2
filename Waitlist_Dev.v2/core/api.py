from django.http import JsonResponse

def health_check(request):
    """
    A simple view to verify that the frontend can communicate with the backend.
    """
    return JsonResponse({'message': 'Django is running and reachable!'})