from contextlib import asynccontextmanager

from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from chat.consumers import ChatConsumer

from .mixins import ChatTestMixin


class ChatConsumerTests(ChatTestMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()

    @asynccontextmanager
    async def connect(self, user=None, path="/ws/chat/"):
        """Async websocket context"""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            path,
        )

        # User.is_authenticated is always True
        # AnonymousUser.is_authenticated is always False
        communicator.scope["user"] = user or AnonymousUser()

        connected, subprotocol = await communicator.connect()

        try:
            yield communicator, connected, subprotocol
        finally:
            if connected:
                await communicator.disconnect()

    async def test_unauthenticated_user_cannot_connect(self):
        """Unauthenticated users cannot connect"""
        async with self.connect() as (_, connected, _):
            self.assertFalse(connected)

    async def test_authenticated_user_can_connect(self):
        """Authenticated users can connect"""
        async with self.connect(self.user_prishe) as (_, connected, _):
            self.assertTrue(connected)

    async def test_member_can_subscribe(self):
        """Room member can subscribe to room"""
        async with self.connect(self.user_prishe) as (communicator, _, _):
            await communicator.send_json_to(
                {
                    "type": "room.subscribe",
                    "room_id": str(self.room_shared.pk),
                }
            )

            response = await communicator.receive_json_from()

            self.assertEqual(response["type"], "chat.history")
            self.assertEqual(response["room_id"], str(self.room_shared.pk))

    async def test_nonmember_cannot_subscribe(self):
        """Non room member cannot subscribe to room"""
        async with self.connect(self.user_ulmia) as (communicator, _, _):
            await communicator.send_json_to(
                {
                    "type": "room.subscribe",
                    "room_id": str(self.room_prishe.pk),
                }
            )

            response = await communicator.receive_json_from()

            self.assertEqual(response["type"], "error")

    async def test_message_is_received_and_broadcast(self):
        """Message is received and broadcast to room group"""
        async with (
            self.connect(self.user_prishe) as (prishe, _, _),
            self.connect(self.user_ulmia) as (ulmia, _, _),
        ):
            for communicator in (prishe, ulmia):
                await communicator.send_json_to(
                    {
                        "type": "room.subscribe",
                        "room_id": str(self.room_shared.id),
                    }
                )
                await communicator.receive_json_from()

            await prishe.send_json_to(
                {
                    "type": "chat.message",
                    "message": "Hello!",
                }
            )

            sender_response = await prishe.receive_json_from()
            receiver_response = await ulmia.receive_json_from()

            self.assertEqual(sender_response["type"], "chat.message")
            self.assertEqual(receiver_response["type"], "chat.message")
            self.assertEqual(receiver_response["message"]["message"], "Hello!")
