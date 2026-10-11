from django.db import models
from django.db.models.functions import Now
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Room(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(default=Now())


class RoomMember(models.Model):
    pk = models.CompositePrimaryKey("user_id", "room_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(default=Now())


class RoomEvent(models.Model):
    class Type(models.TextChoices):
        JOIN = "JOIN", _("Member joined")
        LEAVE = "LEAVE", _("Member left")

    type = models.CharField(max_length=5, choices=Type)
    created_at = models.DateTimeField(auto_now_add=True)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )


class Message(models.Model):
    message = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
