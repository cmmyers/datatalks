from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .identity import set_current_user
from .models import Household, HouseholdMember, User, generate_join_code


def health(request):
    return HttpResponse("OK")


def choose_identity(request):
    # Redirect target for the task 4 identity guard. Extended here with the
    # "create a household" form (task 5); task 6 will add a "join an
    # existing household" form to this same view. This view must never be
    # wrapped in the identity guard itself, since it is the guard's own
    # redirect target — wrapping it would create a redirect loop.
    error = None

    if request.method == "POST":
        household_name = request.POST.get("household_name", "").strip()
        display_name = request.POST.get("display_name", "").strip()

        if not household_name or not display_name:
            error = "Household name and display name are both required."
        else:
            household = _create_household_with_retry(household_name)
            user = User.objects.create(name=display_name)
            HouseholdMember.objects.create(user=user, household=household)
            set_current_user(request, user)
            # Interim landing target: the chore pool (task 8) doesn't exist
            # yet, so redirect to the health-check URL as a stand-in. Task 8
            # should update this (and tasks 6/7/12's equivalent redirects) to
            # point at the real chore pool once it exists.
            return redirect("health")

    return render(request, "chores/choose_identity.html", {"error": error})


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
