import secrets
import string

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


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


class Chore(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLAIMED = "claimed"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLAIMED, "Claimed"),
    ]

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="chores")
    name = models.CharField(max_length=100)
    room = models.CharField(max_length=100)
    points = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    claimed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="claimed_chores"
    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class WeeklyCompletion(models.Model):
    chore = models.ForeignKey(Chore, on_delete=models.PROTECT, related_name="completions")
    household = models.ForeignKey(Household, on_delete=models.PROTECT, related_name="completions")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="completions")
    points_awarded = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    week_start_date = models.DateField()
    completed_at = models.DateTimeField(default=timezone.now)

    def clean(self):
        if self.chore_id and self.household_id and self.household_id != self.chore.household_id:
            raise ValidationError(
                "WeeklyCompletion household must match its chore's household."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.name} completed {self.chore.name} ({self.week_start_date})"
