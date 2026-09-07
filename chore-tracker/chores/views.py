from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .identity import get_current_user, require_identity, set_current_user
from .models import Chore, Household, HouseholdMember, User, generate_join_code


def health(request):
    return HttpResponse("OK")


@require_identity
def index(request):
    # Minimal home/landing page at "/". Wrapped in the task 4 identity
    # guard, so a session with no active identity redirects to /identity/
    # instead of seeing links to views it can't use yet. This is
    # intentionally minimal — task 18 builds the full shared nav/base
    # template and should extend this same view rather than introduce a
    # competing landing page.
    return render(request, "chores/index.html")


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
                return redirect("chore_pool")
        else:
            error = _handle_create(request)
            if error is None:
                return redirect("chore_pool")

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


@require_identity
def switch_identity(request):
    # Lets a session switch among only the identities it has itself
    # created/joined/switched to (request.session["known_user_ids"], set
    # by set_current_user). Wrapped in the task 4 identity guard, so a
    # session with no active identity redirects to /identity/ instead of
    # rendering here.
    error = None

    if request.method == "POST":
        raw_user_id = request.POST.get("user_id", "")
        try:
            submitted_user_id = int(raw_user_id)
        except (TypeError, ValueError):
            submitted_user_id = None

        known_user_ids = request.session.get("known_user_ids", [])

        if submitted_user_id is None or submitted_user_id not in known_user_ids:
            error = "That identity is not available in this session."
        else:
            user = User.objects.filter(pk=submitted_user_id).first()
            if user is None:
                error = "That identity is not available in this session."
            else:
                set_current_user(request, user)
                return redirect("chore_pool")

    current_user = get_current_user(request)
    known_user_ids = request.session.get("known_user_ids", [])

    identities = []
    for user_id in known_user_ids:
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            continue
        membership = HouseholdMember.objects.filter(user=user).first()
        identities.append(
            {
                "user": user,
                "household": membership.household if membership else None,
                "is_current": current_user is not None and user.id == current_user.id,
            }
        )

    return render(
        request,
        "chores/switch_identity.html",
        {"identities": identities, "error": error},
    )


@require_identity
def chore_pool(request):
    # Read-only view of all open (unclaimed) chores for the active
    # household. Wrapped in the task 4 identity guard, so a session with
    # no active identity redirects to /identity/ instead of rendering
    # here. Each User row created by the create/join flows (tasks 5/6)
    # belongs to exactly one household, so this HouseholdMember lookup is
    # unambiguous.
    current_user = get_current_user(request)
    membership = HouseholdMember.objects.get(user=current_user)
    household = membership.household

    chores = Chore.objects.filter(household=household, status=Chore.STATUS_OPEN).order_by(
        "name", "id"
    )

    return render(request, "chores/chore_pool.html", {"chores": chores})


@require_identity
def claim_chore(request, chore_id):
    # Action endpoint: claim an open chore for the current session's active
    # identity. Wrapped in the task 4 identity guard, so a session with no
    # active identity redirects to /identity/ instead of running. Only POST
    # (or another mutating method) performs the claim; a GET returns 405.
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    current_user = get_current_user(request)
    membership = HouseholdMember.objects.get(user=current_user)
    household = membership.household

    # Household filter is part of the query itself, not a Python check
    # applied after fetching by id, so isolation holds structurally: a
    # chore id belonging to a different household is indistinguishable
    # from a nonexistent one (404).
    chore = get_object_or_404(Chore, id=chore_id, household=household)

    if chore.status != Chore.STATUS_OPEN:
        return JsonResponse({"error": "Chore is not open."}, status=409)

    chore.status = Chore.STATUS_CLAIMED
    chore.claimed_by = current_user
    chore.save()

    return JsonResponse({"status": "claimed"})


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
