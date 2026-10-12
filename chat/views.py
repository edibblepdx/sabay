from django.shortcuts import render


def index(request):
    return render(request, "chat/index.html")


def basic(request):
    return render(request, "chat/basic.html")


def room(request, room_id):
    return render(request, "chat/room.html", {"room_id": room_id})
