# Backlog

Tasks for building the Household Chore Tracker described in
[plan.md](plan.md). Each task is scoped to be finishable in one sitting and
handed off without needing to read the others — background/spec references
are repeated where useful rather than assumed.

## 1. Project setup with an empty passing test
Goal: Get a runnable Django project skeleton with one green test.
Description: Confirm/initialize the Django project (`choretracker`) and a
`chores` app, wire the app into `INSTALLED_APPS`, and add a placeholder URL
with a minimal view (e.g. returning a 200 with a plain "OK" response). Add a
single test that uses the Django test client to hit that URL and asserts a
200 response, so `python manage.py test` passes. No models or business logic
yet — this task just proves the project boots, routes a request, and the
test runner works.

## 2. `User`, `Household`, and `HouseholdMember` models
Goal: Model people, households, and membership between them.
Description: Add a `User` model (just a `name` field — no password/email,
per spec), a `Household` model (`name`, unique `join_code`), and a
`HouseholdMember` join model linking the two. Enforce that a user's `name` is
unique within a household (case-insensitive) at the membership level, since
names are not unique globally. Include migrations and model-level tests
(uniqueness constraint, basic creation).

## 3. `Chore` and `WeeklyCompletion` models
Goal: Model chores and the log of completions that drives points/history.
Description: Add a `Chore` model (`household`, `name`, `room`, `points`,
`status` of open/claimed, nullable `claimed_by`) and a `WeeklyCompletion`
model (`chore`, `household`, `user`, `points_awarded`, `week_start_date`,
`completed_at`). `WeeklyCompletion` is the source of truth for both the
points board and history views built later. Include migrations and tests
covering field defaults and basic creation.

## 4. Session-based "acting as" identity
Goal: Let a browser session remember which `User` it's currently acting as.
Description: Build a small helper (e.g. a context processor or utility
functions) that reads/writes the current `User.id` from Django's session,
with no `django.contrib.auth`/passwords involved. Add a guard (e.g. a
decorator or mixin) that redirects to a "who are you" prompt when no identity
is set. This is plumbing only — no UI for switching identities; that's built
in the household switcher task. Test that setting and reading the session
identity works and that an unset session triggers the redirect.

## 5. Create a household
Goal: Let a user start a new household with a shareable join code.
Description: Build a view/form where a person enters a household name and
their own display name, creates the `Household` (generating a unique
`join_code`) and a matching `User` + `HouseholdMember`, and sets the session
identity to that user. Test join-code generation for uniqueness and that the
creator becomes a member.

## 6. Join a household by code
Goal: Let a new person join an existing household using its join code.
Description: Build a view/form where a person enters a join code and a
display name, validates the code exists, enforces that the name is not
already taken in that household (case-insensitive), creates the `User` +
`HouseholdMember`, and sets the session identity. Test the happy path, an
invalid code, and a duplicate-name rejection.

## 7. Household switcher / switch person
Goal: Let a person see and switch between all households (and identities)
they hold, and let one browser demo multiple people.
Description: Using the session identity helpers from task 4, build a view
listing the households linked to the current session's identities (a person
may have separate `User` rows per household) plus any other known identities
for demo purposes, and a control to switch the active session identity to
one of them. Test that switching correctly changes which household's data
subsequent views operate on, and that switching to a different person's
identity works the same way.

## 8. Chore pool view
Goal: Show all open (unclaimed) chores for the active household.
Description: Build a read-only view listing chores with `status="open"` for
the current household, showing name, room, and point value. Assume the
`Chore` model and session identity already exist. Test that only the active
household's open chores appear, not other households' or claimed ones.

## 9. Claim a chore
Goal: Let the acting user claim an open chore.
Description: Build an action (view + `fetch`-backed endpoint per the spec's
JSON convention) that sets a chore's `status` to `claimed` and
`claimed_by` to the current session user, only if it was previously open.
Test that claiming an already-claimed chore is rejected and that claiming
updates the chore correctly.

## 10. Release a claimed chore
Goal: Let the claiming user put a chore back into the open pool.
Description: Build an action that resets a chore's `status` to `open` and
clears `claimed_by`, but only if the requester is the user who currently
holds the claim. Test that a non-claiming user cannot release someone else's
claim.

## 11. Complete a chore and award points
Goal: Let the claiming user mark a chore done and award its points for the
current week.
Description: Build an action that, for a chore claimed by the current user,
creates a `WeeklyCompletion` row (points, user, household, current
Monday-start week, timestamp) and resets the chore back to `open` for the
next cycle (chores are recurring, not deleted). Test that completing awards
the right points, uses the correct week boundary, and that a non-claiming
user can't complete someone else's claim.

## 12. Points board view
Goal: Show each household member's point total for the current week.
Description: Build a read-only view that sums `WeeklyCompletion.points_awarded`
per user for the household's current `week_start_date` (Monday–Sunday) and
displays a simple leaderboard/table. Test that totals are scoped to the
current household and current week only.

## 13. Weekly rollover
Goal: Reset point totals for a new week without losing history or chores.
Description: Add a way to determine the current week's start date
consistently (Monday, server local time) so that once a new week begins, the
points board naturally shows zero until new completions happen this week,
while past `WeeklyCompletion` rows remain untouched for history. Unclaimed
or claimed-but-incomplete chores simply stay as-is in the pool (no deletion
or "missed" marking). Test the week-boundary calculation across a
Sunday-to-Monday transition.

## 14. History view
Goal: Show past weeks' totals and/or a log of completed chores.
Description: Build a read-only view listing prior weeks'
`WeeklyCompletion` records for the household, grouped by `week_start_date`,
showing who completed what and how many points it earned. Test that it
excludes other households' data and correctly groups multiple weeks.

## 15. Household settings — manage chores
Goal: Let members add and edit chores in the pool.
Description: Build views/forms to create a new chore (name, room, points) and
edit an existing one, scoped to the active household. Test that chores
created here appear in the chore pool view and that editing updates the
right record.

## 16. Household settings — join code and member list
Goal: Let members view/copy the household's join code and see who's in it.
Description: Build a read-only settings section showing the household's
`join_code` (with a copy-to-clipboard affordance) and a list of current
members. Test that the join code displayed matches the household's stored
code and the member list matches `HouseholdMember` rows.

## 17. Base layout and navigation
Goal: Give the app a consistent shell so all the views feel like one product.
Description: Build a base Django template (nav linking to chore pool, points
board, history, settings, household switcher) that other view templates
extend, plus minimal shared CSS. No new backend logic — this is purely
wiring existing views into a coherent layout. Manually click through each
linked page to confirm navigation works.
