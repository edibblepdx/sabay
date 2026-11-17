from django.contrib.auth import get_user_model

from chat.models import Room, RoomMember

User = get_user_model()


class ChatTestMixin:
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
