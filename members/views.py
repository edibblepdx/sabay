
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import UserInvite


def login(request):
    error = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            return redirect("dashboard")
        else:
            error = "Invalid username or password"

    return render(request, "auth_logic/login.html", {"error": error})


def signup(request):
    return render(request, "auth_logic/signup.html")


def invite_signup(request, token):
    try:
        invite = UserInvite.objects.get(token=token, used=False)
    except UserInvite.DoesNotExist:
        return render(request, "auth_logic/invalid_invite.html")

    error = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if not username or not password or not confirm_password:
            error = "All fields are required"
        elif password != confirm_password:
            error = "Passwords do not match"
        elif User.objects.filter(username=username).exists():
            error = "Username already exists"
        elif User.objects.filter(email=invite.email).exists():
            error = "Email already exists"
        else:
            with transaction.atomic():
                # Assign the role selected by the admin.
                group, _ = Group.objects.get_or_create(
                    name=invite.get_role_display()
                )

                user = User.objects.create_user(
                    username=username,
                    email=invite.email,
                    password=password,
                )

                user.groups.add(group)

                # Make the invitation unusable after signup.
                invite.used = True
                invite.save(update_fields=["used"])

            return redirect("members:login")

    return render(
        request,
        "auth_logic/invite_signup.html",
        {
            "invite": invite,
            "error": error,
        },
    )


@require_POST
def logout(request):
    auth_logout(request)
    return redirect("home")
