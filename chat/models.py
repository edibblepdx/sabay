from django.db import models
from django.conf import settings


class Room(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sent_message = models.ForeignKey(
        "Message",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="+",
    )


class RoomMember(models.Model):
    pk = models.CompositePrimaryKey("user_id", "room_id")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    last_read_message = models.ForeignKey(
        "Message",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="+",
    )


class Message(models.Model):
    content = models.CharField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
