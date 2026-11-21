from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef, Subquery, Prefetch
from django.shortcuts import get_object_or_404, render

from chat.models import Message, Room, RoomMember
from booking.models import JobPost, JobReq


def render_chat(request, template_name, context=None, **kwargs):
    user = request.user
    context = context or {}

    room_id = context.get("room_id")

    room = (
        get_object_or_404(
            Room,
            pk=room_id,
            roommember__user=user,
        )
        if room_id
        else None
    )

    context = {
        **context,
        "user_profiles": get_user_profiles(user),
        "room_queryset": build_room_queryset(user),
        "job_context": get_room_job_context(room) if room else None,
    }

    return render(request, template_name, context, **kwargs)


def get_user_profiles(user):
    return {
        "provider": getattr(user, "provider_profile", None),
        "seeker": getattr(user, "seeker_profile", None),
    }


def build_room_queryset(user):
    role = RoomMember.objects.filter(
        room=OuterRef("pk"),
        user=user,
    ).values("role")[:1]

    read_at = RoomMember.objects.filter(
        room=OuterRef("pk"),
        user=user,
    ).values("read_at")[:1]

    unread_messages = Message.objects.filter(
        room=OuterRef("pk"),
        created_at__gt=OuterRef("read_at"),
    ).exclude(user=user)

    last_message = (
        Message.objects.filter(
            room=OuterRef("pk"),
        )
        .order_by("-created_at")
        .values("message")[:1]
    )

    seeker_user_id = RoomMember.objects.filter(
        room=OuterRef("pk"),
        role=RoomMember.Role.SEEKER,
    ).values("user_id")[:1]

    provider_user_id = RoomMember.objects.filter(
        room=OuterRef("pk"),
        role=RoomMember.Role.PROVIDER,
    ).values("user_id")[:1]

    accepted_request_type = JobPost.objects.filter(
        seeker__user_id=OuterRef("seeker_user_id"),
        provider__user_id=OuterRef("provider_user_id"),
        status="accepted",
    ).values("task_type")[:1]

    seeker_request_type = JobPost.objects.filter(
        seeker__user_id=OuterRef("seeker_user_id"),
        provider__user_id=OuterRef("provider_user_id"),
        status="open",
    ).values("task_type")[:1]

    provider_request_type = JobReq.objects.filter(
        job__seeker__user_id=OuterRef("seeker_user_id"),
        provider__user_id=OuterRef("provider_user_id"),
        job__status="open",
        dismissed=False,
        status="pending",
    ).values("job__task_type")[:1]

    room_queryset = (
        (
            Room.objects.filter(roommember__user=user)
            .annotate(
                # User and Room meta
                role=Subquery(role),
                read_at=Subquery(read_at),
                last_message=Subquery(last_message),
            )
            .annotate(
                # Role ids
                seeker_user_id=Subquery(seeker_user_id),
                provider_user_id=Subquery(provider_user_id),
            )
            .annotate(
                # Request types
                accepted_request_type=Subquery(accepted_request_type),
                seeker_request_type=Subquery(seeker_request_type),
                provider_request_type=Subquery(provider_request_type),
            )
            .annotate(
                # Exists queries
                has_unread=Exists(unread_messages),
                has_accepted_request=Exists(accepted_request_type),
                has_pending_request=(
                    Exists(seeker_request_type) | Exists(provider_request_type)
                ),
            )
        )
        .prefetch_related(
            Prefetch(
                "roommember_set",
                queryset=RoomMember.objects.exclude(user=user).select_related("user"),
                to_attr="other_members",
            )
        )
        .order_by("-last_message_at")
    )

    return room_queryset


def get_room_job_context(room):
    members = RoomMember.objects.filter(
        room=room,
        role__in=[
            RoomMember.Role.SEEKER,
            RoomMember.Role.PROVIDER,
        ],
    ).select_related("user")

    participants = {member.role: member.user for member in members}

    seeker_user = participants.get(RoomMember.Role.SEEKER)
    provider_user = participants.get(RoomMember.Role.PROVIDER)

    if not seeker_user or not provider_user:
        return None

    seeker = getattr(seeker_user, "seeker_profile", None)
    provider = getattr(provider_user, "provider_profile", None)

    if not seeker or not provider:
        return None

    return {
        "seeker_requests": JobPost.objects.filter(
            seeker=seeker,
            provider=provider,
            status="open",
        ),
        "provider_requests": JobReq.objects.filter(
            job__seeker=seeker,
            provider=provider,
            job__status="open",
            dismissed=False,
            status="pending",
        ).select_related("job"),
        "accepted_bookings": JobPost.objects.filter(
            seeker=seeker,
            provider=provider,
            status="accepted",
        ),
    }


@login_required
def index(request):
    return render_chat(request, "chat/index.html")


@login_required
def conversation(request, room_id):
    # Check room membership
    _ = get_object_or_404(RoomMember, user=request.user, room_id=room_id)
    return render_chat(request, "chat/index.html", {"room_id": room_id})
