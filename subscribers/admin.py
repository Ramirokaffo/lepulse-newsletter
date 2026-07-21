from django.contrib import admin

from .models import Segment, Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'status', 'consent', 'created_at')
    list_filter = ('status', 'consent', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')
    readonly_fields = ('confirmation_token', 'unsubscribe_token', 'created_at')


admin.site.register(Segment)