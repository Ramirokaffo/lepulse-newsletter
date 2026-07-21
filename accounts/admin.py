from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class LePulseUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Le Pulse', {'fields': ('role',)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Le Pulse', {'fields': ('role',)}),)
    list_display = UserAdmin.list_display + ('role',)