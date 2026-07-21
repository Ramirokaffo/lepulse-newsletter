import csv

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone

from core.audit import get_client_ip, log_action
from core.permissions import administrator_required, staff_required
from core.stats import activity_series

from .forms import CampaignForm, NewsletterForm, ScheduleCampaignForm, TestEmailForm
from .models import Campaign, Delivery, Newsletter, TrackingEvent
from .services import describe_smtp_error, send_campaign, send_test_newsletter

def archive(request):
    items = Newsletter.objects.filter(status=Newsletter.Status.PUBLISHED)
    return render(request, 'newsletters/archive.html', {'newsletters': items})


def detail(request, slug):
    item = get_object_or_404(Newsletter, slug=slug, status=Newsletter.Status.PUBLISHED)
    return render(request, 'newsletters/detail.html', {'newsletter': item})


@staff_required
def newsletter_list(request):
    items = Newsletter.objects.select_related('author')
    return render(request, 'newsletters/list.html', {'newsletters': items})


@staff_required
def newsletter_edit(request, pk=None):
    item = get_object_or_404(Newsletter, pk=pk) if pk else None
    form = NewsletterForm(request.POST or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        newsletter = form.save(commit=False)
        if not newsletter.author_id:
            newsletter.author = request.user
        newsletter.save()
        log_action(request, 'newsletter.saved', newsletter, newsletter.title)
        messages.success(request, 'La newsletter a été enregistrée.')
        return redirect('newsletters:list')
    return render(request, 'newsletters/form.html', {
        'form': form,
        'newsletter': item,
        'tinymce_config': settings.TINYMCE_DEFAULT_CONFIG,
    })


@staff_required
def image_list(request):
    """Point d'entrée attendu par le sélecteur d'images TinyMCE."""
    return JsonResponse([], safe=False)


@staff_required
def campaign_list(request):
    campaigns = Campaign.objects.select_related('newsletter', 'segment')
    return render(request, 'newsletters/campaign_list.html', {'campaigns': campaigns})


@staff_required
def campaign_create(request):
    form = CampaignForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        campaign = form.save(commit=False)
        campaign.created_by = request.user
        if campaign.scheduled_at:
            campaign.status = Campaign.Status.SCHEDULED
        campaign.save()
        log_action(request, 'campaign.created', campaign, campaign.name)
        messages.success(request, 'La campagne est prête à être vérifiée.')
        return redirect('newsletters:campaign_detail', campaign.pk)
    return render(request, 'newsletters/campaign_form.html', {'form': form})


@staff_required
def campaign_detail(request, pk):
    campaign = get_object_or_404(
        Campaign.objects.select_related('newsletter', 'segment'), pk=pk
    )
    error_messages = {
        describe_smtp_error(error)
        for error in campaign.deliveries.exclude(error_message='').values_list(
            'error_message', flat=True
        )
    }
    return render(request, 'newsletters/campaign_detail.html', {
        'campaign': campaign,
        'error_messages': sorted(error_messages),
        'deliveries': campaign.deliveries.select_related('subscriber')[:100],
        'test_form': TestEmailForm(initial={'email': request.user.email}),
        'schedule_form': ScheduleCampaignForm(),
        'can_administer': request.user.is_administrator,
        'activity': activity_series(TrackingEvent.objects.filter(delivery__campaign=campaign)),
        'tracking_events': TrackingEvent.objects.filter(
            delivery__campaign=campaign
        ).select_related('delivery__subscriber')[:50],
    })


@administrator_required
def campaign_send(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if request.method == 'POST':
        try:
            campaign = send_campaign(campaign)
            log_action(request, 'campaign.sent', campaign, campaign.name)
            messages.success(
                request, f'Campagne traitée : {campaign.success_count} e-mail(s) envoyé(s).'
            )
        except ValueError as error:
            messages.error(request, str(error))
    return redirect('newsletters:campaign_detail', pk)


@staff_required
def campaign_preview(request, pk):
    campaign = get_object_or_404(Campaign.objects.select_related('newsletter'), pk=pk)
    return render(request, 'newsletters/email.html', {
        'newsletter': campaign.newsletter,
        'unsubscribe_url': '#',
        'open_url': '',
        'click_url': campaign.newsletter.cta_url or '#',
        'logo_src': static('images/logo-ACCENT.png'),
        'is_test': True,
    })


@staff_required
def campaign_test(request, pk):
    campaign = get_object_or_404(Campaign.objects.select_related('newsletter'), pk=pk)
    form = TestEmailForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            send_test_newsletter(campaign.newsletter, form.cleaned_data['email'])
            campaign.test_sent_at = timezone.now()
            campaign.save(update_fields=['test_sent_at'])
            log_action(request, 'campaign.test_sent', campaign, campaign.name)
            messages.success(request, 'E-mail de test envoyé.')
        except Exception as error:
            messages.error(request, describe_smtp_error(error))
    return redirect('newsletters:campaign_detail', pk)


@administrator_required
def campaign_schedule(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk, status=Campaign.Status.DRAFT)
    form = ScheduleCampaignForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        campaign.scheduled_at = form.cleaned_data['scheduled_at']
        campaign.status = Campaign.Status.SCHEDULED
        campaign.save(update_fields=['scheduled_at', 'status'])
        log_action(request, 'campaign.scheduled', campaign, campaign.name)
        messages.success(request, 'Campagne planifiée.')
    else:
        messages.error(request, 'La date de planification est invalide.')
    return redirect('newsletters:campaign_detail', pk)


@administrator_required
def campaign_cancel(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk, status=Campaign.Status.SCHEDULED)
    if request.method == 'POST':
        campaign.status = Campaign.Status.CANCELLED
        campaign.cancelled_at = timezone.now()
        campaign.save(update_fields=['status', 'cancelled_at'])
        log_action(request, 'campaign.cancelled', campaign, campaign.name)
        messages.success(request, 'Campagne annulée.')
    return redirect('newsletters:campaign_detail', pk)


@administrator_required
def campaign_export(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="campagne-{campaign.pk}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['email', 'statut', 'envoye_le', 'ouvert_le', 'clique_le', 'erreur'])
    for delivery in campaign.deliveries.select_related('subscriber'):
        writer.writerow([
            delivery.subscriber.email, delivery.get_status_display(), delivery.sent_at,
            delivery.opened_at, delivery.clicked_at, delivery.error_message,
        ])
    log_action(request, 'campaign.exported', campaign, campaign.name)
    return response


def track_open(request, token):
    delivery = get_object_or_404(Delivery, token=token)
    if not delivery.opened_at:
        delivery.opened_at = timezone.now()
        delivery.save(update_fields=['opened_at'])
    TrackingEvent.objects.create(
        delivery=delivery,
        event_type=TrackingEvent.Type.OPEN,
        ip_address=get_client_ip(request) or None,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
    )
    pixel = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    response = HttpResponse(pixel, content_type='image/gif')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return response


def track_click(request, token):
    delivery = get_object_or_404(
        Delivery.objects.select_related('campaign__newsletter'), token=token
    )
    if not delivery.clicked_at:
        delivery.clicked_at = timezone.now()
        delivery.save(update_fields=['clicked_at'])
    newsletter = delivery.campaign.newsletter
    TrackingEvent.objects.create(
        delivery=delivery,
        event_type=TrackingEvent.Type.CLICK,
        target_url=newsletter.cta_url,
        ip_address=get_client_ip(request) or None,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
    )
    return redirect(newsletter.cta_url or newsletter.get_absolute_url())