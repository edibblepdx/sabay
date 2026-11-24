from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import transaction
from django.utils import timezone

from chat.models import Message, Room, RoomMember
from members.models import Provider, Seeker


def room_message_transaction(func):
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
        self.user_id = None
        self.user_group_name = None
        self.room_id = None
        self.room_group_name = None

        self.room_role = None

        user = self.scope["user"]

        if not user.is_authenticated:
            await self.close()
            return

        self.user_id = user.id
        self.user_group_name = f"user_{self.user_id}"

        await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        await self.accept()

    # WebSocket disconnect
    async def disconnect(self, close_code):
        if self.user_group_name:
            await self.channel_layer.group_discard(
                self.user_group_name, self.channel_name
            )

        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    # Receive message from WebSocket
    async def receive_json(self, content):
        match content.get("type"):
            case "chat.message":
                await self.send_message(content)
            case "room.subscribe":
                await self.subscribe_to_room(content)
            case "room.unsubscribe":
                await self.unsubscribe_from_room()
            case "room.read":
                await self.mark_room_read(self.room_id)
            case "ping":
                await self.send_json({"type": "pong"})
            case _:
                await self.send_json(
                    {
                        "type": "error",
                        "message": "Unknown message type.",
                    }
                )

    # Receive chat message from room group
    async def chat_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send_json(
            {
                "type": "chat.message",
                "message": message,
            }
        )

    # Receive chat message from user group
    async def room_activity(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send_json(
            {
                "type": "room.activity",
                "room_id": message["room_id"],
                "last_message": message,
            }
        )

    # Send message to room group
    async def send_message(self, content):
        if self.room_id is None:
            await self.send_json(
                {
                    "type": "error",
                    "message": "You must subscribe to a room first.",
                }
            )
            return

        if not await self.is_room_member(self.room_id):
            await self.unsubscribe_from_room()
            await self.send_json(
                {
                    "type": "error",
                    "message": "You are not a member of this room.",
                }
            )
            return

        message = await self.save_message(content["message"])
        json_message = await ser_message(message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "message": json_message,
            },
        )

        # Notify users of activity
        user_ids = await database_sync_to_async(list)(
            RoomMember.objects.filter(room_id=message.room_id).values_list(
                "user_id", flat=True
            )
        )

        for user_id in user_ids:
            await self.channel_layer.group_send(
                f"user_{user_id}",
                {
                    "type": "room.activity",
                    "message": json_message,
                },
            )

    # Subscribe to room group
    async def subscribe_to_room(self, content):
        room_id = content["room_id"]
        if not room_id or (str(self.room_id) == str(room_id)):
            return

        # Check membership
        if not await self.is_room_member(room_id):
            await self.send_json(
                {
                    "type": "error",
                    "message": "You are not a member of this room.",
                }
            )
            return

        # Leave previous room
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

        # Join new room
        self.room_id = room_id
        self.room_role = await self.get_member_role(self.room_id)
        self.room_group_name = f"chat_{self.room_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Send message history
        messages = await self.get_messages_history()
        read_at = await self.get_read_at()

        await self.send_json(
            {
                "type": "chat.history",
                "room_id": str(self.room_id),
                "room_role": str(self.room_role),
                "messages": [await ser_message(m) for m in messages],
                "read_at": read_at.isoformat() if read_at else None,
            }
        )

        # Mark room read
        await self.mark_room_read(room_id)

    # Unsubscribe from room group
    async def unsubscribe_from_room(self):
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

        self.room_id = None
        self.room_group_name = None

    # Get messages history
    async def get_messages_history(self):
        room = await Room.objects.aget(pk=self.room_id)
        return [
            message
            async for message in (
                room.message_set.select_related("user").order_by("created_at", "id")
            )
        ]

    # Get read date
    async def get_read_at(self):
        return await RoomMember.objects.values_list("read_at", flat=True).aget(
            user_id=self.user_id,
            room_id=self.room_id,
        )

    # Save message to database
    @room_message_transaction
    def save_message(self, message, *, room, now):
        return Message.objects.create(
            message=message,
            user=self.scope["user"],
            room=room,
            created_at=now,
        )

    # Return true if user is a member of the room
    async def is_room_member(self, room_id):
        return await RoomMember.objects.filter(
            user_id=self.user_id,
            room_id=room_id,
        ).aexists()

    # Get member role
    async def get_member_role(self, room_id):
        return await RoomMember.objects.values_list("role", flat=True).aget(
            room_id=room_id,
            user=self.scope["user"],
        )

    # Set read_at field in RoomMember table
    async def mark_room_read(self, room_id):
        if room_id is not None:
            await RoomMember.objects.filter(
                user_id=self.user_id,
                room_id=room_id,
            ).aupdate(read_at=timezone.now())


# Get user profile picture
async def get_profile_picture(user_id):
    profile = await Seeker.objects.filter(user_id=user_id).afirst()

    if profile is None:
        profile = await Provider.objects.filter(user_id=user_id).afirst()

    if not profile:
        return None

    picture = getattr(profile, "profilePicture", None) or getattr(
        profile, "photo", None
    )

    return picture.url if picture else None


# Serialize message
async def ser_message(m):
    # Grab the profile picture as well
    picture = await get_profile_picture(m.user.id) if m.user else None

    return {
        "room_id": str(m.room_id),
        "user_id": str(m.user.id) if m.user else None,
        "user": {
            "username": m.user.username,
            "first_name": m.user.first_name,
            "last_name": m.user.last_name,
            "picture": picture,
        }
        if m.user
        else {
            "username": None,
            "first_name": None,
            "last_name": None,
        },
        "message": m.message,
        "created_at": m.created_at.isoformat(),
    }
