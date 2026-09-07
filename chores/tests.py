import datetime
from unittest.mock import patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from chores.identity import get_current_user, require_identity, set_current_user
from chores.models import Chore, Household, HouseholdMember, User, WeeklyCompletion


class HealthViewTests(TestCase):
    def test_returns_200(self):
        response = self.client.get("/")
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

    def test_successful_submission_redirects_to_health(self):
        response = self.client.post(
            "/identity/",
            {"household_name": "Smith House", "display_name": "Alex"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

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
