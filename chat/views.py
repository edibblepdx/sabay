from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from chat.models import Room, RoomMember


@login_required
def index(request):
    room_queryset = Room.objects.all()
    return render(request, "chat/index.html", {"room_queryset": room_queryset})


@login_required
def basic(request):
    return render(request, "chat/basic.html")


@login_required
def room(request, room_id):
    # Check room membership
    _ = get_object_or_404(RoomMember, user=request.user, room=room_id)
    return render(request, "chat/room.html", {"room_id": room_id})
