from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef, Subquery, Prefetch
from django.shortcuts import get_object_or_404, render

from chat.models import Message, Room, RoomMember


def render_chat(request, template_name, context=None, **kwargs):
    user = request.user

    member_read_at = RoomMember.objects.filter(
        room=OuterRef("pk"),
        user=user,
    ).values("read_at")[:1]

    unread_messages = Message.objects.filter(
        room=OuterRef("pk"),
        created_at__gt=OuterRef("member_read_at"),
    ).exclude(user=user)

    last_message = Message.objects.filter(
        room=OuterRef("pk"),
    ).order_by("-created_at")

    room_queryset = (
        Room.objects.filter(roommember__user=user)
        .annotate(member_read_at=Subquery(member_read_at))
        .annotate(has_unread=Exists(unread_messages))
        .annotate(last_message=Subquery(last_message.values("message")[:1]))
    )

    context = {
        **(context or {}),
        "room_queryset": room_queryset.prefetch_related(
            Prefetch(
                "roommember_set",
                queryset=RoomMember.objects.exclude(user=user).select_related("user"),
                to_attr="other_members",
            )
        ).order_by("-last_message_at"),
    }

    return render(request, template_name, context, **kwargs)


@login_required
def index(request):
    return render_chat(request, "chat/index.html")


@login_required
def conversation(request, room_id):
    # Check room membership
    _ = get_object_or_404(RoomMember, user=request.user, room_id=room_id)
    return render_chat(request, "chat/index.html", {"room_id": room_id})
