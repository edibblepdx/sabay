import uuid
from django.db import models
from django.db.models.functions import Now
from django.conf import settings


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)


class RoomMember(models.Model):
    pk = models.CompositePrimaryKey("user_id", "room_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(default=Now())
    read_at = models.DateTimeField(default=Now())


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
