import secrets
import string

from django.core.exceptions import ValidationError
from django.db import models


class User(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


def generate_join_code():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class Household(models.Model):
    name = models.CharField(max_length=100)
    join_code = models.CharField(max_length=16, unique=True, default=generate_join_code)

    def __str__(self):
        return self.name


class HouseholdMember(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="members")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "household"], name="unique_user_household_membership"),
        ]

    def clean(self):
        conflict = (
            HouseholdMember.objects.filter(household=self.household, user__name__iexact=self.user.name)
            .exclude(pk=self.pk)
            .exists()
        )
        if conflict:
            raise ValidationError(
                f"A member named '{self.user.name}' already exists in this household."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.name} @ {self.household.name}"
