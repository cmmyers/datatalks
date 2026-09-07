import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

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
