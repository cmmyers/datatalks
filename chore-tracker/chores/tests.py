import datetime
from unittest.mock import patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone

from chores.identity import get_current_user, require_identity, set_current_user
from chores.models import Chore, Household, HouseholdMember, User, WeeklyCompletion
from chores.weeks import current_week_start


class HealthViewTests(TestCase):
    def test_returns_200(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)


class UserModelTests(TestCase):
    def test_create_user(self):
        user = User.objects.create(name="Alex")
        self.assertEqual(user.name, "Alex")


class HouseholdModelTests(TestCase):
    def test_join_code_is_generated_and_unique(self):
        first = Household.objects.create(name="Smith House")
        second = Household.objects.create(name="Jones House")
        self.assertTrue(first.join_code)
        self.assertNotEqual(first.join_code, second.join_code)

    def test_join_code_uniqueness_enforced(self):
        Household.objects.create(name="Smith House", join_code="ABC123")
        with self.assertRaises(IntegrityError):
            Household.objects.create(name="Jones House", join_code="ABC123")


class HouseholdMemberModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")

    def test_create_membership(self):
        user = User.objects.create(name="Alex")
        membership = HouseholdMember.objects.create(user=user, household=self.household)
        self.assertEqual(membership.household, self.household)
        self.assertEqual(membership.user, user)

    def test_duplicate_name_in_household_rejected_case_insensitive(self):
        first_user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=first_user, household=self.household)

        second_user = User.objects.create(name="alex")
        with self.assertRaises(ValidationError):
            HouseholdMember.objects.create(user=second_user, household=self.household)

    def test_same_name_allowed_in_different_households(self):
        other_household = Household.objects.create(name="Jones House")
        first_user = User.objects.create(name="Alex")
        second_user = User.objects.create(name="Alex")

        HouseholdMember.objects.create(user=first_user, household=self.household)
        membership = HouseholdMember.objects.create(user=second_user, household=other_household)

        self.assertEqual(membership.household, other_household)


class ChoreModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")

    def test_new_chore_defaults_to_open_with_no_claimed_by(self):
        chore = Chore.objects.create(
            household=self.household, name="Dishes", room="Kitchen", points=5
        )
        self.assertEqual(chore.status, Chore.STATUS_OPEN)
        self.assertIsNone(chore.claimed_by)

    def test_chore_with_zero_points_fails_validation(self):
        chore = Chore(household=self.household, name="Dishes", room="Kitchen", points=0)
        with self.assertRaises(ValidationError):
            chore.save()

    def test_chore_with_negative_points_fails_validation(self):
        chore = Chore(household=self.household, name="Dishes", room="Kitchen", points=-1)
        with self.assertRaises(ValidationError):
            chore.save()

    def test_chore_with_invalid_status_fails_validation(self):
        chore = Chore(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status="completed",
        )
        with self.assertRaises(ValidationError):
            chore.save()

    def test_deleting_claimed_by_user_clears_claim_not_chore(self):
        user = User.objects.create(name="Alex")
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=user,
        )
        user.delete()
        chore.refresh_from_db()
        self.assertIsNone(chore.claimed_by)


class WeeklyCompletionModelTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)
        self.chore = Chore.objects.create(
            household=self.household, name="Dishes", room="Kitchen", points=5
        )

    def test_create_and_read_back_weekly_completion(self):
        week_start = datetime.date(2026, 9, 7)
        completion = WeeklyCompletion.objects.create(
            chore=self.chore,
            household=self.household,
            user=self.user,
            points_awarded=5,
            week_start_date=week_start,
        )
        fetched = WeeklyCompletion.objects.get(pk=completion.pk)
        self.assertEqual(fetched.chore, self.chore)
        self.assertEqual(fetched.household, self.household)
        self.assertEqual(fetched.user, self.user)
        self.assertEqual(fetched.points_awarded, 5)
        self.assertEqual(fetched.week_start_date, week_start)
        self.assertIsNotNone(fetched.completed_at)

    def test_points_awarded_zero_fails_validation(self):
        completion = WeeklyCompletion(
            chore=self.chore,
            household=self.household,
            user=self.user,
            points_awarded=0,
            week_start_date=datetime.date(2026, 9, 7),
        )
        with self.assertRaises(ValidationError):
            completion.save()

    def test_points_awarded_negative_fails_validation(self):
        completion = WeeklyCompletion(
            chore=self.chore,
            household=self.household,
            user=self.user,
            points_awarded=-3,
            week_start_date=datetime.date(2026, 9, 7),
        )
        with self.assertRaises(ValidationError):
            completion.save()

    def test_household_mismatch_with_chore_household_rejected(self):
        other_household = Household.objects.create(name="Jones House")
        completion = WeeklyCompletion(
            chore=self.chore,
            household=other_household,
            user=self.user,
            points_awarded=5,
            week_start_date=datetime.date(2026, 9, 7),
        )
        with self.assertRaises(ValidationError):
            completion.save()

    def test_deleting_chore_with_completion_raises_protected_error(self):
        WeeklyCompletion.objects.create(
            chore=self.chore,
            household=self.household,
            user=self.user,
            points_awarded=5,
            week_start_date=datetime.date(2026, 9, 7),
        )
        with self.assertRaises(ProtectedError):
            self.chore.delete()

    def test_deleting_household_with_completion_raises_protected_error(self):
        WeeklyCompletion.objects.create(
            chore=self.chore,
            household=self.household,
            user=self.user,
            points_awarded=5,
            week_start_date=datetime.date(2026, 9, 7),
        )
        with self.assertRaises(ProtectedError):
            self.household.delete()

    def test_deleting_user_with_completion_raises_protected_error(self):
        WeeklyCompletion.objects.create(
            chore=self.chore,
            household=self.household,
            user=self.user,
            points_awarded=5,
            week_start_date=datetime.date(2026, 9, 7),
        )
        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_changing_chore_points_does_not_rewrite_existing_completion(self):
        completion = WeeklyCompletion.objects.create(
            chore=self.chore,
            household=self.household,
            user=self.user,
            points_awarded=5,
            week_start_date=datetime.date(2026, 9, 7),
        )
        self.chore.points = 10
        self.chore.save()

        completion.refresh_from_db()
        self.assertEqual(completion.points_awarded, 5)


@require_identity
def _dummy_guarded_view(request):
    return HttpResponse("OK")


def _make_request(path="/dummy/"):
    """Build a request with a real, working session attached."""
    factory = RequestFactory()
    request = factory.get(path)
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    return request


class IdentityHelperTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

    def test_set_then_get_current_user_round_trips(self):
        request = _make_request()
        set_current_user(request, self.user)

        fetched = get_current_user(request)

        self.assertEqual(fetched, self.user)

    def test_get_current_user_returns_none_when_unset(self):
        request = _make_request()

        self.assertIsNone(get_current_user(request))

    def test_stale_user_id_is_removed_from_session(self):
        request = _make_request()
        request.session["user_id"] = self.user.id
        self.user.delete()

        result = get_current_user(request)

        self.assertIsNone(result)
        self.assertNotIn("user_id", request.session)


class RequireIdentityGuardTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

    def test_guarded_view_redirects_when_no_identity_set(self):
        request = _make_request()

        response = _dummy_guarded_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")

    def test_guarded_view_returns_200_when_identity_set(self):
        request = _make_request()
        set_current_user(request, self.user)

        response = _dummy_guarded_view(request)

        self.assertEqual(response.status_code, 200)

    def test_guarded_view_redirects_for_stale_user_id_without_raising(self):
        request = _make_request()
        request.session["user_id"] = self.user.id
        self.user.delete()

        response = _dummy_guarded_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")


class ChooseIdentityViewTests(TestCase):
    def test_returns_200_with_no_session_identity(self):
        response = self.client.get("/identity/")
        self.assertEqual(response.status_code, 200)

    def test_returns_200_with_session_identity_set(self):
        household = Household.objects.create(name="Smith House")
        user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=user, household=household)

        session = self.client.session
        session["user_id"] = user.id
        session.save()

        response = self.client.get("/identity/")
        self.assertEqual(response.status_code, 200)


class CreateHouseholdViewTests(TestCase):
    def test_valid_submission_creates_household_user_and_membership(self):
        response = self.client.post(
            "/identity/",
            {"household_name": "Smith House", "display_name": "Alex"},
        )

        self.assertEqual(Household.objects.count(), 1)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(HouseholdMember.objects.count(), 1)

        household = Household.objects.get()
        user = User.objects.get()
        membership = HouseholdMember.objects.get()
        self.assertEqual(membership.household, household)
        self.assertEqual(membership.user, user)
        self.assertEqual(response.status_code, 302)

    def test_join_code_is_non_empty_and_matches_expected_format(self):
        self.client.post(
            "/identity/",
            {"household_name": "Smith House", "display_name": "Alex"},
        )

        household = Household.objects.get()
        self.assertTrue(household.join_code)
        self.assertRegex(household.join_code, r"^[A-Z0-9]{8}$")

    def test_many_households_never_produce_duplicate_join_codes(self):
        for i in range(20):
            self.client.post(
                "/identity/",
                {"household_name": f"House {i}", "display_name": f"User {i}"},
            )

        join_codes = list(Household.objects.values_list("join_code", flat=True))
        self.assertEqual(len(join_codes), 20)
        self.assertEqual(len(set(join_codes)), 20)

    def test_join_code_collision_is_retried(self):
        existing = Household.objects.create(name="Existing House", join_code="DUPCODE1")

        with patch(
            "chores.views.generate_join_code",
            side_effect=["DUPCODE1", "FRESHCOD"],
        ):
            response = self.client.post(
                "/identity/",
                {"household_name": "Smith House", "display_name": "Alex"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Household.objects.count(), 2)
        new_household = Household.objects.exclude(pk=existing.pk).get()
        self.assertEqual(new_household.join_code, "FRESHCOD")
        self.assertNotEqual(new_household.join_code, existing.join_code)

    def test_get_current_user_returns_new_user_after_creation(self):
        self.client.post(
            "/identity/",
            {"household_name": "Smith House", "display_name": "Alex"},
        )

        user = User.objects.get()
        self.assertEqual(self.client.session["user_id"], user.id)

    def test_successful_submission_redirects_to_chore_pool(self):
        response = self.client.post(
            "/identity/",
            {"household_name": "Smith House", "display_name": "Alex"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/chores/")

    def test_blank_household_name_rerenders_with_error_and_creates_no_rows(self):
        response = self.client.post(
            "/identity/",
            {"household_name": "   ", "display_name": "Alex"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Household.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(HouseholdMember.objects.count(), 0)

    def test_blank_display_name_rerenders_with_error_and_creates_no_rows(self):
        response = self.client.post(
            "/identity/",
            {"household_name": "Smith House", "display_name": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Household.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(HouseholdMember.objects.count(), 0)

    def test_whitespace_padded_names_are_stripped_before_storing(self):
        self.client.post(
            "/identity/",
            {"household_name": "  My House  ", "display_name": "  Alex  "},
        )

        household = Household.objects.get()
        user = User.objects.get()
        self.assertEqual(household.name, "My House")
        self.assertEqual(user.name, "Alex")


class JoinHouseholdViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House", join_code="JOINME1")
        self.existing_user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.existing_user, household=self.household)

    def test_valid_join_creates_user_and_membership_no_new_household(self):
        response = self.client.post(
            "/identity/",
            {"action": "join", "join_code": "JOINME1", "display_name": "Jamie"},
        )

        self.assertEqual(Household.objects.count(), 1)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(HouseholdMember.objects.count(), 2)

        new_user = User.objects.get(name="Jamie")
        membership = HouseholdMember.objects.get(user=new_user)
        self.assertEqual(membership.household, self.household)
        self.assertEqual(response.status_code, 302)

    def test_get_current_user_returns_new_user_after_joining(self):
        self.client.post(
            "/identity/",
            {"action": "join", "join_code": "JOINME1", "display_name": "Jamie"},
        )

        new_user = User.objects.get(name="Jamie")
        self.assertEqual(self.client.session["user_id"], new_user.id)

    def test_successful_join_redirects_to_chore_pool(self):
        response = self.client.post(
            "/identity/",
            {"action": "join", "join_code": "JOINME1", "display_name": "Jamie"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/chores/")

    def test_join_code_matching_no_household_rerenders_with_error(self):
        response = self.client.post(
            "/identity/",
            {"action": "join", "join_code": "NOPE0000", "display_name": "Jamie"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(HouseholdMember.objects.count(), 1)

    def test_blank_join_code_rerenders_with_error_and_creates_no_rows(self):
        response = self.client.post(
            "/identity/",
            {"action": "join", "join_code": "   ", "display_name": "Jamie"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(HouseholdMember.objects.count(), 1)

    def test_blank_display_name_rerenders_with_error_and_creates_no_rows(self):
        response = self.client.post(
            "/identity/",
            {"action": "join", "join_code": "JOINME1", "display_name": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(HouseholdMember.objects.count(), 1)

    def test_duplicate_display_name_in_target_household_rejected_case_insensitive(self):
        response = self.client.post(
            "/identity/",
            {"action": "join", "join_code": "JOINME1", "display_name": "aLEX"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(HouseholdMember.objects.count(), 1)

    def test_same_display_name_in_different_household_succeeds(self):
        other_household = Household.objects.create(name="Jones House", join_code="OTHER123")
        other_user = User.objects.create(name="Jamie")
        HouseholdMember.objects.create(user=other_user, household=other_household)

        response = self.client.post(
            "/identity/",
            {"action": "join", "join_code": "JOINME1", "display_name": "Jamie"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(HouseholdMember.objects.count(), 3)

        new_user = User.objects.exclude(pk__in=[self.existing_user.pk, other_user.pk]).get()
        membership = HouseholdMember.objects.get(user=new_user)
        self.assertEqual(membership.household, self.household)

    def test_padded_join_code_and_display_name_are_stripped(self):
        response = self.client.post(
            "/identity/",
            {"action": "join", "join_code": "  JOINME1  ", "display_name": "  Jamie  "},
        )

        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(name="Jamie")
        membership = HouseholdMember.objects.get(user=new_user)
        self.assertEqual(membership.household, self.household)


class SwitchIdentityViewTests(TestCase):
    def setUp(self):
        # Create a household (task 5), then join a second one (task 6) in
        # the same session, so this session's known_user_ids ends up
        # holding two identities across two households.
        self.client.post(
            "/identity/",
            {"household_name": "Smith House", "display_name": "Alex"},
        )
        self.household1 = Household.objects.get(name="Smith House")
        self.user1 = User.objects.get(name="Alex")

        self.household2 = Household.objects.create(name="Jones House", join_code="JOIN2")
        self.client.post(
            "/identity/",
            {"action": "join", "join_code": "JOIN2", "display_name": "Jamie"},
        )
        self.user2 = User.objects.get(name="Jamie")

    def test_known_user_ids_contains_both_identities_after_create_and_join(self):
        known_user_ids = self.client.session["known_user_ids"]
        self.assertCountEqual(known_user_ids, [self.user1.id, self.user2.id])

    def test_get_switch_lists_both_households(self):
        response = self.client.get("/switch/")

        self.assertEqual(response.status_code, 200)
        identities = response.context["identities"]
        rendered = {entry["user"].id: entry["household"] for entry in identities}
        self.assertEqual(rendered[self.user1.id], self.household1)
        self.assertEqual(rendered[self.user2.id], self.household2)

    def test_switching_to_second_identity_changes_active_household(self):
        response = self.client.post("/switch/", {"user_id": self.user2.id})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/chores/")
        self.assertEqual(self.client.session["user_id"], self.user2.id)
        membership = HouseholdMember.objects.get(user_id=self.client.session["user_id"])
        self.assertEqual(membership.household, self.household2)

    def test_switching_back_to_first_identity_restores_it(self):
        self.client.post("/switch/", {"user_id": self.user2.id})
        response = self.client.post("/switch/", {"user_id": self.user1.id})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/chores/")
        self.assertEqual(self.client.session["user_id"], self.user1.id)
        membership = HouseholdMember.objects.get(user_id=self.client.session["user_id"])
        self.assertEqual(membership.household, self.household1)

    def test_switching_to_already_known_identity_does_not_duplicate(self):
        self.client.post("/switch/", {"user_id": self.user2.id})
        before = sorted(self.client.session["known_user_ids"])

        self.client.post("/switch/", {"user_id": self.user2.id})
        after = sorted(self.client.session["known_user_ids"])

        self.assertEqual(before, after)
        self.assertEqual(len(after), 2)

    def test_switching_to_user_from_separate_session_is_rejected(self):
        other_client = Client()
        other_client.post(
            "/identity/",
            {"household_name": "Other House", "display_name": "Riley"},
        )
        other_user = User.objects.get(name="Riley")

        current_user_id_before = self.client.session["user_id"]
        response = self.client.post("/switch/", {"user_id": other_user.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["user_id"], current_user_id_before)

    def test_switching_with_non_numeric_user_id_is_rejected(self):
        current_user_id_before = self.client.session["user_id"]
        response = self.client.post("/switch/", {"user_id": "not-a-number"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["user_id"], current_user_id_before)

    def test_get_switch_with_single_known_identity_returns_200(self):
        solo_client = Client()
        solo_client.post(
            "/identity/",
            {"household_name": "Lone House", "display_name": "Sam"},
        )

        response = solo_client.get("/switch/")

        self.assertEqual(response.status_code, 200)

    def test_deleted_known_user_omitted_from_rendered_list(self):
        # Switch back to user1 so the deleted user (user2) isn't the
        # currently active identity itself.
        self.client.post("/switch/", {"user_id": self.user1.id})
        self.user2.delete()

        response = self.client.get("/switch/")

        self.assertEqual(response.status_code, 200)
        identities = response.context["identities"]
        rendered_ids = [entry["user"].id for entry in identities]
        self.assertEqual(rendered_ids, [self.user1.id])

    def test_guard_redirects_when_no_identity_set(self):
        fresh_client = Client()
        response = fresh_client.get("/switch/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")


class ChorePoolViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

        self.other_household = Household.objects.create(name="Jones House")

        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

    def test_open_chore_in_active_household_appears_in_list(self):
        chore = Chore.objects.create(
            household=self.household, name="Dishes", room="Kitchen", points=5
        )

        response = self.client.get("/chores/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(chore, list(response.context["chores"]))

    def test_open_chore_in_different_household_excluded(self):
        Chore.objects.create(
            household=self.other_household, name="Laundry", room="Bathroom", points=3
        )

        response = self.client.get("/chores/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["chores"]), [])

    def test_claimed_chore_in_active_household_excluded(self):
        Chore.objects.create(
            household=self.household,
            name="Trash",
            room="Kitchen",
            points=2,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        response = self.client.get("/chores/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["chores"]), [])

    def test_household_with_no_open_chores_renders_200_with_empty_list(self):
        response = self.client.get("/chores/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["chores"]), [])

    def test_no_active_identity_redirects_to_identity(self):
        fresh_client = Client()
        response = fresh_client.get("/chores/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")

    def test_same_named_chores_render_in_deterministic_order_by_id(self):
        first = Chore.objects.create(
            household=self.household, name="Sweep", room="Kitchen", points=1
        )
        second = Chore.objects.create(
            household=self.household, name="Sweep", room="Living Room", points=2
        )

        response = self.client.get("/chores/")

        self.assertEqual(list(response.context["chores"]), [first, second])

        response_again = self.client.get("/chores/")
        self.assertEqual(list(response_again.context["chores"]), [first, second])


class IndexViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

    def test_no_active_identity_redirects_to_identity(self):
        response = self.client.get("")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")

    def test_active_identity_returns_200_with_links(self):
        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

        response = self.client.get("")

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("/chores/", content)
        self.assertIn("/switch/", content)

    def test_visiting_root_does_not_mutate_session(self):
        session = self.client.session
        session["user_id"] = self.user.id
        session["known_user_ids"] = [self.user.id]
        session.save()

        before_user_id = self.client.session["user_id"]
        before_known_user_ids = list(self.client.session["known_user_ids"])

        self.client.get("")

        self.assertEqual(self.client.session["user_id"], before_user_id)
        self.assertEqual(
            list(self.client.session["known_user_ids"]), before_known_user_ids
        )


class ClaimChoreViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

        self.other_user = User.objects.create(name="Jamie")
        HouseholdMember.objects.create(user=self.other_user, household=self.household)

        self.other_household = Household.objects.create(name="Jones House")

        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

    def _claim_url(self, chore_id):
        return f"/chores/{chore_id}/claim/"

    def test_claiming_open_chore_sets_status_and_claimed_by(self):
        chore = Chore.objects.create(
            household=self.household, name="Dishes", room="Kitchen", points=5
        )

        response = self.client.post(self._claim_url(chore.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "claimed"})

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)
        self.assertEqual(chore.claimed_by, self.user)

    def test_claiming_already_claimed_chore_is_rejected(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.other_user,
        )

        response = self.client.post(self._claim_url(chore.id))

        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)
        self.assertEqual(chore.claimed_by, self.other_user)

    def test_claiming_chore_already_claimed_by_requester_is_rejected(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        response = self.client.post(self._claim_url(chore.id))

        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)
        self.assertEqual(chore.claimed_by, self.user)

    def test_claiming_chore_in_different_household_returns_404(self):
        chore = Chore.objects.create(
            household=self.other_household, name="Laundry", room="Bathroom", points=3
        )

        response = self.client.post(self._claim_url(chore.id))

        self.assertEqual(response.status_code, 404)

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_OPEN)
        self.assertIsNone(chore.claimed_by)

    def test_claiming_nonexistent_chore_returns_404(self):
        response = self.client.post(self._claim_url(99999))

        self.assertEqual(response.status_code, 404)

    def test_get_request_does_not_claim_and_returns_405(self):
        chore = Chore.objects.create(
            household=self.household, name="Dishes", room="Kitchen", points=5
        )

        response = self.client.get(self._claim_url(chore.id))

        self.assertEqual(response.status_code, 405)

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_OPEN)

    def test_no_active_identity_redirects_to_identity(self):
        chore = Chore.objects.create(
            household=self.household, name="Dishes", room="Kitchen", points=5
        )

        fresh_client = Client()
        response = fresh_client.post(self._claim_url(chore.id))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_OPEN)


class ReleaseChoreViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

        self.other_user = User.objects.create(name="Jamie")
        HouseholdMember.objects.create(user=self.other_user, household=self.household)

        self.other_household = Household.objects.create(name="Jones House")

        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

    def _release_url(self, chore_id):
        return f"/chores/{chore_id}/release/"

    def test_releasing_own_claim_resets_status_and_claimed_by(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        response = self.client.post(self._release_url(chore.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "open"})

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_OPEN)
        self.assertIsNone(chore.claimed_by)

    def test_releasing_chore_claimed_by_different_user_is_rejected(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.other_user,
        )

        response = self.client.post(self._release_url(chore.id))

        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.json())

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)
        self.assertEqual(chore.claimed_by, self.other_user)

    def test_releasing_already_open_chore_is_rejected(self):
        chore = Chore.objects.create(
            household=self.household, name="Dishes", room="Kitchen", points=5
        )

        response = self.client.post(self._release_url(chore.id))

        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_OPEN)
        self.assertIsNone(chore.claimed_by)

    def test_releasing_chore_in_different_household_returns_404(self):
        chore = Chore.objects.create(
            household=self.other_household,
            name="Laundry",
            room="Bathroom",
            points=3,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        response = self.client.post(self._release_url(chore.id))

        self.assertEqual(response.status_code, 404)

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)
        self.assertEqual(chore.claimed_by, self.user)

    def test_releasing_nonexistent_chore_returns_404(self):
        response = self.client.post(self._release_url(99999))

        self.assertEqual(response.status_code, 404)

    def test_get_request_does_not_release_and_returns_405(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        response = self.client.get(self._release_url(chore.id))

        self.assertEqual(response.status_code, 405)

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)

    def test_no_active_identity_redirects_to_identity(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        fresh_client = Client()
        response = fresh_client.post(self._release_url(chore.id))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)


class CurrentWeekStartTests(TestCase):
    def test_returns_same_monday_for_every_day_monday_through_sunday(self):
        # Monday 2026-09-07 through Sunday 2026-09-13.
        monday = datetime.date(2026, 9, 7)
        days_in_week = [monday + datetime.timedelta(days=offset) for offset in range(7)]

        for day in days_in_week:
            with patch("chores.weeks.timezone.localdate", return_value=day):
                self.assertEqual(current_week_start(), monday)

    def test_straddles_sunday_to_monday_boundary(self):
        previous_sunday = datetime.date(2026, 9, 6)
        previous_monday = datetime.date(2026, 8, 31)
        next_monday = datetime.date(2026, 9, 7)

        with patch("chores.weeks.timezone.localdate", return_value=previous_sunday):
            self.assertEqual(current_week_start(), previous_monday)

        with patch("chores.weeks.timezone.localdate", return_value=next_monday):
            self.assertEqual(current_week_start(), next_monday)


class CompleteChoreViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

        self.other_user = User.objects.create(name="Jamie")
        HouseholdMember.objects.create(user=self.other_user, household=self.household)

        self.other_household = Household.objects.create(name="Jones House")

        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

    def _complete_url(self, chore_id):
        return f"/chores/{chore_id}/complete/"

    def test_completing_own_claim_awards_points_and_resets_chore(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        response = self.client.post(self._complete_url(chore.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "completed", "points_awarded": 5})

        self.assertEqual(WeeklyCompletion.objects.count(), 1)
        completion = WeeklyCompletion.objects.get()
        self.assertEqual(completion.chore, chore)
        self.assertEqual(completion.household, self.household)
        self.assertEqual(completion.user, self.user)
        self.assertEqual(completion.points_awarded, 5)
        self.assertEqual(completion.week_start_date, current_week_start())

        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_OPEN)
        self.assertIsNone(chore.claimed_by)
        self.assertEqual(chore.name, "Dishes")
        self.assertEqual(chore.room, "Kitchen")
        self.assertEqual(chore.points, 5)

    def test_completing_chore_claimed_by_different_user_is_rejected(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.other_user,
        )

        response = self.client.post(self._complete_url(chore.id))

        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.json())

        self.assertEqual(WeeklyCompletion.objects.count(), 0)
        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)
        self.assertEqual(chore.claimed_by, self.other_user)

    def test_completing_already_open_chore_is_rejected(self):
        chore = Chore.objects.create(
            household=self.household, name="Dishes", room="Kitchen", points=5
        )

        response = self.client.post(self._complete_url(chore.id))

        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())

        self.assertEqual(WeeklyCompletion.objects.count(), 0)
        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_OPEN)
        self.assertIsNone(chore.claimed_by)

    def test_completing_chore_in_different_household_returns_404(self):
        chore = Chore.objects.create(
            household=self.other_household,
            name="Laundry",
            room="Bathroom",
            points=3,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        response = self.client.post(self._complete_url(chore.id))

        self.assertEqual(response.status_code, 404)

        self.assertEqual(WeeklyCompletion.objects.count(), 0)
        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)
        self.assertEqual(chore.claimed_by, self.user)

    def test_completing_nonexistent_chore_returns_404(self):
        response = self.client.post(self._complete_url(99999))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(WeeklyCompletion.objects.count(), 0)

    def test_editing_points_after_completion_leaves_points_awarded_unchanged(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        response = self.client.post(self._complete_url(chore.id))
        self.assertEqual(response.status_code, 200)

        completion = WeeklyCompletion.objects.get()
        self.assertEqual(completion.points_awarded, 5)

        chore.points = 99
        chore.save()

        completion.refresh_from_db()
        self.assertEqual(completion.points_awarded, 5)

    def test_get_request_does_not_complete_and_returns_405(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        response = self.client.get(self._complete_url(chore.id))

        self.assertEqual(response.status_code, 405)

        self.assertEqual(WeeklyCompletion.objects.count(), 0)
        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)

    def test_no_active_identity_redirects_to_identity(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )

        fresh_client = Client()
        response = fresh_client.post(self._complete_url(chore.id))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")

        self.assertEqual(WeeklyCompletion.objects.count(), 0)
        chore.refresh_from_db()
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)


class PointsBoardViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

        self.other_household = Household.objects.create(name="Jones House")

        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

    def _make_chore(self, household=None, points=5):
        return Chore.objects.create(
            household=household or self.household, name="Dishes", room="Kitchen", points=points
        )

    def _complete(self, user, household=None, points=5, week_start_date=None):
        household = household or self.household
        chore = self._make_chore(household=household, points=points)
        return WeeklyCompletion.objects.create(
            chore=chore,
            household=household,
            user=user,
            points_awarded=points,
            week_start_date=week_start_date or current_week_start(),
        )

    def test_user_with_one_completion_this_week_shows_that_total(self):
        self._complete(self.user, points=5)

        response = self.client.get("/points/")

        self.assertEqual(response.status_code, 200)
        board = response.context["board"]
        self.assertEqual(len(board), 1)
        self.assertEqual(board[0]["user"], self.user)
        self.assertEqual(board[0]["total"], 5)

    def test_user_with_multiple_completions_this_week_shows_sum(self):
        self._complete(self.user, points=5)
        self._complete(self.user, points=3)

        response = self.client.get("/points/")

        board = response.context["board"]
        self.assertEqual(len(board), 1)
        self.assertEqual(board[0]["total"], 8)

    def test_member_with_no_completions_appears_with_zero_total(self):
        other_member = User.objects.create(name="Jamie")
        HouseholdMember.objects.create(user=other_member, household=self.household)

        response = self.client.get("/points/")

        board = response.context["board"]
        users_and_totals = {entry["user"]: entry["total"] for entry in board}
        self.assertIn(other_member, users_and_totals)
        self.assertEqual(users_and_totals[other_member], 0)

    def test_completion_from_different_household_excluded_even_with_same_name(self):
        same_name_user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=same_name_user, household=self.other_household)
        self._complete(same_name_user, household=self.other_household, points=10)

        response = self.client.get("/points/")

        board = response.context["board"]
        self.assertEqual(len(board), 1)
        self.assertEqual(board[0]["user"], self.user)
        self.assertEqual(board[0]["total"], 0)

    def test_completion_from_previous_week_excluded(self):
        previous_week = current_week_start() - datetime.timedelta(days=7)
        self._complete(self.user, points=5, week_start_date=previous_week)

        response = self.client.get("/points/")

        board = response.context["board"]
        self.assertEqual(board[0]["total"], 0)

    def test_completion_from_future_week_excluded(self):
        future_week = current_week_start() + datetime.timedelta(days=7)
        self._complete(self.user, points=5, week_start_date=future_week)

        response = self.client.get("/points/")

        board = response.context["board"]
        self.assertEqual(board[0]["total"], 0)

    def test_tied_members_ordered_case_insensitively_alphabetically(self):
        # "bob" (lowercase) must sort after "Alice" despite SQLite's
        # default case-sensitive CharField collation putting uppercase
        # before lowercase in a naive sort.
        bob = User.objects.create(name="bob")
        HouseholdMember.objects.create(user=bob, household=self.household)
        alice = User.objects.create(name="Alice")
        HouseholdMember.objects.create(user=alice, household=self.household)

        self._complete(bob, points=4)
        self._complete(alice, points=4)
        self._complete(self.user, points=4)

        response = self.client.get("/points/")

        board = response.context["board"]
        names_in_order = [entry["user"].name for entry in board]
        self.assertEqual(names_in_order, ["Alex", "Alice", "bob"])

    def test_household_with_only_current_user_renders_200(self):
        response = self.client.get("/points/")

        self.assertEqual(response.status_code, 200)
        board = response.context["board"]
        self.assertEqual(len(board), 1)
        self.assertEqual(board[0]["user"], self.user)
        self.assertEqual(board[0]["total"], 0)

    def test_no_active_identity_redirects_to_identity(self):
        fresh_client = Client()
        response = fresh_client.get("/points/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")


class WeeklyRolloverTests(TestCase):
    """Locks in that crossing a week boundary mutates nothing.

    No batch job, cron, or management command computes a weekly reset
    anywhere in this codebase (task 14) — the points board (task 13) simply
    re-queries WeeklyCompletion scoped to current_week_start() at read time,
    and nothing else touches Chore.status/claimed_by on a schedule. These
    tests simulate crossing the Sunday-to-Monday boundary the same way
    CurrentWeekStartTests does (patching chores.weeks.timezone.localdate)
    and assert that existing Chore and WeeklyCompletion rows come back
    byte-for-byte identical, and that hitting the points board across the
    boundary performs no writes.
    """

    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

        # Same boundary CurrentWeekStartTests.test_straddles_sunday_to_monday_boundary
        # uses: previous_sunday's week starts previous_monday; next_monday starts
        # its own new week.
        self.previous_sunday = datetime.date(2026, 9, 6)
        self.next_monday = datetime.date(2026, 9, 7)

    def test_claimed_chore_unchanged_across_week_boundary(self):
        chore = Chore.objects.create(
            household=self.household,
            name="Dishes",
            room="Kitchen",
            points=5,
            status=Chore.STATUS_CLAIMED,
            claimed_by=self.user,
        )
        pre_status = chore.status
        pre_claimed_by_id = chore.claimed_by_id

        with patch("chores.weeks.timezone.localdate", return_value=self.next_monday):
            chore.refresh_from_db()

        self.assertEqual(chore.status, pre_status)
        self.assertEqual(chore.claimed_by_id, pre_claimed_by_id)
        self.assertEqual(chore.status, Chore.STATUS_CLAIMED)
        self.assertEqual(chore.claimed_by_id, self.user.id)

    def test_open_chore_unchanged_across_week_boundary(self):
        chore = Chore.objects.create(
            household=self.household, name="Laundry", room="Bedroom", points=3
        )
        pre_status = chore.status
        pre_claimed_by_id = chore.claimed_by_id

        with patch("chores.weeks.timezone.localdate", return_value=self.next_monday):
            chore.refresh_from_db()

        self.assertEqual(chore.status, pre_status)
        self.assertEqual(chore.claimed_by_id, pre_claimed_by_id)
        self.assertEqual(chore.status, Chore.STATUS_OPEN)
        self.assertIsNone(chore.claimed_by_id)

    def test_weekly_completion_unchanged_across_week_boundary(self):
        with patch("chores.weeks.timezone.localdate", return_value=self.previous_sunday):
            week_start = current_week_start()

        chore = Chore.objects.create(
            household=self.household, name="Trash", room="Kitchen", points=4
        )
        completion = WeeklyCompletion.objects.create(
            chore=chore,
            household=self.household,
            user=self.user,
            points_awarded=4,
            week_start_date=week_start,
        )
        pre = {
            "points_awarded": completion.points_awarded,
            "week_start_date": completion.week_start_date,
            "chore_id": completion.chore_id,
            "user_id": completion.user_id,
            "household_id": completion.household_id,
            "completed_at": completion.completed_at,
        }

        with patch("chores.weeks.timezone.localdate", return_value=self.next_monday):
            completion.refresh_from_db()

        self.assertEqual(completion.points_awarded, pre["points_awarded"])
        self.assertEqual(completion.week_start_date, pre["week_start_date"])
        self.assertEqual(completion.chore_id, pre["chore_id"])
        self.assertEqual(completion.user_id, pre["user_id"])
        self.assertEqual(completion.household_id, pre["household_id"])
        self.assertEqual(completion.completed_at, pre["completed_at"])

    def test_points_board_get_across_boundary_has_no_write_side_effects(self):
        with patch("chores.weeks.timezone.localdate", return_value=self.previous_sunday):
            week_start = current_week_start()

        chore = Chore.objects.create(
            household=self.household, name="Vacuum", room="Living Room", points=6
        )
        WeeklyCompletion.objects.create(
            chore=chore,
            household=self.household,
            user=self.user,
            points_awarded=6,
            week_start_date=week_start,
        )
        count_before = WeeklyCompletion.objects.count()

        with patch("chores.weeks.timezone.localdate", return_value=self.next_monday):
            response = self.client.get("/points/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(WeeklyCompletion.objects.count(), count_before)

    def test_prior_week_completion_excluded_from_new_total_but_survives_boundary(self):
        with patch("chores.weeks.timezone.localdate", return_value=self.previous_sunday):
            week_start = current_week_start()

        chore = Chore.objects.create(
            household=self.household, name="Mop", room="Kitchen", points=7
        )
        completion = WeeklyCompletion.objects.create(
            chore=chore,
            household=self.household,
            user=self.user,
            points_awarded=7,
            week_start_date=week_start,
        )

        with patch("chores.weeks.timezone.localdate", return_value=self.next_monday):
            response = self.client.get("/points/")

        board = response.context["board"]
        totals_by_user = {entry["user"]: entry["total"] for entry in board}
        self.assertEqual(totals_by_user[self.user], 0)

        completion.refresh_from_db()
        self.assertEqual(completion.points_awarded, 7)
        self.assertEqual(completion.week_start_date, week_start)
        self.assertTrue(WeeklyCompletion.objects.filter(pk=completion.pk).exists())


class HistoryViewTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Smith House")
        self.user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=self.user, household=self.household)

        self.other_household = Household.objects.create(name="Jones House")

        session = self.client.session
        session["user_id"] = self.user.id
        session.save()

    def _make_chore(self, household=None, name="Dishes", points=5):
        return Chore.objects.create(
            household=household or self.household, name=name, room="Kitchen", points=points
        )

    def _complete(
        self,
        user=None,
        household=None,
        chore=None,
        points=5,
        week_start_date=None,
        completed_at=None,
    ):
        household = household or self.household
        user = user or self.user
        chore = chore or self._make_chore(household=household, points=points)
        kwargs = {
            "chore": chore,
            "household": household,
            "user": user,
            "points_awarded": points,
            "week_start_date": week_start_date or current_week_start(),
        }
        if completed_at is not None:
            kwargs["completed_at"] = completed_at
        return WeeklyCompletion.objects.create(**kwargs)

    def test_completion_in_active_household_appears_with_details(self):
        chore = self._make_chore(name="Dishes", points=5)
        completion = self._complete(chore=chore, points=5)

        response = self.client.get("/history/")

        self.assertEqual(response.status_code, 200)
        weeks = response.context["weeks"]
        self.assertEqual(len(weeks), 1)
        rendered_completions = weeks[0]["completions"]
        self.assertEqual(len(rendered_completions), 1)
        rendered = rendered_completions[0]
        self.assertEqual(rendered.user.name, "Alex")
        self.assertEqual(rendered.chore.name, "Dishes")
        self.assertEqual(rendered.points_awarded, 5)
        self.assertEqual(rendered.completed_at, completion.completed_at)

    def test_completion_from_different_household_excluded_even_with_same_name(self):
        same_name_user = User.objects.create(name="Alex")
        HouseholdMember.objects.create(user=same_name_user, household=self.other_household)
        self._complete(user=same_name_user, household=self.other_household, points=10)

        response = self.client.get("/history/")

        weeks = response.context["weeks"]
        self.assertEqual(weeks, [])

    def test_two_weeks_render_as_separate_groups_with_correct_totals(self):
        older_week = current_week_start() - datetime.timedelta(days=7)
        self._complete(points=5, week_start_date=older_week)
        self._complete(points=3, week_start_date=older_week)
        self._complete(points=7, week_start_date=current_week_start())

        response = self.client.get("/history/")

        weeks = response.context["weeks"]
        self.assertEqual(len(weeks), 2)

        current_group = weeks[0]
        older_group = weeks[1]

        self.assertEqual(current_group["week_start_date"], current_week_start())
        self.assertEqual(len(current_group["completions"]), 1)
        self.assertEqual(current_group["total"], 7)

        self.assertEqual(older_group["week_start_date"], older_week)
        self.assertEqual(len(older_group["completions"]), 2)
        self.assertEqual(older_group["total"], 8)

    def test_week_groups_ordered_most_recent_first(self):
        oldest_week = current_week_start() - datetime.timedelta(days=14)
        middle_week = current_week_start() - datetime.timedelta(days=7)
        newest_week = current_week_start()

        self._complete(points=1, week_start_date=middle_week)
        self._complete(points=1, week_start_date=oldest_week)
        self._complete(points=1, week_start_date=newest_week)

        response = self.client.get("/history/")

        weeks = response.context["weeks"]
        week_starts = [week["week_start_date"] for week in weeks]
        self.assertEqual(week_starts, [newest_week, middle_week, oldest_week])

    def test_completions_within_week_ordered_by_completed_at_then_id_descending(self):
        same_timestamp = timezone.now()
        first = self._complete(points=1, completed_at=same_timestamp)
        second = self._complete(points=2, completed_at=same_timestamp)
        third = self._complete(points=3, completed_at=same_timestamp - datetime.timedelta(minutes=5))

        response = self.client.get("/history/")
        weeks = response.context["weeks"]
        self.assertEqual(len(weeks), 1)
        ordered_ids = [c.id for c in weeks[0]["completions"]]
        # second and first share completed_at, so id descending breaks the
        # tie (second was created after first, so has the higher id); third
        # has an earlier completed_at, so it sorts last.
        self.assertEqual(ordered_ids, [second.id, first.id, third.id])

        response_again = self.client.get("/history/")
        ordered_ids_again = [c.id for c in response_again.context["weeks"][0]["completions"]]
        self.assertEqual(ordered_ids_again, ordered_ids)

    def test_current_week_in_progress_completion_appears_alongside_older_weeks(self):
        older_week = current_week_start() - datetime.timedelta(days=7)
        self._complete(points=4, week_start_date=older_week)
        self._complete(points=6, week_start_date=current_week_start())

        response = self.client.get("/history/")

        weeks = response.context["weeks"]
        week_starts = [week["week_start_date"] for week in weeks]
        self.assertIn(current_week_start(), week_starts)
        self.assertEqual(week_starts, [current_week_start(), older_week])

    def test_household_with_no_completions_renders_200_with_empty_weeks(self):
        response = self.client.get("/history/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["weeks"], [])

    def test_no_active_identity_redirects_to_identity(self):
        fresh_client = Client()
        response = fresh_client.get("/history/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/identity/")
