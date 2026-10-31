import json

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import transaction
from django.utils import timezone

from chat.models import Message, Room, RoomMember


def sync_timestamp_db(func):
    @database_sync_to_async
    @transaction.atomic
    def wrapper(self, *args, **kwargs):
        now = timezone.now()
        room = Room.objects.get(pk=self.room_id)
        room.last_message_at = now
        room.save(update_fields=["last_message_at"])

        return func(self, *args, room=room, now=now, **kwargs)

    return wrapper


class ChatConsumer(AsyncJsonWebsocketConsumer):
    # WebSocket Connect
    async def connect(self):
        self.user_id = self.scope["user"].id
        self.room_id = None

        self.user_group_name = f"user_{self.user_id}"
        self.room_group_name = None

        # Join user group
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        await self.accept()

    # WebSocket disconnect
    async def disconnect(self, close_code):
        # Leave user and room groups
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    # Receive message from WebSocket
    async def receive_json(self, content):
        match content["type"]:
            case "chat.message":
                await self.send_message(content)
            case "room.subscribe":
                await self.subscribe_to_room(content)

    # Receive chat message from room group
    async def chat_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send_json(
            content={
                "type": "chat.message",
                "message": ser_message(message),
            }
        )

    # Receive chat message from user group
    async def room_activity(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send_json(
            content={
                "type": "room.activity",
                "room_id": str(message.room_id),
                "last_message": ser_message(message),
            }
        )

    # Send message to room group
    async def send_message(self, content):
        message = await self.save_message(content["message"])

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "chat.message", "message": message}
        )

        # Notify users of activity
        user_ids = await database_sync_to_async(list)(
            RoomMember.objects.filter(room_id=message.room_id).values_list(
                "user_id", flat=True
            )
        )

        for user_id in user_ids:
            await self.channel_layer.group_send(
                f"user_{user_id}", {"type": "room.activity", "message": message}
            )

    # Subscribe to room group
    async def subscribe_to_room(self, content):
        room_id = content["room_id"]

        # Check membership
        if not await self.is_room_member(room_id):
            await self.send_json(
                {"type": "error", "message": "You are not a member of this room."}
            )
            return

        # Leave previous room
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

        # Join new room
        self.room_id = room_id
        self.room_group_name = f"chat_{self.room_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Send message history
        messages = await self.get_messages()
        await self.send_json(
            content={
                "type": "chat.history",
                "messages": [ser_message(m) for m in messages],
            }
        )

    # Get messages history
    async def get_messages(self):
        room = await Room.objects.aget(pk=self.room_id)
        return [
            message async for message in room.message_set.select_related("user").all()
        ]

    # Save message to database
    @sync_timestamp_db
    def save_message(self, message, *, room, now):
        return Message.objects.create(
            message=message, user=self.scope["user"], room=room, created_at=now
        )

    # Return true if user is a member of the room
    @database_sync_to_async
    def is_room_member(self, room_id):
        return RoomMember.objects.filter(user_id=self.user_id, room_id=room_id).exists()


# Serialize message
def ser_message(m):
    return {
        "room_id": str(m.room_id),
        "message": m.message,
        "username": m.user.username,
        "created_at": m.created_at.isoformat(),
    }
