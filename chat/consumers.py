import json

from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.db import transaction

from chat.models import Room, Message


def room_activity(func):
    @sync_to_async
    @transaction.atomic
    def wrapper(self, *args, **kwargs):
        now = timezone.now()
        room = Room.objects.get(pk=self.room_id)
        room.last_message_at = now
        room.save(update_fields=["last_message_at"])

        return func(self, *args, room=room, now=now, **kwargs)

    return wrapper


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"chat_{self.room_id}"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        # Send message history
        messages = await self.get_messages()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat.history",
                    "messages": [ser_message(m) for m in messages],
                }
            )
        )

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = await self.save_message(text_data_json["message"])

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "chat.message", "message": message}
        )

    # Receive message from room group
    async def chat_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat.message",
                    "message": ser_message(message),
                }
            )
        )

    # Get messages
    async def get_messages(self):
        room = await Room.objects.aget(pk=self.room_id)
        return [
            message async for message in room.message_set.select_related("user").all()
        ]

    # Save message to database
    @room_activity
    def save_message(self, message, *, room, now):
        return Message.objects.create(
            message=message, user=self.scope["user"], room=room, created_at=now
        )

    def member_join(self):
        pass

    def member_leave(self):
        pass


# Serialize message
def ser_message(m):
    return {
        "message": m.message,
        "username": m.user.username,
        "created_at": m.created_at.isoformat(),
    }
