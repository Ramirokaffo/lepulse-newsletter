from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'object_type', 'object_id', 'created_at')
    list_filter = ('action', 'object_type', 'created_at')
    search_fields = ('description', 'object_id', 'user__username')
    readonly_fields = (
        'user', 'action', 'object_type', 'object_id', 'description',
        'ip_address', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False