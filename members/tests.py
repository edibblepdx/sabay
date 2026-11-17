
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import UserInvite


class SignupTests(TestCase):
    def test_public_signup_displays_contact_admin_message(self):
        response = self.client.get(reverse("members:signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please contact an admin to sign up.",
        )

    def test_public_signup_cannot_create_user(self):
        response = self.client.post(
            reverse("members:signup"),
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "TestPassword123!",
                "confirm_password": "TestPassword123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username="testuser").exists()
        )


class UserInviteTests(TestCase):
    def setUp(self):
        self.invite = UserInvite.objects.create(
            email="caretaker@example.com",
            role=UserInvite.Role.CARETAKER,
        )

        self.invite_url = reverse(
            "members:invite_signup",
            args=[self.invite.token],
        )

    def signup_with_invite(self, username="testuser"):
        return self.client.post(
            self.invite_url,
            {
                "username": username,
                "password": "TestPassword123!",
                "confirm_password": "TestPassword123!",
            },
        )

    def test_valid_invite_displays_signup_page(self):
        response = self.client.get(self.invite_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "caretaker@example.com")

    def test_invalid_invite_displays_invalid_page(self):
        response = self.client.get(
            reverse(
                "members:invite_signup",
                args=["fake-token"],
            )
        )

        self.assertContains(response, "Invalid Invitation")

    def test_caretaker_signup_creates_user(self):
        response = self.signup_with_invite("caretaker1")

        self.assertTrue(
            User.objects.filter(
                username="caretaker1",
                email="caretaker@example.com",
            ).exists()
        )

        self.assertRedirects(response, reverse("members:login"))

    def test_caretaker_signup_assigns_caretaker_group(self):
        self.signup_with_invite("caretaker1")

        user = User.objects.get(username="caretaker1")

        self.assertTrue(
            user.groups.filter(name="Caretaker").exists()
        )
        self.assertFalse(
            user.groups.filter(name="Careseeker").exists()
        )

    def test_careseeker_signup_assigns_careseeker_group(self):
        self.invite.role = UserInvite.Role.CARESEEKER
        self.invite.save(update_fields=["role"])

        response = self.signup_with_invite("careseeker1")

        user = User.objects.get(username="careseeker1")

        self.assertTrue(
            user.groups.filter(name="Careseeker").exists()
        )
        self.assertFalse(
            user.groups.filter(name="Caretaker").exists()
        )
        self.assertRedirects(response, reverse("members:login"))

    def test_signup_marks_invite_used(self):
        self.signup_with_invite("caretaker1")

        self.invite.refresh_from_db()

        self.assertTrue(self.invite.used)

    def test_used_invite_cannot_be_reused(self):
        self.invite.used = True
        self.invite.save(update_fields=["used"])

        response = self.client.get(self.invite_url)

        self.assertContains(response, "Invalid Invitation")

    def test_invite_cannot_be_used_twice(self):
        self.signup_with_invite("firstuser")

        response = self.signup_with_invite("seconduser")

        self.assertContains(response, "Invalid Invitation")
        self.assertFalse(
            User.objects.filter(username="seconduser").exists()
        )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class UserInviteAdminTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.client.force_login(self.admin)

    def test_admin_rejects_duplicate_active_invite(self):
        UserInvite.objects.create(
            email="duplicate@example.com",
            role=UserInvite.Role.CARETAKER,
        )

        response = self.client.post(
            reverse("admin:members_userinvite_add"),
            {
                "email": "DUPLICATE@example.com",
                "role": UserInvite.Role.CARESEEKER,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "An active invitation already exists for this email.",
        )
        self.assertEqual(
            UserInvite.objects.filter(email__iexact="duplicate@example.com").count(),
            1,
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_rejects_existing_user_email(self):
        User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            reverse("admin:members_userinvite_add"),
            {
                "email": "EXISTING@example.com",
                "role": UserInvite.Role.CARETAKER,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "This email is already registered to an account.",
        )
        self.assertFalse(
            UserInvite.objects.filter(email__iexact="existing@example.com").exists()
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_creating_caretaker_invite_sends_email(self):
        response = self.client.post(
            reverse("admin:members_userinvite_add"),
            {
                "email": "newcaretaker@example.com",
                "role": UserInvite.Role.CARETAKER,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)

        invite = UserInvite.objects.get(
            email="newcaretaker@example.com"
        )

        self.assertEqual(invite.role, UserInvite.Role.CARETAKER)
        self.assertFalse(invite.used)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to,
            ["newcaretaker@example.com"],
        )

        invite_url = reverse(
            "members:invite_signup",
            args=[invite.token],
        )

        self.assertIn(invite_url, mail.outbox[0].body)
        self.assertIn("Caretaker", mail.outbox[0].body)

    def test_admin_creating_careseeker_invite_sends_email(self):
        response = self.client.post(
            reverse("admin:members_userinvite_add"),
            {
                "email": "newcareseeker@example.com",
                "role": UserInvite.Role.CARESEEKER,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)

        invite = UserInvite.objects.get(
            email="newcareseeker@example.com"
        )

        self.assertEqual(invite.role, UserInvite.Role.CARESEEKER)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to,
            ["newcareseeker@example.com"],
        )
        self.assertIn("Careseeker", mail.outbox[0].body)
