from functools import wraps

from django.shortcuts import redirect

from .models import User


def get_current_user(request):
    """Return the User this session is currently acting as, or None.

    If the session references a User that no longer exists, the stale
    session key is removed so subsequent calls don't keep trying to
    resolve a dangling id.
    """
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        del request.session["user_id"]
        return None


def set_current_user(request, user):
    """Store the given User as this session's active identity.

    Also records user.id in request.session["known_user_ids"] (creating the
    list if absent, never adding a duplicate) so a session can later switch
    back to any identity it has ever created/joined/switched to (task 7).
    """
    request.session["user_id"] = user.id

    known_user_ids = request.session.get("known_user_ids", [])
    if user.id not in known_user_ids:
        known_user_ids.append(user.id)
    request.session["known_user_ids"] = known_user_ids


def require_identity(view_func):
    """Decorator that redirects to choose_identity when no identity is set."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if get_current_user(request) is None:
            return redirect("choose_identity")
        return view_func(request, *args, **kwargs)

    return wrapped
