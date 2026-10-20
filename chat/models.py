import uuid
from django.db import models
from django.db.models.functions import Now
from django.conf import settings
from django.utils import timezone


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)


class RoomMember(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(default=timezone.now)  # keep modifiable
    read_at = models.DateTimeField(default=timezone.now)  # keep modifiable

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "room"],
                name="unique_user_room",
            ),
        ]


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    message = models.TextField(blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=Now())
