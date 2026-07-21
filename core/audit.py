from .models import AuditLog


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')


def log_action(request, action, obj=None, description=''):
    return AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        object_type=obj._meta.label if obj else '',
        object_id=str(obj.pk) if obj and obj.pk else '',
        description=description[:500],
        ip_address=get_client_ip(request) or None,
    )