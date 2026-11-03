from django.test import TestCase
from django.urls import reverse

from .mixins import ChatTestMixin


class ChatTemplateTestCase(ChatTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user_prishe)

    def test_base_includes_chat_partials(self):
        """Response includes partial templates"""
        response = self.client.get(reverse("chat:index"))

        self.assertTemplateUsed(response, "chat/base.html")
        self.assertTemplateUsed(response, "chat/conversations.html")
        self.assertTemplateUsed(response, "chat/conversation.html")
        self.assertTemplateUsed(response, "chat/details.html")
        self.assertTemplateUsed(response, "chat/suggestions.html")
