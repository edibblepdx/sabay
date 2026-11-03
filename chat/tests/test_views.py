from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chat.models import Message, Room, RoomMember

User = get_user_model()


class TestCaseMixin:
    def setUp(self):
        self.user_prishe = User.objects.create_user(
            username="prishe",
            password="password",
        )
        self.user_ulmia = User.objects.create_user(
            username="ulmia",
            password="password",
        )

        self.room_shared = Room.objects.create()
        self.room_prishe = Room.objects.create()
        self.room_unused = Room.objects.create()

        RoomMember.objects.create(
            user=self.user_prishe,
            room=self.room_shared,
        )
        RoomMember.objects.create(
            user=self.user_ulmia,
            room=self.room_shared,
        )

        RoomMember.objects.create(
            user=self.user_prishe,
            room=self.room_prishe,
        )


class ChatViewTestCase(TestCaseMixin, TestCase):
    def setUp(self):
        super().setUp()

    # Authentication

    def test_index_requires_login(self):
        """Authentication: Index requires login"""
        response = self.client.get(reverse("chat:index"))

        self.assertEqual(response.status_code, 302)

    def test_conversation_requires_login(self):
        """Authentication: Conversation requires login"""
        response = self.client.get(
            reverse("chat:conversation", args=[self.room_shared.pk])
        )

        self.assertEqual(response.status_code, 302)

    # Room Membership

    def test_member_can_access_conversation(self):
        """Membership: can access room"""
        self.client.force_login(self.user_prishe)

        response = self.client.get(
            reverse("chat:conversation", args=[self.room_shared.pk])
        )

        self.assertEqual(response.status_code, 200)

    def test_non_member_cannot_access_conversation(self):
        """Membership: cannot access room"""
        self.client.force_login(self.user_ulmia)

        response = self.client.get(
            reverse("chat:conversation", args=[self.room_prishe.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_nonexistent_room_returns_404(self):
        """Membership: room does not exist"""
        import uuid

        self.client.force_login(self.user_prishe)

        response = self.client.get(reverse("chat:conversation", args=[uuid.uuid7()]))

        self.assertEqual(response.status_code, 404)


class ChatRenderTestCase(TestCaseMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user_prishe)

    # Room Queryset

    def test_joined_rooms_in_queryset(self):
        """Joined rooms returned in room_queryset"""
        response = self.client.get(reverse("chat:index"))

        self.assertCountEqual(
            response.context["room_queryset"],
            [self.room_shared, self.room_prishe],
        )

    def test_rooms_ordered_by_activity(self):
        """Rooms ordered by activity in room_queryset"""
        now = timezone.now()

        Room.objects.filter(pk=self.room_shared.pk).update(
            last_message_at=now - timedelta(hours=1)
        )
        Room.objects.filter(pk=self.room_prishe.pk).update(last_message_at=now)

        response = self.client.get(reverse("chat:index"))
        rooms = list(response.context["room_queryset"])

        self.assertEqual(
            [room.pk for room in rooms],
            [self.room_prishe.pk, self.room_shared.pk],
        )

    def test_annotates_rooms_with_unread_messages(self):
        """Annotate rooms unread in room_queryset"""
        Message.objects.create(
            room=self.room_shared,
            user=self.user_ulmia,
            message="Hello!",
        )

        response = self.client.get(reverse("chat:index"))

        rooms = {room.pk: room for room in response.context["room_queryset"]}

        self.assertTrue(rooms[self.room_shared.pk].has_unread)
        self.assertFalse(rooms[self.room_prishe.pk].has_unread)
