from django.contrib import admin
from chat.models import Room, RoomMember


class RoomAdmin(admin.ModelAdmin):
    pass


class RoomMemberAdmin(admin.ModelAdmin):
    pass


admin.site.register(Room, RoomAdmin)
admin.site.register(RoomMember, RoomMemberAdmin)
