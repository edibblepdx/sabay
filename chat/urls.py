from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.index, name="index"),
    path("<uuid:room_id>/", views.conversation, name="conversation"),
    path(
        "<uuid:room_id>/profile-card/<str:role>/",
        views.profile_card,
        name="profile_card",
    ),
    path(
        "<uuid:room_id>/mobile-banner/",
        views.mobile_banner,
        name="mobile_banner",
    ),
]
