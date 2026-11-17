import secrets

from django.db import models


def generate_invite_token():
    return secrets.token_urlsafe(32)


class UserInvite(models.Model):
    class Role(models.TextChoices):
        CARETAKER = "caretaker", "Caretaker"
        CARESEEKER = "careseeker", "Careseeker"

    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CARETAKER,
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_invite_token,
    )
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"