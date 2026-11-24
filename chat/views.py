from django.contrib.auth.decorators import login_required
from django.db.models import (
    Count,
    Exists,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.db import transaction
from django.contrib.auth import get_user_model

from booking.models import JobPost, JobReq
from chat.models import Message, Room, RoomMember

User = get_user_model()


def render_chat(request, template_name, context=None, **kwargs):
    user = request.user
    context = context or {}

    room_id = context.get("room_id")

    member = (
        get_object_or_404(RoomMember, room_id=room_id, user=user) if room_id else None
    )

    room = member.room if member else None

    room_meta = (
        {
            "role": member.role,
        }
        if room
        else {
            "role": None,
        }
    )

    context = {
        **context,
        "room_meta": room_meta,
        "room_queryset": build_room_queryset(user, room_id),
    }

    return render(request, template_name, context, **kwargs)


def get_provider(room):
    member = (
        RoomMember.objects.filter(
            room=room,
            role=RoomMember.Role.PROVIDER,
        )
        .select_related("user")
        .first()
    )

    user = member.user if member else None

    profile = getattr(user, "provider_profile", None) if user else None

    return {
        "provider": {
            "user": user,
            "profile": profile,
        },
    }


def get_seeker(room):
    member = (
        RoomMember.objects.filter(
            room=room,
            role=RoomMember.Role.SEEKER,
        )
        .select_related("user")
        .first()
    )

    user = member.user if member else None

    profile = getattr(user, "seeker_profile", None) if user else None

    return {
        "seeker": {
            "user": user,
            "profile": profile,
        }
    }


def build_room_queryset(user, current_room_id):
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

    accepted_requests = JobPost.objects.filter(
        seeker__user_id=OuterRef("seeker_user_id"),
        provider__user_id=OuterRef("provider_user_id"),
        status="accepted",
    )

    seeker_requests = JobPost.objects.filter(
        seeker__user_id=OuterRef("seeker_user_id"),
        provider__user_id=OuterRef("provider_user_id"),
        status="open",
    )

    provider_requests = JobReq.objects.filter(
        job__seeker__user_id=OuterRef("seeker_user_id"),
        provider__user_id=OuterRef("provider_user_id"),
        job__status="open",
        dismissed=False,
        status="pending",
    )

    def request_count(queryset):
        return Subquery(
            queryset.annotate(total=Count("pk")).values("total")[:1],
        )

    accepted_request_count = request_count(accepted_requests)
    seeker_request_count = request_count(seeker_requests)
    provider_request_count = request_count(provider_requests)

    def request_type(queryset, field):
        return Subquery(queryset.order_by("-created_at").values(field)[:1])

    accepted_request_type = request_type(accepted_requests, "task_type")
    seeker_request_type = request_type(seeker_requests, "task_type")
    provider_request_type = request_type(provider_requests, "job__task_type")

    room_queryset = (
        (
            Room.objects.filter(
                Q(last_message_at__isnull=False) | Q(pk=current_room_id),
                roommember__user=user,
            )
            .annotate(
                # User and Room meta
                read_at=Subquery(read_at),
                last_message=Subquery(last_message),
            )
            .annotate(
                # Role ids
                seeker_user_id=Subquery(seeker_user_id),
                provider_user_id=Subquery(provider_user_id),
            )
            .annotate(
                # Request counts
                accepted_request_count=accepted_request_count,
                seeker_request_count=seeker_request_count,
                provider_request_count=provider_request_count,
            )
            .annotate(
                # Request count sums
                total_request_count=(
                    Coalesce(accepted_request_count, Value(0))
                    + Coalesce(seeker_request_count, Value(0))
                    + Coalesce(provider_request_count, Value(0))
                ),
                pending_request_count=(
                    Coalesce(seeker_request_count, Value(0))
                    + Coalesce(provider_request_count, Value(0))
                ),
            )
            .annotate(
                # Request types
                accepted_request_type=accepted_request_type,
                seeker_request_type=seeker_request_type,
                provider_request_type=provider_request_type,
            )
            .annotate(
                # Exists queries
                has_unread=Exists(unread_messages),
                has_accepted_request=Q(accepted_request_count__gt=0),
                has_pending_request=Q(pending_request_count__gt=0),
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


@login_required
def profile_card(request, room_id, role):
    member = get_object_or_404(RoomMember, user=request.user, room_id=room_id)
    room = member.room

    # Get the other person's information
    if role == RoomMember.Role.SEEKER:
        person = get_seeker(room)["seeker"]
        role = "seeker"
    elif role == RoomMember.Role.PROVIDER:
        person = get_provider(room)["provider"]
        role = "provider"
    else:
        person = None
        role = None

    return render(
        request,
        "chat/partials/_profile_card.html#profile_card",
        {
            "person": person,
            "role": role,
        },
    )


@login_required
def mobile_banner(request, room_id):
    room = build_room_queryset(request.user).filter(id=room_id).first()

    return render(
        request,
        "chat/partials/_mobile_banner.html#mobile_banner_info",
        {"room": room},
    )


@login_required
@require_POST
@transaction.atomic
def new(request):
    other_user = get_object_or_404(
        User,
        pk=request.POST.get("user_id"),
    )

    if other_user == request.user:
        return redirect("chat")

    # Look for existing room

    current_user_membership = RoomMember.objects.filter(
        room=OuterRef("pk"),
        user=request.user,
    )

    other_user_membership = RoomMember.objects.filter(
        room=OuterRef("pk"),
        user=other_user,
    )

    room = (
        Room.objects.annotate(
            has_current_user=Exists(current_user_membership),
            has_other_user=Exists(other_user_membership),
            member_count=Count("roommember"),
        )
        .filter(
            has_current_user=True,
            has_other_user=True,
            member_count=2,
        )
        .first()
    )

    if room:
        return redirect("chat:conversation", room_id=room.pk)

    # Create new room

    room = Room.objects.create()

    RoomMember.objects.create(
        room=room,
        user=request.user,
        role=RoomMember.Role.SEEKER,
    )
    RoomMember.objects.create(
        room=room,
        user=other_user,
        role=RoomMember.Role.PROVIDER,
    )

    return redirect("chat:conversation", room_id=room.pk)
