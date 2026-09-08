import itertools

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.db.models.functions import Lower
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .identity import get_current_user, require_identity, set_current_user
from .models import Chore, Household, HouseholdMember, User, WeeklyCompletion, generate_join_code
from .weeks import current_week_start


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
    request.session["show_new_household_banner"] = True
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

    show_new_household_banner = request.session.pop("show_new_household_banner", False)
    context = {"chores": chores, "show_new_household_banner": show_new_household_banner}
    if show_new_household_banner:
        context["new_household_join_code"] = household.join_code

    return render(request, "chores/chore_pool.html", context)


@require_identity
def my_claimed_chores(request):
    # Read-only view of chores the current session's active identity has
    # personally claimed but not yet completed, scoped to the active
    # household. Wrapped in the task 4 identity guard, so a session with no
    # active identity redirects to /identity/ instead of rendering here.
    # Resolves the active household the same way chore_pool/points_board/
    # history/household_settings do. Unlike task 8's chore pool (status
    # open, any claimant), this filters on both status=claimed and
    # claimed_by=current_user, so a chore claimed by a different member of
    # the same household is excluded, not just chores from another
    # household or another of this session's identities.
    current_user = get_current_user(request)
    membership = HouseholdMember.objects.get(user=current_user)
    household = membership.household

    chores = Chore.objects.filter(
        household=household, status=Chore.STATUS_CLAIMED, claimed_by=current_user
    ).order_by("name", "id")

    return render(request, "chores/my_claimed_chores.html", {"chores": chores})


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


@require_identity
def release_chore(request, chore_id):
    # Action endpoint: release a chore the current session's identity holds
    # a claim on, putting it back in the open pool. Wrapped in the task 4
    # identity guard, so a session with no active identity redirects to
    # /identity/ instead of running. Only POST (or another mutating method)
    # performs the release; a GET returns 405.
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

    if chore.status != Chore.STATUS_CLAIMED:
        return JsonResponse({"error": "Chore is not claimed."}, status=409)

    if chore.claimed_by_id != current_user.id:
        return JsonResponse({"error": "Chore is claimed by someone else."}, status=403)

    chore.status = Chore.STATUS_OPEN
    chore.claimed_by = None
    chore.save()

    return JsonResponse({"status": "open"})


@require_identity
def complete_chore(request, chore_id):
    # Action endpoint: mark a chore the current session's identity holds a
    # claim on as done, awarding its points for the current week and
    # resetting it back into the open pool (chores are recurring — this
    # never deletes it). Wrapped in the task 4 identity guard, so a session
    # with no active identity redirects to /identity/ instead of running.
    # Only POST (or another mutating method) performs the completion; a GET
    # returns 405.
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

    if chore.status != Chore.STATUS_CLAIMED:
        return JsonResponse({"error": "Chore is not claimed."}, status=409)

    if chore.claimed_by_id != current_user.id:
        return JsonResponse({"error": "Chore is claimed by someone else."}, status=403)

    points_awarded = chore.points

    WeeklyCompletion.objects.create(
        chore=chore,
        household=household,
        user=current_user,
        points_awarded=points_awarded,
        week_start_date=current_week_start(),
    )

    chore.status = Chore.STATUS_OPEN
    chore.claimed_by = None
    chore.save()

    return JsonResponse({"status": "completed", "points_awarded": points_awarded})


@require_identity
def points_board(request):
    # Read-only view of each household member's point total for the
    # current week. Wrapped in the task 4 identity guard, so a session
    # with no active identity redirects to /identity/ instead of
    # rendering here. Resolves the active household the same way
    # chore_pool/claim_chore/release_chore/complete_chore do.
    current_user = get_current_user(request)
    membership = HouseholdMember.objects.get(user=current_user)
    household = membership.household

    week_start = current_week_start()

    totals_by_user_id = {
        row["user_id"]: row["total"]
        for row in (
            WeeklyCompletion.objects.filter(household=household, week_start_date=week_start)
            .values("user_id")
            .annotate(total=Sum("points_awarded"))
        )
    }

    # Every member of the active household appears on the board, even
    # with zero completions this week (falling back to 0 below) — the
    # point of the board is to surface "did nothing", not hide it.
    members = HouseholdMember.objects.filter(household=household).select_related("user")

    board = sorted(
        (
            {"user": member.user, "total": totals_by_user_id.get(member.user_id, 0)}
            for member in members
        ),
        # Descending by total, ties broken alphabetically by name,
        # case-insensitively (a naive case-sensitive sort would put
        # "Bob" before "adam", which isn't true alphabetical order).
        key=lambda entry: (-entry["total"], entry["user"].name.lower()),
    )

    return render(request, "chores/points_board.html", {"board": board})


HISTORY_WEEKS_LIMIT = 12
# Task 22: the history view (below) intentionally caps how many distinct
# week groups it renders, so a household's page doesn't grow unbounded as
# its WeeklyCompletion log accumulates over months of use. A fixed number of
# most-recent weeks (rather than ?page=/"load more" pagination) is enough
# for this local homework project. Module-level so it's a single source of
# truth tests can import instead of a magic number re-typed in assertions.


@require_identity
def history(request):
    # Read-only log of a household's completed chores, grouped by week, most
    # recent week first. Wrapped in the task 4 identity guard, so a session
    # with no active identity redirects to /identity/ instead of rendering
    # here. Resolves the active household the same way chore_pool/points_board
    # do. Every week with at least one completion is shown, including the
    # week-in-progress (current_week_start()) — nothing distinguishes a
    # "past" week from the current one in the data model, so this view must
    # not filter it out. Capped to the HISTORY_WEEKS_LIMIT most recent
    # distinct week_start_dates (task 22) so the page doesn't grow unbounded;
    # the cap is computed within this same household-scoped queryset so one
    # household's history never affects how many weeks another renders.
    current_user = get_current_user(request)
    membership = HouseholdMember.objects.get(user=current_user)
    household = membership.household

    recent_week_starts = (
        WeeklyCompletion.objects.filter(household=household)
        .values_list("week_start_date", flat=True)
        .distinct()
        .order_by("-week_start_date")[:HISTORY_WEEKS_LIMIT]
    )

    completions = (
        WeeklyCompletion.objects.filter(household=household, week_start_date__in=recent_week_starts)
        .select_related("user", "chore")
        .order_by("-week_start_date", "-completed_at", "-id")
    )

    # completions is already ordered by week_start_date descending (and, within
    # a week, completed_at/id descending), so groupby's "consecutive runs
    # share a key" behavior groups it correctly without a second query or an
    # extra sort. Each group's total is computed from these same fetched
    # rows, not a second query.
    weeks = []
    for week_start_date, group in itertools.groupby(completions, key=lambda c: c.week_start_date):
        week_completions = list(group)
        weeks.append(
            {
                "week_start_date": week_start_date,
                "completions": week_completions,
                "total": sum(c.points_awarded for c in week_completions),
            }
        )

    return render(request, "chores/history.html", {"weeks": weeks})


def _parse_chore_form(post_data):
    """Validate and parse the add/edit chore form (task 16).

    Returns (name, room, points, error). On invalid input, name/room/points
    are all None and error is a user-facing message; on valid input, error
    is None. Validates before ever touching the model layer — Chore.save()
    calls full_clean() (task 3), so handing it bad data directly would
    surface as an unhandled ValidationError rather than a friendly
    re-rendered form.
    """
    name = post_data.get("name", "").strip()
    room = post_data.get("room", "").strip()
    raw_points = post_data.get("points", "")

    if not name or not room:
        return None, None, None, "Name and room are both required."

    try:
        # int() rejects non-numeric strings (e.g. "abc") and non-integer
        # numeric strings (e.g. "3.5") alike, matching the task's
        # requirement that both count as invalid input.
        points = int(raw_points)
    except (TypeError, ValueError):
        return None, None, None, "Points must be a whole number."

    if points <= 0:
        return None, None, None, "Points must be a positive number."

    return name, room, points, None


@require_identity
def household_settings(request):
    # Lets members add new chores to the active household's pool and see
    # every existing chore (any status) with a link to edit it. Wrapped in
    # the task 4 identity guard, so a session with no active identity
    # redirects to /identity/ instead of rendering or processing the form.
    # Resolves the active household the same way chore_pool/points_board/
    # history do. Follows the choose_identity form-handling pattern (tasks
    # 5/6): GET renders, POST processes, a rejected submission re-renders
    # with an error and creates no row rather than raising a server error.
    current_user = get_current_user(request)
    membership = HouseholdMember.objects.get(user=current_user)
    household = membership.household

    error = None

    if request.method == "POST":
        name, room, points, error = _parse_chore_form(request.POST)
        if error is None:
            # status/claimed_by take their model defaults (open/unset) — a
            # chore created here is never pre-claimed.
            Chore.objects.create(household=household, name=name, room=room, points=points)
            return redirect("household_settings")

    # Unlike task 8's chore pool, this page manages the whole pool, so a
    # claimed chore must still show up here to be editable — no status
    # filter, only the household scope. Same deterministic ordering as
    # task 8.
    chores = Chore.objects.filter(household=household).order_by("name", "id")

    # Task 17: read-only join-code and member-list sections, scoped to the
    # active household. Member order is deterministic — ascending
    # alphabetical by name, case-insensitively — mirroring task 13's
    # points-board ordering. User.name is already unique within a household
    # case-insensitively (task 2), so no further tiebreaker is needed.
    members = (
        HouseholdMember.objects.filter(household=household)
        .select_related("user")
        .order_by(Lower("user__name"))
    )

    return render(
        request,
        "chores/household_settings.html",
        {"chores": chores, "error": error, "household": household, "members": members},
    )


@require_identity
def chore_edit(request, chore_id):
    # Lets a member edit an existing chore's name/room/points. Wrapped in
    # the task 4 identity guard, so a session with no active identity
    # redirects to /identity/ instead of rendering or processing the form.
    current_user = get_current_user(request)
    membership = HouseholdMember.objects.get(user=current_user)
    household = membership.household

    # Household filter is part of the query itself, not a Python check
    # applied after fetching by id, so isolation holds structurally on both
    # GET and POST: a chore id belonging to a different household is
    # indistinguishable from a nonexistent one (404) either way.
    chore = get_object_or_404(Chore, id=chore_id, household=household)

    error = None

    if request.method == "POST":
        name, room, points, error = _parse_chore_form(request.POST)
        if error is None:
            # Only name/room/points are touched — status/claimed_by are
            # owned exclusively by the claim/release/complete actions
            # (tasks 10-12), and any WeeklyCompletion.points_awarded rows
            # already recorded against this chore keep their own stored
            # value (task 3) regardless of this edit.
            chore.name = name
            chore.room = room
            chore.points = points
            chore.save()
            return redirect("household_settings")

    return render(request, "chores/chore_edit.html", {"chore": chore, "error": error})


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
