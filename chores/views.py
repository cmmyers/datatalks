from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .identity import set_current_user
from .models import Household, HouseholdMember, User, generate_join_code


def health(request):
    return HttpResponse("OK")


def choose_identity(request):
    # Redirect target for the task 4 identity guard. Extended in task 5 with
    # a "create a household" form and in task 6 with a "join an existing
    # household" form, both posted to this same view/URL. A hidden `action`
    # field on each form ("create" or "join") tells POST which handler to
    # run; missing/unrecognized action defaults to "create" so older
    # submissions of the create form (no action field) keep working. This
    # view must never be wrapped in the identity guard itself, since it is
    # the guard's own redirect target — wrapping it would create a redirect
    # loop.
    error = None

    if request.method == "POST":
        action = request.POST.get("action", "create")

        if action == "join":
            error = _handle_join(request)
            if error is None:
                return redirect("health")
        else:
            error = _handle_create(request)
            if error is None:
                return redirect("health")

    return render(request, "chores/choose_identity.html", {"error": error})


def _handle_create(request):
    """Process the create-household form. Returns an error string, or None on success."""
    household_name = request.POST.get("household_name", "").strip()
    display_name = request.POST.get("display_name", "").strip()

    if not household_name or not display_name:
        return "Household name and display name are both required."

    household = _create_household_with_retry(household_name)
    user = User.objects.create(name=display_name)
    HouseholdMember.objects.create(user=user, household=household)
    set_current_user(request, user)
    # Interim landing target: the chore pool (task 8) doesn't exist
    # yet, so redirect to the health-check URL as a stand-in. Task 8
    # should update this (and tasks 6/7/12's equivalent redirects) to
    # point at the real chore pool once it exists.
    return None


def _handle_join(request):
    """Process the join-household form. Returns an error string, or None on success."""
    join_code = request.POST.get("join_code", "").strip()
    display_name = request.POST.get("display_name", "").strip()

    if not join_code or not display_name:
        return "Join code and display name are both required."

    household = Household.objects.filter(join_code=join_code).first()
    if household is None:
        return "No household found for that join code."

    conflict = HouseholdMember.objects.filter(
        household=household, user__name__iexact=display_name
    ).exists()
    if conflict:
        return f"A member named '{display_name}' already exists in that household."

    user = User.objects.create(name=display_name)
    HouseholdMember.objects.create(user=user, household=household)

    set_current_user(request, user)
    return None


def _create_household_with_retry(name):
    """Create a Household, regenerating join_code on a collision.

    Household.join_code is DB-level unique but Household doesn't
    pre-validate uniqueness the way other models here do, so a colliding
    code surfaces as IntegrityError on save. Wrapping this in
    transaction.atomic() ensures a caught IntegrityError doesn't leave the
    surrounding transaction unusable (important under TestCase, where each
    test already runs inside its own transaction).
    """
    while True:
        try:
            with transaction.atomic():
                return Household.objects.create(name=name, join_code=generate_join_code())
        except IntegrityError:
            continue
