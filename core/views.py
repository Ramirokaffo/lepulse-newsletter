from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import AuditLog
from .permissions import administrator_required, staff_required
from .stats import activity_series


def home(request):
    from newsletters.models import Newsletter
    from subscribers.forms import SubscriptionForm

    return render(request, 'core/home.html', {
        'form': SubscriptionForm(),
        'latest_newsletters': Newsletter.objects.filter(status='published')[:3],
    })


@staff_required
def dashboard(request):
    from newsletters.models import Campaign, Delivery, Newsletter, TrackingEvent
    from subscribers.models import Subscriber

    deliveries = Delivery.objects.all()
    total_sent = deliveries.filter(status='sent').count()
    return render(request, 'core/dashboard.html', {
        'subscriber_count': Subscriber.objects.filter(status='active').count(),
        'newsletter_count': Newsletter.objects.count(),
        'campaign_count': Campaign.objects.filter(status='sent').count(),
        'open_rate': round(deliveries.filter(opened_at__isnull=False).count() * 100 / total_sent, 1) if total_sent else 0,
        'recent_campaigns': Campaign.objects.select_related('newsletter')[:5],
        'activity': activity_series(TrackingEvent.objects.all(), days=7),
    })


@staff_required
def statistics(request):
    from newsletters.models import Campaign, TrackingEvent

    campaigns = Campaign.objects.filter(status=Campaign.Status.SENT).select_related(
        'newsletter', 'segment'
    )[:50]
    return render(request, 'core/statistics.html', {
        'campaigns': campaigns,
        'activity': activity_series(TrackingEvent.objects.all(), days=14),
    })


@administrator_required
def audit_log(request):
    logs = AuditLog.objects.select_related('user')
    query = request.GET.get('q', '').strip()
    action = request.GET.get('action', '').strip()
    if query:
        logs = logs.filter(
            Q(description__icontains=query)
            | Q(object_type__icontains=query)
            | Q(user__username__icontains=query)
        )
    if action:
        logs = logs.filter(action=action)
    actions = AuditLog.objects.order_by('action').values_list('action', flat=True).distinct()
    return render(request, 'core/audit_log.html', {
        'logs': Paginator(logs, 50).get_page(request.GET.get('page')),
        'actions': actions,
        'query': query,
        'selected_action': action,
    })