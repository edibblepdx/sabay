import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Now
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)


class RoomMember(models.Model):
    class Role(models.TextChoices):
        SEEKER = "seeker", _("Seeker")
        PROVIDER = "provider", _("Provider")
        COORDINATOR = "coordinator", _("Coordinator")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(default=timezone.now)  # keep modifiable
    read_at = models.DateTimeField(default=timezone.now)  # keep modifiable
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "room"],
                name="unique_user_room_pair",
            ),
            models.UniqueConstraint(
                fields=["room"],
                condition=models.Q(role="seeker"),
                name="unique_seeker_per_room",
            ),
            models.UniqueConstraint(
                fields=["room"],
                condition=models.Q(role="provider"),
                name="unique_provider_per_room",
            ),
        ]

    def save(self, *args, **kwargs):
        if self._state.adding:
            now = timezone.now()
            self.joined_at = now
            self.read_at = now

        super().save(*args, **kwargs)


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    message = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=Now())
