from django.http import HttpResponse


def health(request):
    return HttpResponse("OK")


def choose_identity(request):
    # Placeholder for the identity guard's redirect target. Tasks 5 and 6
    # extend this view with the create/join household forms. This view must
    # never be wrapped in the identity guard itself, since it is the guard's
    # own redirect target.
    return HttpResponse("OK")
