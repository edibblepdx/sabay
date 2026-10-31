from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from chat.models import Room, RoomMember


def render_chat(request, template_name, context=None, **kwargs):
    user = request.user

    context = {
        **(context or {}),
        "room_queryset": Room.objects.filter(roommember__user=user)
        .prefetch_related("roommember_set__user")
        .order_by("-last_message_at"),
    }

    return render(request, template_name, context, **kwargs)


@login_required
def index(request):
    return render_chat(request, "chat/index.html")


@login_required
def basic(request):
    return render_chat(request, "chat/basic.html")


@login_required
def conversation(request, room_id):
    # Check room membership
    _ = get_object_or_404(RoomMember, user=request.user, room=room_id)
    return render_chat(request, "chat/conversation.html", {"room_id": room_id})
