from contextlib import asynccontextmanager

from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from chat.consumers import ChatConsumer

from .mixins import ChatTestMixin


class ChatConsumerTests(ChatTestMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()

    @asynccontextmanager
    async def connect(self, user=None, path="/ws/chat/"):
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            path,
        )

        if user is not None:
            communicator.scope["user"] = user

        connected, subprotocol = await communicator.connect()

        try:
            yield communicator, connected, subprotocol
        finally:
            if connected:
                await communicator.disconnect()

    async def test_member_can_connect(self):
        async with self.connect(self.user_prishe) as (
            _,
            connected,
            _,
        ):
            self.assertTrue(connected)
