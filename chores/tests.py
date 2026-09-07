from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from chores.models import Household, HouseholdMember, User


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
