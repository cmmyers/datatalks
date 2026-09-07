# Household Chore Tracker — Spec

## Overview

A web-based tool for managing shared household chores, built around
**accountability and fair distribution of effort** rather than just reminders.
Chores live in a shared pool per household; members claim and complete them at
will, earning points that are meant to balance out across the household over
time.

This is a local homework project — no deployment/hosting required, just needs
to run on localhost with a real backend and database.

## Core Concepts

- **Household** — a private group of people sharing a chore pool. Fully
  isolated from other households (no cross-visibility of chores, members, or
  points).
- **User** — a person, identified by a name, with no password/email. Identity
  is tied to the browser session, and that same session can belong to
  multiple households. A name must be unique **within** a household, but
  names are never matched across households — the same name in two different
  households is never assumed to be the same person.
- **Chore** — a task with a point value, belonging to one household.
- **Claim** — a user taking ownership of an open chore. Once claimed, only
  that user can mark it complete (or release it back to the pool).
- **Points** — accumulated per user, per household, and tallied on a weekly
  cycle. The goal is visible balance, not enforcement — the app surfaces the
  numbers; it doesn't block anyone from doing more or less.

## Features (v1)

### Households
- Create a new household (generates a shareable join code).
- Join a household using a join code.
- Belong to and switch between multiple households.
- Each household has its own member list, chore pool, and point history.

### People / Identity
- No accounts, no passwords. A person picks a display name when they first
  join or create a household.
- Lightweight local "session" (browser-stored) remembers who you're currently
  acting as, so the app is usable without logging in — this also makes it
  possible to demo multiple people/households from one browser (e.g. a
  "switch person" control for grading/demo purposes).

### Chores
- Each chore has: name, room, point value, and household it belongs to.
- Chores sit in an open pool, visible to all household members.
- Any member can claim an open chore.
- The claiming member marks it done (honor system — no photo/approval
  required) or releases it back to the pool unclaimed.
- Chores are recurring by default: completing one doesn't delete it, it just
  resets it for the next cycle.

### Points & Balance
- Completing a chore awards its point value to the completing user for the
  current week.
- Points are tallied **per week**, Monday–Sunday, per household.
- A household view shows each member's point total for the current week, so
  the group can see the balance (or imbalance) at a glance.
- On weekly reset, point totals zero out for the new week; **unclaimed or
  incomplete chores roll over** into the new week's pool rather than
  disappearing or being marked missed.
- Historical weekly totals are kept (not deleted) so there's a track record
  over time, even though "current standing" is always this week's numbers.

### Views (minimum)
- **Household switcher** — pick which household you're acting in.
- **Chore pool** — open chores available to claim, with point values.
- **My claimed chores** — chores you've claimed but not yet completed.
- **Points board** — this week's point totals per household member.
- **History** — past weeks' totals and/or a log of completed chores (who,
  what, when, how many points).
- **Household settings** — add/edit chores, view/copy join code, member list.

### Explicitly out of scope for v1
- Notifications/reminders (push, email, or otherwise).
- Photo proof or peer approval/confirmation of completed chores.
- Public sign-up / discoverable households — joining always requires a code.
- Mobile app / installable PWA.
- Deployment or hosting of any kind — local only.

## Tech Stack

- **Backend:** Django (required by the assignment).
- **Database:** SQLite via Django's ORM (Django's default, zero setup,
  sufficient for local use).
- **Frontend:** Plain HTML/CSS/JS. Rendered via Django templates for page
  structure, with `fetch` calls back to Django views for the dynamic bits
  (claiming a chore, marking complete, switching household/person) — no
  separate JS framework, no Node/npm/build step.
- **Communication:** Django views return either rendered templates (page
  loads) or JSON (for the `fetch`-driven interactions), backed by Django
  models/ORM against SQLite. Plain Django views are enough; Django REST
  Framework is unnecessary for a scope this small unless you want the
  practice with it.
- **Identity:** Django's session framework can carry the "who am I acting as
  right now" state (no need for `django.contrib.auth`/passwords — a session
  variable holding the current `User.id` is enough to satisfy the "simple
  shared code, no real accounts" model and to let one browser convincingly
  demo switching between people/households).
- **Run:** Standard Django dev server (`python manage.py runserver`); the
  app is used by opening `localhost:8000` in a browser.

## Data Model (draft)

Maps directly onto Django models (each block below is one model; `id` is
Django's implicit auto primary key, foreign keys and the join table would use
`ForeignKey`/`ManyToManyField` as usual).

```
User
  id
  name

Household
  id
  name
  join_code (unique)

HouseholdMember (join table: User <-> Household)
  user_id
  household_id
  # (household_id, user.name) must be unique, case-insensitive — enforced at
  # the membership layer since user.name isn't globally unique across users

Chore
  id
  household_id
  name
  room
  points
  status        # open | claimed | (completed handled via WeeklyCompletion log)
  claimed_by    # user_id, nullable

WeeklyCompletion
  id
  chore_id
  household_id
  user_id
  points_awarded
  week_start_date
  completed_at
```

`WeeklyCompletion` is the source of truth for both the points board (sum by
user + household for the current `week_start_date`) and history (group by
past `week_start_date`s).

## Decisions (formerly Open Questions)

1. **Week boundary** — Weeks run Monday–Sunday, server local time. Confirmed,
   hardcoded.
2. **Chore fields** — v1 chore fields are name, room, and points (no category,
   no due date/recurrence interval beyond the weekly pool).
3. **Releasing a claim** — Confirmed: a member can release a chore they've
   claimed but not finished, putting it back in the open pool for anyone to
   claim.
4. **Duplicate names** — A name must be unique **within** a household
   (case-insensitive), enforced when a person creates or joins a household —
   attempting to use a name already taken by someone else in that household
   is rejected with a prompt to pick another. Names are **not** deduplicated
   or matched globally: the same name showing up in two different households
   is never assumed to be the same person, and no identity-merging happens
   across households.
