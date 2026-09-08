# Backlog

Tasks for building the Household Chore Tracker described in
[plan.md](plan.md). Each task is scoped to be finishable in one sitting and
handed off without needing to read the others — background/spec references
are repeated where useful rather than assumed.

## 1. Project setup with an empty passing test — Completed 2026-09-07 13:00 PDT
Goal: Get a runnable Django project skeleton with one green test.
Description: Confirm/initialize the Django project (`choretracker`) and a
`chores` app, wire the app into `INSTALLED_APPS`, and add a placeholder URL
with a minimal view (e.g. returning a 200 with a plain "OK" response). Add a
single test that uses the Django test client to hit that URL and asserts a
200 response, so `python manage.py test` passes. No models or business logic
yet — this task just proves the project boots, routes a request, and the
test runner works.

## 2. `User`, `Household`, and `HouseholdMember` models — Completed 2026-09-07 13:08 PDT
Goal: Model people, households, and membership between them.
Description: Add a `User` model (just a `name` field — no password/email,
per spec), a `Household` model (`name`, unique `join_code`), and a
`HouseholdMember` join model linking the two. Enforce that a user's `name` is
unique within a household (case-insensitive) at the membership level, since
names are not unique globally. Include migrations and model-level tests
(uniqueness constraint, basic creation).

## 3. `Chore` and `WeeklyCompletion` models — Completed 2026-09-07 13:35 PDT
Goal: Model chores and the log of completions that drives points/history.
Description: Add a `Chore` model (`household` FK, `name`, `room`, `points`
as a positive integer — must be greater than zero, enforced with a validator
such as `MinValueValidator(1)`, not just `PositiveIntegerField` which alone
would still permit `0` — `status` restricted to `open`/`claimed` via model
`choices` and defaulting to `open` on creation, nullable/optional
`claimed_by` FK to `User`, `null=True`, defaulting to unset) and a
`WeeklyCompletion` model (`chore` FK, `household` FK, `user` FK,
`points_awarded` as a positive integer with the same `>0` validation,
`week_start_date`, `completed_at` timestamp defaulting to creation time).
`status` only ever tracks open/claimed at the model level — "completed" is
not a stored status; completing a chore is represented by writing a
`WeeklyCompletion` row and resetting the chore back to `open` (that reset
behavior is built in task 12, not here).

Set explicit `on_delete` behavior rather than leaving it to accident:
`WeeklyCompletion.chore`, `.household`, and `.user` should use
`on_delete=models.PROTECT`, since `WeeklyCompletion` is meant to be
append-only history — the ORM must refuse to delete a `Chore`/`Household`/
`User` that has completions attached rather than silently cascading them
away. `Chore.claimed_by` should use `on_delete=models.SET_NULL` so removing
a `User` clears a claim instead of deleting the `Chore` itself.

Note that `WeeklyCompletion.household` is redundant with
`WeeklyCompletion.chore.household` by design (it's denormalized for simpler
querying later); a completion's `household` must always match its `chore`'s
household — enforce this with model-level validation (e.g. a `clean()`
override raising `ValidationError` on mismatch), not just as a convention
that happens to hold when application code behaves. `points_awarded` is its
own stored value, independent of `Chore.points`, so that editing a chore's
point value later (task 16) never rewrites already-recorded history.

Include migrations and tests asserting: a newly created `Chore` defaults to
`status="open"` with no `claimed_by`; creating a `Chore` with `points=0` (or
negative) fails validation, and likewise for `WeeklyCompletion.points_awarded`;
creating a `Chore` with a `status` outside `open`/`claimed` fails validation;
a `WeeklyCompletion` can be created with all fields and read back with the
same values; a `WeeklyCompletion` created with a `household` that doesn't
match its `chore`'s `household` is rejected; deleting a `Chore` (or
`Household`/`User`) that has an associated `WeeklyCompletion` raises
`ProtectedError` instead of cascading; and changing a `Chore`'s `points`
after a `WeeklyCompletion` referencing it already exists leaves that
completion's `points_awarded` unchanged.

## 4. Session-based "acting as" identity — Completed 2026-09-07 13:45 PDT
Goal: Let a browser session remember which `User` it's currently acting as.
Description: Add a small identity helper module (e.g. `chores/identity.py`)
with two functions: `get_current_user(request)`, which reads
`request.session["user_id"]` and returns the matching `User` instance, or
`None` if the key is unset **or** if it references a `User` that no longer
exists (clear the stale session key in that case rather than letting
`User.DoesNotExist` propagate); and `set_current_user(request, user)`, which
stores `user.id` under `request.session["user_id"]`. No
`django.contrib.auth`/passwords are involved.

Add a guard (e.g. a view decorator or class-based mixin) that wraps a view
and, when `get_current_user(request)` returns `None`, redirects (302)
instead of running the view. Since the real "who are you" prompt is built in
tasks 5 and 6, add a minimal placeholder URL/view now purely as the guard's
redirect target — e.g. a URL path `/identity/` named `choose_identity` that
renders a stub page (any 200 response is fine); tasks 5 and 6 should extend
or replace this same view rather than introduce a competing one. This
placeholder view must not itself be wrapped in the guard — since it's the
guard's own redirect target, guarding it would create a redirect loop for a
session with no identity — so it must return 200 on GET regardless of
whether a session identity is currently set. This task is plumbing only —
no identity-switching UI (that's task 7). No other view in the app is
wrapped in the guard yet (task 8 builds the first real one), so test the
guard itself against a minimal dummy view defined for test purposes only
(e.g. inline in the test module via `RequestFactory`, or a view wrapped in
the guard directly within the test file) rather than adding a throwaway
production URL to `chores/urls.py`.

Include tests asserting: setting the session identity via `set_current_user`
and reading it back via `get_current_user` returns the same `User`; a view
wrapped in the guard redirects to the `choose_identity` URL when the session
has no `user_id`; the same guarded view returns 200 (runs normally) once an
identity is set on the session; a session holding a `user_id` for a `User`
that has since been deleted is treated the same as no identity set —
`get_current_user` returns `None`, the stale `user_id` key is actually
removed from `request.session` (not merely ignored on this call), and the
guarded view redirects rather than raising an error; and GET `/identity/`
itself returns 200 both when the session has no identity set and when one
is already set, confirming the placeholder view is reachable regardless of
guard state rather than redirecting to itself.

## 5. Create a household — Completed 2026-09-07 13:52 PDT
Goal: Let a user start a new household with a shareable join code.
Description: Extend the `choose_identity` view/URL (`/identity/`, added in
task 4 as the identity guard's redirect target) with a "create a household"
form, rather than introducing a separate page — GET renders the empty form,
POST processes the submission. A person enters a household name and their
own display name; both are required and rejected (re-render the form with an
error, no records created) if blank or whitespace-only after stripping. On a
valid submission, save the *stripped* values (not the raw submitted strings)
as `Household.name` and `User.name`, so surrounding whitespace never gets
baked into a stored name — this matters because task 6's join flow later
compares a new submission's stripped name against these stored names
case-insensitively, and a stored name with leftover padding would silently
break that comparison. Create a `Household` with a generated `join_code`
(e.g. a short random alphanumeric string — regenerate on collision rather
than trusting randomness alone; the DB-level `unique=True` on `join_code` is
the actual guarantee, but `Household` does not override `save()` to
pre-validate uniqueness the way `Chore`/`WeeklyCompletion`/`HouseholdMember`
do, so a colliding `join_code` surfaces as `IntegrityError` on save, not a
friendlier `ValidationError` — the view must catch this and retry with a
freshly generated code rather than letting it propagate to the user; wrap
the create-and-retry logic in `django.db.transaction.atomic()` so a caught
`IntegrityError` doesn't leave the surrounding transaction unusable, which
matters under Django's `TestCase`, where each test already runs inside its
own transaction), a matching `User` row holding the display name, and a
`HouseholdMember` row linking that user to that household, then call
`set_current_user` (task 4) to make the new `User` the session's active
identity, and redirect (302) to a concrete landing target that actually
exists today — since the chore pool (task 8) hasn't been built yet, redirect
to the existing health-check URL (name `"health"`, from task 1) as an
interim stand-in rather than reversing a not-yet-existent `chore_pool` URL
name, which would raise `NoReverseMatch`; task 8 should update this redirect
(and tasks 6/7/13's equivalent placeholder redirects) to point at the real
chore pool once it exists — rather than re-rendering the form. Because this
always creates a brand-new household, there is no existing member to
collide names with — the case-insensitive within-household name uniqueness
check only matters when *joining* an existing household (task 6), not here.
This view must not itself be wrapped in the task 4 identity guard, since
it's the guard's own redirect target — wrapping it would create a redirect
loop for a session with no identity yet.

Include tests asserting: submitting valid household/display names creates
exactly one `Household`, one `User`, and one `HouseholdMember` linking that
user to that household; the created `Household.join_code` is non-empty and
matches whatever format the implementation defines; creating many households
in a row never produces a duplicate `join_code`; submitting a household name
or display name with leading/trailing whitespace around otherwise-valid
content stores the stripped value on `Household.name`/`User.name`, not the
raw padded string; forcing a `join_code` collision (e.g. by monkeypatching
the code-generation function so its first call returns an already-used code
and its second call returns a fresh one) still results in exactly one new
`Household` being created with a unique `join_code`, rather than an
`IntegrityError` propagating to the caller; after creation,
`get_current_user(request)` returns the newly created `User` for that
session; a successful submission responds with a 302 redirect to the
`health` URL (today's interim landing target, per above) rather than
re-rendering the form; and submitting a blank (or whitespace-only) household
name or display name re-renders the form with an error and creates no
`Household`, `User`, or `HouseholdMember` rows.

## 6. Join a household by code — Completed 2026-09-07 14:05 PDT
Goal: Let a new person join an existing household using its join code.
Description: Extend the same `choose_identity` view (`/identity/`, added in
task 4 as the identity guard's redirect target and extended in task 5 with
the "create a household" form) with a second form for joining an existing
household, rather than introducing a separate page/URL — task 4 calls for
tasks 5 and 6 to extend or replace this one view, not add competing ones.
Both forms should be reachable from a GET to `/identity/`; a POST must be
able to tell which form was submitted (e.g. distinct field names/a hidden
action field) and route to the matching handler. A person enters a join code
and their own display name; both are required and rejected (re-render the
form with an error, no records created) if blank or whitespace-only after
stripping.

Match the submitted code against `Household.join_code` after stripping
surrounding whitespace; matching is case-sensitive (join codes are opaque
generated tokens, unlike display names, which is where case-insensitive
matching applies). If no household has a matching `join_code`, re-render the
form with an error and create no records. If the code matches, enforce that
the stripped display name is not already used by an existing member of
*that* household, case-insensitively (e.g. an existing member "Alice" blocks
a new submission of "aLICE" or " alice "); this check is scoped to the
target household only — the same name already belonging to a member of a
*different* household must not block the join, since names are unique per
household, not globally. On a valid submission, create a `User` row holding
the given display name and a `HouseholdMember` row linking it to the
matched (not newly created) `Household`, call `set_current_user` (task 4) to
make the new `User` the session's active identity, and redirect (302) to the
chore pool (or whatever the current default landing view is) rather than
re-rendering the form. Like the create-household form, this view must not
itself be wrapped in the task 4 identity guard, since it's the guard's own
redirect target — wrapping it would create a redirect loop for a session
with no identity yet.

Include tests asserting: submitting a valid join code and a new display name
creates exactly one `User` and one `HouseholdMember` linking that user to
the household the code belongs to, and creates no new `Household`; after
joining, `get_current_user(request)` returns the newly created `User` for
that session; a successful submission responds with a redirect rather than
re-rendering the form; submitting a join code that matches no `Household`
re-renders the form with an error and creates no `User` or
`HouseholdMember` row; submitting a blank (or whitespace-only) join code or
display name re-renders the form with an error and creates no rows;
submitting a display name that already belongs to another member of the
target household, case-insensitively, re-renders the form with an error and
creates no rows; and submitting a display name that already belongs to a
member of a *different* household succeeds and creates the expected `User`
and `HouseholdMember` rows (proving name uniqueness is per-household, not
global).

## 7. Household switcher / switch person — Completed 2026-09-07 14:20 PDT
Goal: Let a person see and switch between all households (and identities)
this browser session has established, and let one browser demo multiple
people by switching among only those identities — never any arbitrary user
in the database.
Description: A session only ever tracks one *active* identity
(`request.session["user_id"]`, per task 4), so switching requires the
session to also remember every identity it has *ever* acted as. Extend the
`set_current_user(request, user)` helper from task 4 (the single choke point
already called by task 5's create-household flow, task 6's join flow, and
this task's own switch action) so that, in addition to setting
`request.session["user_id"]`, it appends `user.id` to a list stored under a
separate session key, e.g. `request.session["known_user_ids"]`, creating the
list if absent and never adding a duplicate. This list is what makes a
person's other households/identities discoverable later in the same
browser — it must never be populated from, or expanded to include, `User`
rows this session didn't itself create/join/switch to.

Build a new view (e.g. `/switch/` named `switch_identity`), wrapped in the
task 4 identity guard (a session with no active identity has nothing to
switch from, so it should redirect to `/identity/` like any other guarded
view). On GET, render one row per id in `known_user_ids` that still resolves
to an existing `User` — drop ids that no longer resolve (a `User` deleted
since being recorded) from what's displayed, mirroring the stale-reference
handling `get_current_user` already does, rather than erroring — showing
that user's display name and the `Household` they belong to (via
`HouseholdMember`), with a form control to switch to it, and a visual
indicator on whichever row matches the currently active `user_id`. A session
whose `known_user_ids` contains only the current identity still renders
successfully (a list of one, no other options), not an error.

On POST, accept a submitted `user_id`. Session-stored ids in `known_user_ids`
are ints, but Django POST data arrives as strings, so parse the submitted
value to an int before comparing; treat a non-numeric submission the same as
"not present" (reject, don't raise). Reject it — re-render the list with an
error and make no session change — if that `user_id` (as an int) is not
present in the session's own `known_user_ids`; this is the enforcement point
that stops a crafted request from switching a session into somebody else's
household without ever having gone through a join code, which would break
household isolation. If the `user_id` is present and still resolves to an
existing `User`, call `set_current_user(request, user)` to make it the
active identity and redirect (302) to a concrete landing target that
actually exists today — since the chore pool (task 8) hasn't been built yet,
redirect to the existing health-check URL (name `"health"`, per tasks 5/6's
same interim stand-in) rather than reversing a not-yet-existent `chore_pool`
URL name, which would raise `NoReverseMatch`; task 8 should update this
redirect once the chore pool exists.

Include tests asserting: after creating a household (task 5) and then, in
the same session, joining a second household (task 6), `known_user_ids`
contains both identities and GET `/switch/` lists both households; switching
to the second identity makes `get_current_user` return that user and that
user's `HouseholdMember` row resolves to the second household (proving the
active identity's household scope changed, without depending on the
not-yet-built chore pool view); switching back to the first identity makes
`get_current_user` return the first user again with their `HouseholdMember`
row resolving back to the first household; switching to an identity already
present in `known_user_ids` a second time does not append a duplicate entry
(the list's length and contents are unchanged); submitting a `user_id`
belonging to a `User` from an entirely separate session/household (never
joined or created by this session) is rejected — `get_current_user` is
unchanged afterward and no redirect occurs; submitting a non-numeric
`user_id` (e.g. a string that isn't a valid id) is rejected the same way,
without raising a server error; a session with exactly one known identity
still returns 200 for GET `/switch/`; and a `known_user_ids` entry whose
`User` has since been deleted is omitted from the rendered list instead of
raising an error.

## 8. Chore pool view — Completed 2026-09-07 14:35 PDT
Goal: Show all open (unclaimed) chores for the active household.
Description: Build a read-only view (e.g. URL `/chores/` named `chore_pool`)
wrapped in the task 4 identity guard, so a request with no active session
identity redirects (302) to `/identity/` instead of rendering the pool.
Assume the `Chore` model (task 3) and the session identity helpers/guard
(task 4) already exist. For a signed-in session, resolve the active
household via the current user's `HouseholdMember` row — each `User` row
created by the create/join flows (tasks 5/6) belongs to exactly one
household, so this lookup is unambiguous — then list `Chore` rows with
`status="open"` for that household only, showing each chore's name, room,
and point value. A household with zero open chores still renders 200 with
an empty list/message rather than erroring. Order the results consistently
by name (e.g. `order_by("name", "id")`) so a test can assert on exact list
contents and order rather than an unordered set — `Chore.name` has no
uniqueness constraint (unlike `User.name`), so two open chores in the same
household can share a name; break ties by `id` (creation order) so the
ordering stays deterministic even then.

This task also retires the three interim `redirect("health")` stand-ins left
by tasks 5, 6, and 7 for exactly this reason — each of those tasks'
descriptions says outright that task 8 should update its redirect once the
real chore pool exists. Update all three redirect targets to
`redirect("chore_pool")` now that the URL exists: the create-household
handler (`_handle_create`, task 5), the join-household handler
(`_handle_join`, task 6), and `switch_identity`'s POST success path (task 7).
Update those three tasks' existing tests that assert a redirect to the
`health` URL so they instead assert a redirect to `chore_pool` — this task
isn't complete until no view redirects to `health` as a stand-in landing
target anymore (the `health` URL itself, task 1's placeholder, is untouched
and can remain for its own health-check purpose).

Include tests asserting: an open chore belonging to the active household
appears in the rendered list; a chore belonging to a different household is
excluded even if it also has `status="open"`; a chore in the active
household with `status="claimed"` is excluded; a household with no open
chores renders 200 with an empty list rather than an error; a request with
no active session identity redirects to `/identity/` rather than rendering
the pool; two open chores in the active household sharing the same `name`
still render in a deterministic order (e.g. by ascending `id`) across
repeated requests; and, updated in this task, that creating a household
(task 5), joining a household (task 6), and switching identity (task 7)
each redirect to `chore_pool` rather than `health` on success.

## 9. Home page with navigation at "/" — Completed 2026-09-07 14:50 PDT
Goal: Give the app a real landing page at the root URL with links to what's
built so far, instead of the root just being the task 1 health-check stub.
Description: Move the task 1 health-check view off the root path — keep it
reachable at `/health/` under the same URL name `"health"` (so anything
holding a reference to `reverse("health")` keeps working; only the *path*
changes, not the name) — and add a new view at the root path (`""`), named
`index`, wrapped in the task 4 `require_identity` guard, so a session with no
active identity is redirected to `/identity/` instead of seeing a nav page
full of links to views it can't use yet, consistent with every other guarded
view (tasks 7, 8). For a signed-in session, `index` renders a minimal page
linking to the chore pool (`/chores/`, task 8) and the household switcher
(`/switch/`, task 7) — the only two guarded, navigable views that exist as of
this task.

This is intentionally minimal, not the app's final navigation: task 18
(formerly task 17, before this task's insertion) later builds a full base
template with shared nav across every view — including points board,
history, and settings, once those exist — plus real shared CSS. This task
exists so there's something clickable to land on today rather than waiting
for task 18's full treatment; task 18 should extend/restyle this same
`index`/root page as part of wiring the shared base template, rather than
introduce a competing landing page.

Because the root path's behavior changes (it's no longer an unguarded 200
"OK" for every request), update task 1's existing health-check test to hit
`/health/` instead of `""`. Do not change any existing redirect target
elsewhere in the app — the create-household, join-household, and
switch-identity flows still redirect to `chore_pool` on success, per task 8;
`index` is a separate, additional entry point for visiting `/` directly, not
a new landing target those flows need to point at instead.

Include tests asserting: GET `/health/` still returns 200 (the relocated
health check); GET `""` (root) with no active session identity redirects
(302) to `/identity/`, mirroring every other guarded view; GET `""` with an
active session identity returns 200 and the rendered page contains links to
`/chores/` and `/switch/` (assert on those URLs appearing in the response
content, not just a bare 200 status); and visiting `""` does not itself
mutate session state (e.g. does not add to `known_user_ids` or change the
active identity) — it's read-only navigation, not an identity-changing
action.

## 10. Claim a chore — Completed 2026-09-07 15:05 PDT
Goal: Let the acting user claim an open chore.
Description: Build an action endpoint (e.g. POST `/chores/<id>/claim/`,
named `claim_chore`) wrapped in the task 4 identity guard, so a request with
no active session identity redirects (302) to `/identity/` rather than
running. Resolve the active household via the current user's
`HouseholdMember` row (same lookup as task 8). Look up the target `Chore`
with a single query filtered by both id and household — e.g.
`get_object_or_404(Chore, id=chore_id, household=household)` — rather than
fetching by id alone and checking `chore.household == household` afterward
in Python; the household filter must be enforced by the query itself so
isolation holds structurally, not merely as an observed side effect of code
that happens to check it today. A chore id belonging to a different
household must be treated as not found (404), not claimed, even if it is
`open`, so household isolation holds against a guessed/crafted id. If the
chore exists in the active household and its `status` is `open`, set `status="claimed"`
and `claimed_by` to the current session user, and return a 200 with a JSON
body of exactly `{"status": "claimed"}` — this is the first view in the app
to return JSON (no existing view in `chores/views.py` does yet, and
`_docs/plan.md` doesn't mandate a specific shape beyond "JSON for the
fetch-driven interactions"), and tasks 11 (release) and 12 (complete) are
described as following this same pattern, so fixing a concrete, testable
shape here — rather than leaving it as a loose example — is what keeps all
three consistent. If the chore is not `open` (already `claimed` by anyone,
including the same user retrying), reject the claim — leave the chore
unchanged and return a 409 with a JSON body containing an `"error"` key
(the exact message text is not prescribed and need not be asserted by
tests) rather than silently succeeding or raising a server error. Only
accept POST (or another mutating method) — a GET must not perform the
claim, per the spec's `fetch`-backed JSON convention for dynamic
interactions; reject non-POST requests with 405 rather than allowing state
changes via GET.

The request needs no body/payload beyond what's already in the URL and the
session — the chore id comes from the URL path and the acting user from
`get_current_user(request)`, so a bare POST with an empty body is
sufficient and the view must not require or parse any POST data fields.
Like every other POST view in this app, this endpoint is protected by
Django's `CsrfViewMiddleware` (already active in `settings.py`) and must
not be marked `csrf_exempt`; Django's test client satisfies this
automatically for the tests below (`enforce_csrf_checks` defaults to
`False`), so no special test setup is needed here — a real browser
`fetch()` call will need to send the CSRF token itself, which is a
frontend-wiring concern for whichever later task first adds a clickable
claim button to a template — no task currently on the backlog owns that
wiring explicitly, since tasks 10-12 build the JSON endpoints themselves
and the template tasks (16, 18) don't mention hooking buttons up to them;
worth flagging to the user as a possible backlog gap rather than silently
assuming it's covered.

Include tests asserting: POSTing to claim an open chore in the active
household with an empty body sets its `status` to `claimed` and
`claimed_by` to the current user, confirmed by re-fetching the `Chore` from
the DB (no payload beyond the URL/session is required), and the response
body is exactly `{"status": "claimed"}` with a 200; claiming a chore that is
already `claimed` (by any user, including the requester) is rejected — the
response is 409 with a JSON body containing an `"error"` key, and the
chore's `status`/`claimed_by` are unchanged; claiming a chore id that
belongs to a different household returns 404 and leaves that chore
unchanged, even if it is `open`; claiming a nonexistent chore id returns
404; a GET to the claim endpoint does not change the chore's `status` and
returns a non-2xx (405) response; and a request with no active session
identity redirects to `/identity/` rather than performing the claim.

## 11. Release a claimed chore — Completed 2026-09-07
Goal: Let the claiming user put a chore back into the open pool.
Description: Build an action endpoint (e.g. POST `/chores/<id>/release/`,
named `release_chore`) wrapped in the task 4 identity guard, so a request
with no active session identity redirects (302) to `/identity/` rather than
running. Resolve the active household via the current user's
`HouseholdMember` row (same lookup as tasks 8 and 10). Look up the target
`Chore` scoped to that household — a chore id belonging to a different
household must be treated as not found (404), not released, even if it is
`claimed`, so household isolation holds against a guessed/crafted id; a
nonexistent chore id likewise returns 404.

If the chore exists in the active household, its `status` is `claimed`, and
`claimed_by` equals the current session user, set `status="open"` and
`claimed_by=None`, and return a JSON success response (e.g.
`{"status": "open"}`) with a 200. If the chore is `claimed` by a *different*
user, reject the release — leave the chore unchanged and return a JSON error
response with 403 (the requester doesn't hold this claim). If the chore is
already `open` (not claimed by anyone), reject the release too — leave it
unchanged and return a JSON error response with 409 (nothing to release),
matching task 10's use of 409 for "not in the expected state" rather than
treating it as a permissions problem. Only accept POST (or another mutating
method) — a GET must not perform the release, per the spec's `fetch`-backed
JSON convention for dynamic interactions; reject non-POST requests with 405
rather than allowing state changes via GET.

Include tests asserting: POSTing to release a chore claimed by the current
user resets its `status` to `open` and `claimed_by` to `None`, confirmed by
re-fetching the `Chore` from the DB; POSTing to release a chore claimed by a
*different* member of the same household is rejected with 403 and leaves the
chore's `status`/`claimed_by` unchanged; POSTing to release a chore that is
already `open` (claimed by no one) is rejected with 409 and leaves the chore
unchanged; releasing a chore id that belongs to a different household
returns 404 and leaves that chore unchanged, even if it is `claimed`;
releasing a nonexistent chore id returns 404; a GET to the release endpoint
does not change the chore's `status` and returns a non-2xx (405) response;
and a request with no active session identity redirects to `/identity/`
rather than performing the release.

## 12. Complete a chore and award points — Completed 2026-09-07 17:10 PDT
Goal: Let the claiming user mark a chore done and award its points for the
current week.
Description: Build an action endpoint (e.g. POST `/chores/<id>/complete/`,
named `complete_chore`) wrapped in the task 4 identity guard, so a request
with no active session identity redirects (302) to `/identity/` rather than
running. Resolve the active household via the current user's
`HouseholdMember` row (same lookup as tasks 8, 10, and 11). Look up the target `Chore`
scoped to that household — a chore id belonging to a different household
must be treated as not found (404), not completed, even if it is `claimed`,
so household isolation holds against a guessed/crafted id; a nonexistent
chore id likewise returns 404.

This task needs a way to compute "the current Monday-start week" before
task 14 formally builds one, since a `WeeklyCompletion` row can't be written
without a `week_start_date`. Add a small helper now (e.g. a
`current_week_start()` function in a new `chores/weeks.py`, using
`django.utils.timezone.localdate()` per the spec's "server local time" rule)
that returns the date of the Monday on or before today. Task 14 should reuse
this helper (and extend its tests across the Sunday-to-Monday boundary)
rather than introduce a competing one.

If the chore exists in the active household, its `status` is `claimed`, and
`claimed_by` equals the current session user, create a `WeeklyCompletion`
row with `chore`, `household`, `user` set to the current user,
`points_awarded` set to a snapshot of the chore's *current* `points` value
(per task 3, `points_awarded` is independent of `Chore.points` so later
point-value edits never rewrite this record), `week_start_date` from
`current_week_start()`, and `completed_at` defaulting to creation time; then
reset the chore back to `status="open"` and `claimed_by=None` (chores are
recurring — completing one never deletes it), leaving its `name`, `room`,
and `points` unchanged. Return a JSON success response (e.g.
`{"status": "completed", "points_awarded": <n>}`) with a 200.

If the chore is `claimed` by a *different* user, reject the completion —
create no `WeeklyCompletion` row, leave the chore unchanged, and return a
JSON error response with 403 (the requester doesn't hold this claim). If the
chore is already `open` (not claimed by anyone), reject the completion too —
create no `WeeklyCompletion` row, leave the chore unchanged, and return a
JSON error response with 409 (nothing to complete), matching tasks 10/11's use
of 409 for "not in the expected state" rather than treating it as a
permissions problem. Only accept POST (or another mutating method) — a GET
must not perform the completion, per the spec's `fetch`-backed JSON
convention for dynamic interactions; reject non-POST requests with 405
rather than allowing state changes via GET.

Include tests asserting: POSTing to complete a chore claimed by the current
user creates exactly one `WeeklyCompletion` row with `points_awarded`
matching the chore's `points` at completion time, `week_start_date` equal to
the current Monday (`current_week_start()`), and `user`/`household` matching
the current user/active household, confirmed by querying the DB; the same
request resets the chore's `status` back to `open` and `claimed_by` to
`None` (not deleted — the chore still exists) while its `name`/`room`/
`points` are unchanged; completing a chore claimed by a *different* member
of the same household is rejected with 403, creates no `WeeklyCompletion`
row, and leaves the chore's `status`/`claimed_by` unchanged; completing a
chore that is already `open` (claimed by no one) is rejected with 409,
creates no `WeeklyCompletion` row, and leaves the chore unchanged; completing
a chore id that belongs to a different household returns 404, creates no
`WeeklyCompletion` row, and leaves that chore unchanged, even if it is
`claimed`; completing a nonexistent chore id returns 404; changing a chore's
`points` after completing it once (task 16 territory, but exercisable now
via direct model edit in the test) does not change the already-recorded
`WeeklyCompletion.points_awarded`; `current_week_start()` returns the same
Monday date for every day Monday through Sunday of a given week and a date
one day earlier (the prior Sunday) for the preceding week — i.e. it correctly
straddles a Sunday-to-Monday boundary; a GET to the complete endpoint does
not change the chore's `status`, creates no `WeeklyCompletion` row, and
returns a non-2xx (405) response; and a request with no active session
identity redirects to `/identity/` rather than performing the completion.

## 13. Points board view — Completed 2026-09-07 17:35 PDT
Goal: Show each household member's point total for the current week.
Description: Build a read-only view (e.g. URL `/points/` named
`points_board`) wrapped in the task 4 identity guard, so a request with no
active session identity redirects (302) to `/identity/` instead of rendering
the board. Assume the `WeeklyCompletion` model (task 3), the session
identity helpers/guard (task 4), and the `current_week_start()` helper
(`chores/weeks.py`, task 12) already exist — task 14 will formally own
week-boundary logic, but this task can rely on `current_week_start()` as it
stands now. Resolve the active household via the current user's
`HouseholdMember` row (same lookup as tasks 8, 10, 11, and 12), then, for every `User`
who is a member of that household (via `HouseholdMember`), sum
`WeeklyCompletion.points_awarded` where `household` matches the active
household and `week_start_date` equals `current_week_start()`, grouped by
`user`.

A member of the active household with zero completions this week must still
appear on the board with a total of `0`, not be omitted — the point of the
board is to surface imbalance, including "did nothing this week." Order the
results consistently — descending by total, ties broken alphabetically by
name **case-insensitively** (e.g. `order_by(Lower("user__name"))` or an
equivalent case-insensitive key, not a naive `order_by("name")`, since
SQLite's default `CharField` collation is case-sensitive and would sort
uppercase names before lowercase ones — "Bob" before "adam" — rather than
true alphabetical order; this mirrors the case-insensitive name handling
already required elsewhere, e.g. task 2's membership uniqueness and task 6's
join-name check) — so a test can assert on exact list contents and order
rather than an unordered set. A household with no members other than the current user
still renders 200 with that one member's total (`0` if they have no
completions yet) rather than erroring.

Include tests asserting: a user with one completed chore this week
(`points_awarded=n`) shows a total of `n` on the board; a user with multiple
completed chores this week shows the sum of their `points_awarded` values;
a member of the active household with no completions this week appears on
the board with a total of `0` rather than being omitted; a
`WeeklyCompletion` belonging to a different household is excluded from
every total, even if it was awarded to a user with the same display name or
the same underlying real-world person acting under a different `User` row
in another household (task 7) — household isolation must hold; a
`WeeklyCompletion` in the active household but from a *previous*
`week_start_date` is excluded from the current total (it doesn't leak into
"this week"'s sum); a `WeeklyCompletion` dated for a *future* week (an edge
case beyond normal use — e.g. a test fixture simulating clock skew) is
likewise excluded, since only `week_start_date == current_week_start()`
should count; two members of the active household tied at the same
current-week point total appear in case-insensitive alphabetical order by
name (e.g. a member named "bob" and a member named "Alice" tied at the same
total must show "Alice" first — a naive case-sensitive sort would wrongly
place lowercase "bob" before uppercase "Alice"); and a request with no
active session identity redirects to `/identity/` rather than rendering the
board.

## 14. Weekly rollover — Completed 2026-09-07 17:55 PDT
Goal: Confirm the weekly reset is already fully correct and needs no new
production code, and close the one remaining gap: proving that crossing a
week boundary never mutates existing `Chore` state or `WeeklyCompletion`
history.
Description: Task 12 already built `current_week_start()` (`chores/weeks.py`)
and tested it across the Sunday-to-Monday boundary
(`CurrentWeekStartTests.test_straddles_sunday_to_monday_boundary`), and task
13's points board already sums `WeeklyCompletion.points_awarded` filtered to
`week_start_date == current_week_start()`, with tests proving a completion
from a previous week (`test_completion_from_previous_week_excluded`) or a
future week (`test_completion_from_future_week_excluded`) is excluded from
the current total, and a member with zero completions this week still shows
a `0` (`test_member_with_no_completions_appears_with_zero_total`). Taken
together, these already prove the points board "naturally shows zero" once a
new week begins — no batch job, cron, or management command computes or
mutates a weekly reset anywhere in this codebase (there is none), and none is
being added here: the reset is a pure side effect of `week_start_date`-scoped
queries run at read time. Likewise, nothing in the codebase touches a
`Chore`'s `status`/`claimed_by` on a schedule or in response to the current
date — only the claim/release/complete actions (tasks 10-12) ever change
those fields — so unclaimed and claimed-but-incomplete chores already stay
exactly as they are across a week boundary, by the simple fact that no code
path exists that would do otherwise.

What's not yet pinned down by an explicit test is that invariant itself:
that simulating a week boundary crossing leaves existing `Chore` rows and
`WeeklyCompletion` rows completely unchanged, and that hitting the read-only
points board view (task 13) across that boundary has no side effects. This
task adds no production code — only tests that lock in the current, correct
behavior so a future regression (e.g., someone later adding a scheduled task
that clears the chore pool or archives old completions) would be caught.

Include tests asserting: a `Chore` left `claimed` (with a `claimed_by` set)
before a simulated week boundary retains the exact same `status` and
`claimed_by` after the boundary is crossed (patch
`chores.weeks.timezone.localdate`, as `CurrentWeekStartTests` already does,
to move `current_week_start()` into a new week, then re-fetch the `Chore`
from the DB and compare to its pre-boundary values) — no rollover step is
invoked, because none exists; the same holds for a `Chore` left `open`; a
`WeeklyCompletion` row created in the prior week is still present with every
field (`points_awarded`, `week_start_date`, `chore`, `user`, `household`,
`completed_at`) unchanged after the boundary is crossed, confirmed by
re-fetching it from the DB; `WeeklyCompletion.objects.count()` is unchanged
before and after a GET to `/points/` (task 13) that spans a simulated week
boundary, confirming the read-only board view has no write side effects; and
after the boundary is crossed, that same prior-week completion contributes
`0` to the new current week's total on `/points/` while still being fully
present in the database (re-asserting
`test_completion_from_previous_week_excluded`'s exclusion, but this time
paired with a DB check that the row survived unmodified, closing the gap
that test alone doesn't check for).

## 15. History view — Completed 2026-09-07 18:10 PDT
Goal: Show a log of a household's completed chores, grouped by week, so
members can see who did what and how many points it earned over time — not
just the current week, which the points board (task 13) already covers.
Description: Build a read-only view (e.g. URL `/history/` named `history`)
wrapped in the task 4 `require_identity` guard, so a request with no active
session identity redirects (302) to `/identity/` instead of rendering
history. Resolve the active household via the current user's
`HouseholdMember` row (same lookup as tasks 8, 10-13). Query
`WeeklyCompletion` rows scoped to that household only (mirroring task 13's
household-isolation filter — a completion belonging to a different household
must never appear, even if it was awarded to a user with the same display
name as a member of the active household), and group them by
`week_start_date`.

Every week that has at least one completion is shown, including the
week-in-progress (`week_start_date == current_week_start()`, from
`chores/weeks.py`, task 12) — nothing in the data model distinguishes a
"past" week from the current one except how `current_week_start()` happens
to evaluate at read time, so this view must not filter out the current week;
a completion made earlier today should show up in history immediately, not
only after the week rolls over. Order the week groups by `week_start_date`
descending — most recent week first — so the most relevant history surfaces
at the top of the page. Within each week group, list the individual
completions (completing user's name, chore's name, `points_awarded`,
`completed_at`) ordered by `completed_at` descending, with `id` descending as
a tiebreaker for determinism (mirroring task 8's `id`-tiebreaker pattern,
since two completions could in principle share a `completed_at` timestamp).
Also show each week group's total points (the sum of `points_awarded` for
that week's completions) computed from the same household-scoped rows
already fetched, not a second query. A household with zero
`WeeklyCompletion` rows at all (no history yet) still renders 200 with an
empty list/message rather than erroring — mirroring the empty-state handling
in tasks 8 and 13.

Include tests asserting: a `WeeklyCompletion` belonging to the active
household appears in the rendered history, showing the completing user's
name, the chore's name, `points_awarded`, and `completed_at`; a
`WeeklyCompletion` belonging to a different household is excluded from the
history entirely, even if it was awarded to a user with the same display
name as a member of the active household (household isolation, mirroring
task 13); completions from two different `week_start_date`s render as two
separate groups, each containing only that week's completions, and each
group's displayed total equals the sum of that week's `points_awarded`
values; the week groups appear ordered most-recent-`week_start_date`-first;
multiple completions within the same week group render in a deterministic
order (`completed_at` descending, `id` descending as tiebreaker) across
repeated requests; a completion dated for the current week-in-progress
(`week_start_date == current_week_start()`) appears in the history alongside
older weeks in the same grouped structure, rather than being held back until
the week rolls over; a household with zero `WeeklyCompletion` rows renders
200 with an empty list/message rather than an error; and a request with no
active session identity redirects to `/identity/` rather than rendering
history.

## 16. Household settings — manage chores — Completed 2026-09-07 18:35 PDT
Goal: Let members add new chores to the pool and edit existing ones (name,
room, points), scoped to the active household.
Description: Build a new view (e.g. URL `/settings/` named
`household_settings`) wrapped in the task 4 `require_identity` guard, so a
request with no active session identity redirects (302) to `/identity/`
instead of rendering. Resolve the active household via the current user's
`HouseholdMember` row (same lookup as tasks 8, 10-13, 15). On GET, render
every `Chore` row belonging to that household — not just `status="open"`
ones (unlike task 8's chore pool, this page is for managing the whole pool,
so a `claimed` chore must still show up here to be editable) — ordered the
same deterministic way as task 8 (`order_by("name", "id")`), each with a
link to `/chores/<id>/edit/`, plus an empty "add a chore" form (name, room,
points). Task 17 will extend this same `/settings/` page with the join-code
and member-list sections, mirroring how tasks 5/6 both extend
`choose_identity` rather than introducing competing pages.

Follow the `choose_identity` form-handling pattern (tasks 5/6): GET renders,
POST processes, and a rejected submission re-renders the form with an error
and creates/changes no rows rather than raising a server error. On POST to
`/settings/`, treat the submission as the "add a chore" form. Validate
before ever touching the model layer — `Chore.save()` calls `full_clean()`
(task 3), so handing it bad data directly would surface as an unhandled
`ValidationError`, not a friendly re-rendered form: strip `name` and `room`
and reject (re-render with an error, no `Chore` created) if either is blank
after stripping; parse `points` and reject the same way if it isn't a valid
integer, or is `0` or negative (mirroring `Chore.points`'s
`MinValueValidator(1)`, task 3) — a non-numeric string (e.g. `"abc"`) and a
non-integer numeric string (e.g. `"3.5"`) both count as invalid input here,
same as `0` or a negative value. `Chore.name` has no uniqueness constraint
(task 8 already established this — two chores in a household can share a
name), so unlike `User`/`Household` names, no duplicate check is needed. On
a valid submission, create a `Chore` with `household` set to the active
household, the stripped `name`/`room`, the parsed `points`, and let
`status`/`claimed_by` take their model defaults (`open`/unset) — a chore
created here is never pre-claimed — then redirect (302) back to
`/settings/` rather than re-rendering.

Build a second view (URL `/chores/<id>/edit/`, named `chore_edit`), also
wrapped in `require_identity`. Look up the target `Chore` scoped to the
active household in one query — `get_object_or_404(Chore, id=chore_id,
household=household)`, the same structural pattern tasks 10-12 use for
claim/release/complete — on both GET and POST, so a chore id belonging to a
different household is indistinguishable from a nonexistent one (404)
whether you're loading the edit form or submitting it, not only on
submission. On GET, render a form pre-filled with the chore's current
`name`, `room`, and `points`. On POST, apply the same validation as the
create form above (blank name/room after stripping, non-integer/zero/
negative points all rejected with a re-rendered form and no change to the
`Chore` row); on success, update only `name`, `room`, and `points` on the
existing row and redirect (302) to `/settings/`. Editing must never touch
`status` or `claimed_by` — those fields are owned exclusively by the
claim/release/complete actions (tasks 10-12), not by this form, so editing a
chore that is currently `claimed` must leave its `status`/`claimed_by`
exactly as they were, even though its `name`/`room`/`points` change.
Likewise, per task 3's design (`WeeklyCompletion.points_awarded` is its own
stored value, independent of `Chore.points`, "so that editing a chore's
point value later (task 16) never rewrites already-recorded history"),
editing a chore's `points` after a `WeeklyCompletion` referencing it already
exists must leave that completion's `points_awarded` completely unchanged —
this task is exactly the "later" edit task 3 was written in anticipation of.

Include tests asserting: submitting a valid add-chore form on `/settings/`
creates exactly one `Chore` in the active household with the submitted
(stripped) `name`/`room` and parsed `points`, `status="open"`, and no
`claimed_by`; that new chore then appears in the chore pool view (task 8,
`/chores/`) with the same name/room/points, proving the two views agree;
submitting the add-chore form with a blank (or whitespace-only) `name` or
`room`, or with `points` that is non-numeric, zero, or negative, re-renders
`/settings/` with an error and creates no `Chore`; GET `/settings/` lists
every chore in the active household regardless of `status` (both `open` and
`claimed` chores appear) and excludes chores belonging to other households;
GET `/chores/<id>/edit/` for a chore in the active household returns 200
with the form pre-filled with that chore's current values; submitting a
valid edit updates that exact `Chore` row's `name`/`room`/`points`
(confirmed by re-fetching from the DB) and redirects to `/settings/`;
submitting an edit with a blank name/room or invalid points (non-numeric,
zero, negative) re-renders the edit form with an error and leaves the
`Chore` row completely unchanged; editing a chore that is currently
`status="claimed"` with some `claimed_by` set updates its `name`/`room`/
`points` but leaves `status` and `claimed_by` exactly as they were before
the edit; editing a chore's `points` after a `WeeklyCompletion` row already
references it (created via direct model creation in the test, as task 12's
tests do) leaves that `WeeklyCompletion.points_awarded` unchanged; GET or
POST to `/chores/<id>/edit/` for a chore id belonging to a different
household returns 404 and leaves that chore's row completely unchanged, so
household isolation holds against a guessed/crafted id; GET or POST to
`/chores/<id>/edit/` for a nonexistent chore id returns 404; and a request
to either `/settings/` or `/chores/<id>/edit/` with no active session
identity redirects to `/identity/` rather than rendering or processing the
form.

## 17. Household settings — join code and member list — Completed 2026-09-07 18:50 PDT
Goal: Let members view the household's join code and see who's currently in
it, extending the same `/settings/` page task 16 built rather than
introducing a new page.
Description: Extend the existing `household_settings` view
(`chores/views.py`) and its template
(`chores/templates/chores/household_settings.html`), both already wrapped in
the task 4 `require_identity` guard and already resolving the active
household via the current user's `HouseholdMember` row (same lookup as tasks
8, 10-13, 15, 16) — do not add a new URL/view for this, mirroring how tasks
5/6 both extend `choose_identity` rather than introduce competing pages.

Add two read-only sections to the GET-rendered page, alongside the existing
chores list and add-chore form (unchanged by this task): the active
household's `join_code` (rendered as plain text, e.g.
`{{ household.join_code }}`), and a list of the household's current
members — every `HouseholdMember` row scoped to the active household,
showing each member's `User.name`. Order the member list deterministically:
ascending alphabetically by name, case-insensitively (mirroring task 13's
points-board ordering, e.g.
`HouseholdMember.objects.filter(household=household).select_related("user").order_by(Lower("user__name"))`
or equivalent) — `User.name` is already unique within a household
case-insensitively (task 2), so no further tiebreaker is needed. Both
sections must be scoped to the active household only: a different
household's `join_code` or member rows must never appear, even if that other
household's `join_code` or a member's name happens to look similar to the
active household's.

Add a copy-to-clipboard control (e.g. a button using the browser clipboard
API) next to the displayed join code, as a frontend/JS affordance — this is
a UI nicety with no server-observable behavior, so it is not something a
Django test client can meaningfully assert on. Scope the testable acceptance
criteria below to what the server actually renders (the join code text and
member names present in the response), not the copy button's JS behavior,
which is a manual/visual check only.

This task changes only the GET rendering path of `household_settings` — the
existing POST handling (add-chore form, task 16) and the `chore_edit` view
are unchanged.

Include tests asserting: GET `/settings/` for a signed-in session includes
the active household's `join_code` text in the rendered response; GET
`/settings/` includes the display name of every current member of the
active household (every `HouseholdMember` row for that household) in the
rendered response; a `join_code` belonging to a *different* household does
not appear anywhere in the response; a member's name belonging to a
*different* household does not appear in the response (household isolation,
mirroring tasks 8/13/15); the member list renders in ascending alphabetical
order case-insensitively (e.g. a member named "bob" and a member named
"Alice" in the same household render with "Alice" appearing before "bob");
the existing add-chore form and chore list from task 16 still render and
function unchanged (submitting a valid add-chore form still creates exactly
one `Chore`, per task 16's existing test coverage — not a new assertion,
just confirming this task didn't regress it); and a request to `/settings/`
with no active session identity redirects to `/identity/` rather than
rendering.

---

**Tasks 18 and below have not been groomed yet** — they still reflect the
original backlog language and will be reviewed for checkable acceptance
criteria and edge cases when their turn comes up.

---

## 18. Base layout and navigation — Completed 2026-09-08 04:55 PDT
Goal: Give the app a consistent shell — shared nav and minimal CSS — so the
views that exist today feel like one product instead of a set of
disconnected standalone pages.
Description: Add `chores/templates/chores/base.html`: a `<!DOCTYPE html>`
shell with `<meta charset="utf-8">`, a `{% block title %}{% endblock %}`
inside `<title>`, minimal shared CSS (plain `<style>` block or a linked
static CSS file — no framework/build step, per `AGENTS.md`), a `<nav>`
element (give it a stable marker, e.g. `<nav id="site-nav">`, so tests can
scope assertions to it) containing links built with `{% url %}` — never
hardcoded paths — to the chore pool (`chore_pool`, `/chores/`), points board
(`points_board`, `/points/`), history (`history`, `/history/`), household
settings (`household_settings`, `/settings/`), and the household switcher
(`switch_identity`, `/switch/`), and a `{% block content %}{% endblock %}`
for page-specific markup. This task touches templates only — no
`views.py`/`urls.py`/model changes, and no view needs to start passing new
context; the nav's five links are static markup, not conditioned on any
per-view data.

Convert every existing template to extend `base.html`, keeping each page's
current substantive content (chore list, points-board table, history groups,
settings forms/lists, chore-edit form, switch-identity list, including all
existing dynamic values, error messages, and the task 17 copy-to-clipboard
button) unchanged inside `{% block content %}` — this is a restyle/rewire,
not a rewrite of what any page shows: `index.html`, `chore_pool.html`,
`points_board.html`, `history.html`, `household_settings.html`,
`chore_edit.html`, and `switch_identity.html`. Per task 9's forward note
("task 18 should extend/restyle this same index/root page ... rather than
introduce a competing landing page"), `index.html` drops its own now-
redundant inline `<ul>` of links to `/chores/` and `/switch/` — that
navigation now lives in the shared nav — and keeps a short welcome
heading/intro in its content block.

`choose_identity.html` (`/identity/`) is explicitly **out of scope** and
stays a standalone full-HTML document, not converted to extend `base.html`:
it's the task 4 guard's own redirect target, reachable precisely when a
session has *no* active identity, so wiring it into a nav whose links all
point at guarded pages would only show links that immediately bounce the
visitor back to `/identity/` — dead weight rather than useful navigation.

Task 21's "my claimed chores" view isn't built yet, so the nav does not get
a sixth link for it now — see task 23 (appended below) for adding that link
once task 21 lands, rather than stubbing a dead link today.

The shared CSS itself has no server-observable behavior a Django test client
can assert on (mirroring task 17's copy-button caveat) — treat visual
styling as a manual/visual check only: after making these changes, manually
click through each nav link from a signed-in session to confirm every linked
page loads and the nav renders consistently.

Include tests asserting: for a signed-in session, GET on each of `/`,
`/chores/`, `/points/`, `/history/`, `/settings/`, and `/switch/` returns 200
and the rendered response contains all five nav link URLs (`/chores/`,
`/points/`, `/history/`, `/settings/`, `/switch/`); GET
`/chores/<id>/edit/` for a chore in the active household (task 16) also
returns 200 and contains those same five nav link URLs; each of those six
pages' pre-existing content still renders correctly after the conversion —
reuse/extend each task's existing content assertions (e.g., the chore pool
still shows an open chore's name per task 8, the points board still shows a
member's total per task 13, history still shows a completion per task 15,
settings still shows the join code and member list per task 17, switch
identity still shows known identities per task 7) rather than re-deriving
new assertions, so a wiring regression is caught without duplicating
already-covered behavior; GET `/identity/` with no active session identity
still returns 200 and does **not** contain the five nav link URLs (proving
the shared nav is scoped to signed-in/guarded pages, not leaked onto a page
a signed-out session can't use its links from); GET `/` with an active
identity no longer contains its old standalone `<ul>` of exactly `/chores/`
and `/switch/` as inline body content (superseded by the shared nav) while
still returning 200 and still containing those URLs via the nav itself —
distinguish the two by asserting the nav's marker (e.g. `id="site-nav"`)
wraps the links, not just checking for the bare hrefs anywhere in the page;
and each converted template's rendered `<title>` still reflects that specific
page rather than a generic shell title shared across all of them — e.g.
`<title>Chore pool</title>` for `/chores/` and `<title>Points board</title>`
for `/points/` — confirming the `{% block title %}` inheritance actually
fills in per page.

## 19. Show join code immediately after creating a household — Completed 2026-09-08 05:10 PDT
Goal: Let a household's creator see and copy the join code right away,
without having to first navigate to settings.
Description: Extend `_handle_create` (`chores/views.py`, task 5) so that,
immediately after creating the `Household`/`User`/`HouseholdMember` rows and
calling `set_current_user`, it also sets a one-time session flag — e.g.
`request.session["show_new_household_banner"] = True` — before
`choose_identity` redirects to `chore_pool` (task 8, updated to
`redirect("chore_pool")` by task 8). `_handle_join` (task 6) and
`switch_identity`'s POST success path (task 7) must **not** set this flag —
the banner is specific to *creating* a household, not joining one or
switching into one.

Extend `chore_pool` (`chores/views.py`, task 8) to consume the flag on the
very next render: `show_new_household_banner =
request.session.pop("show_new_household_banner", False)`. Using `.pop()`
(not `.get()`) is what makes this one-time — the key is removed from the
session the instant it's read, so a page reload, a second GET to `/chores/`,
or navigating away and back via the shared nav (task 18) never shows the
banner again for that session, even though the flag was set only moments
earlier. `chore_pool` doesn't currently pass `household` to its template
(only `chores`) — add two context keys instead of the whole object:
`show_new_household_banner` (the popped boolean) and
`new_household_join_code`, set to `household.join_code` (from the same
`household` variable the view already resolves via the current user's
`HouseholdMember` row for its chore-list query) when the flag is `True`, or
omitted/`None` when it's `False`. Do not stash the join code (or a household
id) inside the session flag itself and read it back from there — always
derive `new_household_join_code` from that request's live `household`
lookup. Because `chore_pool` re-resolves the active household from the
session's *current* identity on every request, and the flag is popped on
this exact request, the code shown can never drift to a different
household — including across task 7's multi-household switching, where a
session's active identity (and thus active household) can change between the
create POST and any later GET to `/chores/`.

Add the banner markup to `chores/templates/chores/chore_pool.html`, inside
`{% block content %}`, conditioned on `show_new_household_banner` — e.g. a
`<div id="new-household-banner">` containing explanatory text and the code
in its own element, e.g. `<span id="new-household-join-code">{{
new_household_join_code }}</span>`, so tests can assert on the code precisely
rather than scraping surrounding prose. This is a one-time interstitial
banner, distinct from task 17's permanent join-code display in household
settings: task 17's `{{ household.join_code }}` in
`household_settings.html` renders on *every* GET to `/settings/` for as long
as the household exists, with no session state involved, while this banner
renders at most once — only on the single `chore_pool` render immediately
following creation — and never again afterward for that session, even for
that same household.

This task touches `_handle_create`, `chore_pool`, and `chore_pool.html`
only — no new URL, no new view, no model changes, and no change to
`_handle_join`, `switch_identity`, or `household_settings`.

Include tests asserting: submitting a valid create-household form, then
following the redirect with a GET to `/chores/` in that same test-client
session, renders the banner containing the household's actual `join_code`
(assert the response contains that exact string, read back from
`Household.objects.get(...).join_code` in the DB — not a hardcoded/guessed
value); a second GET to `/chores/` in that same session immediately
afterward (simulating a reload or re-visiting via the nav) does **not**
render the banner or the join code, proving the flag is one-time and cleared
after its first consumption; joining an existing household (task 6) and then
GETing `/chores/` never renders the banner, since only creation sets the
flag; switching identity (task 7, POST to `/switch/`) to a different,
previously-created household and then GETing `/chores/` does not render the
banner (switching itself never sets the flag, and any flag set by that
household's own earlier creation was already consumed the first time
`/chores/` was visited right after creating it); and a session that creates
two households back to back (POSTing to `/identity/` with `action=create` a
second time while already holding an active identity — `choose_identity` is
unguarded, so this is reachable today without waiting on task 20) sees, after
the *second* creation, a banner showing the *second* household's join code
specifically — not the first's — confirming the code always matches the
currently active household rather than a stale one from an earlier creation
in the same session.

## 20. Link from the household switcher to create/join another household — Completed 2026-09-08 05:25 PDT
Goal: Let someone already viewing the switcher (task 7) add a new household
or identity to the current browser session without navigating to
`/identity/` by hand.
Description: Add a link to `chores/templates/chores/switch_identity.html`
(task 7's template, already extending `base.html` per task 18), inside
`{% block content %}`, pointing at `{% url 'choose_identity' %}`
(`/identity/`) — built with `{% url %}`, never a hardcoded path, mirroring
task 18's nav links. Give it a stable marker (e.g.
`id="add-household-link"`) so tests can assert on it precisely rather than
scraping surrounding prose. This is a template-only change: `switch_identity`
(`chores/views.py`, task 7) needs no code change to render this link, since
it's static markup conditioned on nothing — the view doesn't gain a new
context key.

No changes are needed to `choose_identity`, `_handle_create`, or
`_handle_join` (tasks 4-6) either — reading their current implementation
confirms the "must not clear or replace an existing identity" requirement
this task's Goal implies is already satisfied structurally, not something to
newly build: GET `/identity/` never touches `request.session` at all
(`choose_identity`'s GET path only renders the template), so simply
following the new link and landing on the page leaves the current active
identity and `known_user_ids` completely untouched regardless of whether one
is already set. A subsequent successful POST (create or join) calls
`set_current_user` (`chores/identity.py`, task 7), which always sets the
*new* user as `request.session["user_id"]` (making it the newly active
identity — the same behavior tasks 5/6 already rely on when reached from a
fresh session) and *appends* the new user's id to `known_user_ids` without
ever removing an id already present, so an existing identity's entry
survives a subsequent create/join by that same session. This existing
behavior is already exercised by task 19's
`test_creating_two_households_back_to_back_shows_second_households_code`,
but that test doesn't assert on `known_user_ids` directly; this task closes
that gap with an explicit assertion, reached via the new link's path
(switcher → identity page → create/join) rather than only via a bare POST to
`/identity/`.

Include tests asserting: GET `/switch/` for a session with at least one
known identity contains a link to `/identity/` (assert on the marker, e.g.
`id="add-household-link"`, and that its target resolves to `/identity/`);
following that link — GET `/identity/` with an active identity already set —
returns 200 and leaves both `request.session["user_id"]` and
`request.session["known_user_ids"]` completely unchanged (confirmed by
comparing session state before and after the GET); starting from a session
with one identity already active, then submitting a valid create-household
form on `/identity/`, results in `request.session["known_user_ids"]`
containing both the original identity's id and the newly created one (not
just the new one), and a subsequent GET `/switch/` lists both households,
with the new one marked as currently active and the original one shown as
switchable; the same holds for submitting a valid join-household form
instead of create (starting from one active identity, joining a second
household results in `known_user_ids` containing both ids, and `/switch/`
lists both); and a session with no active identity at all is redirected away
from `/switch/` to `/identity/` by the existing task 4 guard before ever
reaching this new link (mirroring task 7's own
`test_guard_redirects_when_no_identity_set`) — so the link is only ever
reachable from a session that already has at least one identity to
preserve.

## 21. My claimed chores view — Completed 2026-09-08 05:40 PDT
Goal: Let a member see the chores they've personally claimed but not yet
completed.
Description: `_docs/plan.md` lists "My claimed chores" as one of the
minimum views, but no existing task builds it — tasks 10-12 only cover the
claim/release/complete *actions*, not a page listing a member's own claims.
Build a read-only view (e.g. URL `/chores/mine/` named `my_claimed_chores`)
wrapped in the task 4 identity guard, so a request with no active session
identity redirects (302) to `/identity/` instead of rendering the list.
Resolve the active household via the current user's `HouseholdMember` row,
same as tasks 8, 10-13, 15-17, then list `Chore` rows with `status="claimed"`
and `claimed_by` equal to the current session user, scoped to that
household, showing each chore's name, room, and point value. A chore claimed
by a different member of the same household must not appear, even though it
shares the household — this view is scoped to "claimed by me," not "claimed
by anyone." A user with no active claims still renders 200 with an empty
list/message rather than erroring. Nothing stops a user from holding claims
on more than one chore at once (claiming is per-chore, not limited to one
active claim per user), so order the results the same deterministic way as
task 8's chore pool (`order_by("name", "id")`) — `Chore.name` has no
uniqueness constraint, so two of the current user's claimed chores can share
a name; break ties by `id` so a test can assert on exact list contents and
order rather than an unordered set.

Its template (`chores/templates/chores/my_claimed_chores.html`) must extend
`chores/base.html` and use `{% block title %}`/`{% block content %}`, like
every other template converted or added since task 18 (`chore_pool.html`,
`points_board.html`, `history.html`, `household_settings.html`,
`chore_edit.html`, `switch_identity.html`, `index.html`) — this task does
not itself ship a first-class template, it ships one that matches the
established shell. Note explicitly what this task does *not* do: it does not
add a sixth link to `base.html`'s shared `<nav>` — task 23, appended to this
backlog when task 18 was groomed, already owns wiring `my_claimed_chores`
into the nav once this view exists, and doing it here would duplicate that
work. Because `base.html`'s nav is static markup rendered on every page that
extends it regardless of which page is current (the same reason
`chore_edit.html`, itself not one of the five linked pages, still shows the
nav), `/chores/mine/` already renders the existing five nav links the moment
its template extends `base.html`, even before task 23 adds the sixth link
pointing back at itself.

Include tests asserting: a chore claimed by the current user appears in the
rendered list; a chore claimed by a different user in the same household is
excluded; a chore claimed by the current session's *other* identity in a
different household (per task 7's multi-household switching) is excluded;
an open (unclaimed) chore in the active household is excluded; two chores
claimed by the current user that share the same `name` still render in a
deterministic order (e.g. ascending `id`) across repeated requests; GET
`/chores/mine/` for a signed-in session returns 200 and the rendered
response contains the existing five nav link URLs from task 18
(`/chores/`, `/points/`, `/history/`, `/settings/`, `/switch/`), confirming
the template extends `base.html` rather than rendering standalone; and a
request with no active session identity redirects to `/identity/` rather
than rendering the list.

## 22. Cap the history view to the most recent weeks — Completed 2026-09-08 05:55 PDT
Goal: Keep the history view (task 15) from rendering an unbounded page as a
household's `WeeklyCompletion` log grows over months of use.
Description: Task 15's history view intentionally has no limit on how many
week groups it queries/renders — scoping that decision was out of scope for
task 15 itself, since it's a growth concern rather than a correctness one,
and flagging it as its own backlog item kept task 15 focused on
grouping/ordering/isolation correctness. This is a local homework project
(per `_docs/plan.md`, "no deployment/hosting required"), so a `?page=` query
param or a "load more" control is more machinery than the problem needs —
cap the view to a fixed number of most-recent weeks instead of building
pagination. Add a module-level constant, e.g. `HISTORY_WEEKS_LIMIT = 12`, in
`chores/views.py` (or `chores/weeks.py`, alongside `current_week_start()`),
so the exact number is a single source of truth tests can import rather than
a magic number re-typed in assertions.

Determine the active household's `HISTORY_WEEKS_LIMIT` most recent distinct
`week_start_date`s (e.g.
`WeeklyCompletion.objects.filter(household=household).values_list("week_start_date", flat=True).distinct().order_by("-week_start_date")[:HISTORY_WEEKS_LIMIT]`)
and filter the completions query to only those dates before grouping — this
must be computed within the same household-scoped queryset task 15 already
filters by `household`, so the number of weeks shown for one household is
never inflated or reduced by another household's history (household
isolation must hold under the cap the same way it already holds for task
15's per-completion filtering). Everything task 15 already established about
the resulting weeks stays true under the cap: most-recent-`week_start_date`-
first ordering, the current week-in-progress included and counted as one of
the `HISTORY_WEEKS_LIMIT` slots (not shown in addition to them), `completed_at`/
`id`-descending order within each group, and each group's total computed
from the same fetched rows (not a second query per group). A household with
`HISTORY_WEEKS_LIMIT` or fewer distinct weeks of history renders every week
it has, unaffected by the cap.

Include tests asserting: a household with more than `HISTORY_WEEKS_LIMIT`
distinct `week_start_date`s renders exactly `HISTORY_WEEKS_LIMIT` week
groups by default, the `HISTORY_WEEKS_LIMIT` most recent ones, with the
older week(s) beyond the cutoff excluded entirely; those rendered weeks
still appear most-recent-first, per task 15; a household with exactly
`HISTORY_WEEKS_LIMIT` distinct weeks renders all of them (boundary case,
proving the cutoff isn't off-by-one in either direction); a household with
fewer than `HISTORY_WEEKS_LIMIT` weeks renders exactly as task 15 already
specifies, with no missing or duplicated weeks; a second household with more
history than `HISTORY_WEEKS_LIMIT` does not affect how many weeks render for
the active household (household isolation under the cap, mirroring task
15's existing isolation tests); and the current week-in-progress, when
present among a household's most recent `HISTORY_WEEKS_LIMIT` weeks, still
appears in the rendered history alongside older weeks in the same grouped
structure, per task 15.

## 23. Add "My claimed chores" to the shared nav
Goal: Keep the shared nav (task 18) complete once task 21's "my claimed
chores" view exists, since task 18 intentionally ships without a link to it
because task 21 isn't built yet at that point in the backlog.
Description: Extend `chores/templates/chores/base.html`'s `<nav>` (task 18)
with a sixth link, built with `{% url 'my_claimed_chores' %}` (task 21,
`/chores/mine/`), alongside the existing five links (chore pool, points
board, history, settings, household switcher). No other change to
`base.html`'s structure or shared CSS is needed — this is purely adding one
more link to the same nav list, and no other converted template needs any
change.
Include tests asserting: for a signed-in session, GET on each of the
nav-bearing pages (`/`, `/chores/`, `/chores/mine/`, `/points/`,
`/history/`, `/settings/`, `/switch/`, and `/chores/<id>/edit/`) returns 200
and the rendered response contains all six nav link URLs, including
`/chores/mine/`, extending task 18's five-link assertion to six; and GET
`/identity/` with no active session identity still does not contain any of
the six nav link URLs, mirroring task 18's same scoping assertion.

## 24. Add a way back to the switcher from `/identity/` when an identity is already active
Goal: Let someone who followed task 20's new link from the switcher to
`/identity/`, then changed their mind, get back to `/switch/` without
relying on the browser's back button.
Description: `choose_identity.html` (`/identity/`) is a standalone page with
no shared nav — task 18 explicitly keeps it out of the `base.html` layout,
since it's the task 4 guard's own redirect target and reachable with no
active identity at all, when a nav full of guarded-page links would be dead
weight for that visitor. Task 20 adds a legitimate path to this same page
*from* a guarded page (the switcher) for a session that already has an
active identity, so for that specific case add a link back to `/switch/` on
`choose_identity.html`, conditioned on `get_current_user(request)` (task 4)
returning a non-`None` user — shown only when there is an existing identity
to switch back to; a session with no active identity at all (the normal,
un-guarded arrival at this page) sees no such link, since there is nothing
to go back to. This is a template change plus one new boolean/user context
key passed by the `choose_identity` view (`chores/views.py`, tasks 4-6) on
GET only — no change to `_handle_create`, `_handle_join`, or
`switch_identity`, and no change to POST handling.
Include tests asserting: GET `/identity/` with an active identity already
set includes a link to `/switch/`; GET `/identity/` with no active identity
set does not include a link to `/switch/`; and the existing create/join
forms and their behavior (tasks 5/6, including their existing test
coverage) are unchanged by this addition.
