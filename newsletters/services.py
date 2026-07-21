import logging
import smtplib
from html import unescape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from core.email import attach_brand_logo

from .models import Campaign, Delivery

logger = logging.getLogger(__name__)


def describe_smtp_error(error):
    """Produit un diagnostic utile sans adresse ou détail SMTP sensible."""
    if isinstance(error, str) and error.startswith((
        'Authentification SMTP',
        'Expéditeur refusé',
        'Destinataire refusé',
        'Boîte e-mail indisponible',
        'Connexion au serveur SMTP',
        'Échec SMTP',
    )):
        return error
    text = str(error).lower()
    code = getattr(error, 'smtp_code', None)
    if isinstance(error, smtplib.SMTPAuthenticationError) or code == 535:
        return 'Authentification SMTP refusée (code 535).'
    if isinstance(error, smtplib.SMTPSenderRefused) or any(
        marker in text for marker in ('sender address is not allowed', 'sender refused')
    ):
        return f'Expéditeur refusé par le serveur SMTP (code {code or 550}).'
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return 'Destinataire refusé par le serveur SMTP.'
    if 'mailbox unavailable' in text:
        return f'Boîte e-mail indisponible (code {code or 550}).'
    if isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return 'Connexion au serveur SMTP impossible.'
    return f'Échec SMTP ({type(error).__name__}).'


def send_campaign(campaign):
    """Envoie une campagne une seule fois et journalise chaque destinataire."""
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().select_related('newsletter').get(
            pk=campaign.pk
        )
        allowed = (Campaign.Status.DRAFT, Campaign.Status.FAILED, Campaign.Status.SCHEDULED)
        if campaign.status not in allowed:
            raise ValueError('Cette campagne a déjà été traitée.')
        campaign.status = Campaign.Status.SENDING
        campaign.save(update_fields=['status'])
    recipients = list(campaign.recipients())
    success = failure = 0

    for subscriber in recipients:
        delivery, _ = Delivery.objects.get_or_create(campaign=campaign, subscriber=subscriber)
        if delivery.status == Delivery.Status.SENT:
            continue
        context = {
            'newsletter': campaign.newsletter,
            'subscriber': subscriber,
            'unsubscribe_url': settings.SITE_URL + reverse(
                'subscribers:unsubscribe', args=[subscriber.unsubscribe_token]
            ),
            'open_url': settings.SITE_URL + reverse('newsletters:track_open', args=[delivery.token]),
            'click_url': settings.SITE_URL + reverse('newsletters:track_click', args=[delivery.token]),
        }
        html = render_to_string('newsletters/email.html', context)
        message = EmailMultiAlternatives(
            campaign.newsletter.subject,
            strip_tags(unescape(html)),
            settings.DEFAULT_FROM_EMAIL,
            [subscriber.email],
        )
        message.attach_alternative(html, 'text/html')
        attach_brand_logo(message)
        try:
            message.send(fail_silently=False)
            delivery.status = Delivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.error_message = ''
            success += 1
        except Exception as exc:
            delivery.status = Delivery.Status.FAILED
            delivery.error_message = describe_smtp_error(exc)
            logger.error(
                'Échec envoi campagne_id=%s delivery_id=%s type=%s code=%s',
                campaign.pk,
                delivery.pk,
                type(exc).__name__,
                getattr(exc, 'smtp_code', None),
            )
            failure += 1
        delivery.save()

    success = campaign.deliveries.filter(status=Delivery.Status.SENT).count()
    failure = campaign.deliveries.filter(status=Delivery.Status.FAILED).count()
    campaign.status = Campaign.Status.SENT if not failure else Campaign.Status.FAILED
    campaign.recipient_count = len(recipients)
    campaign.success_count = success
    campaign.failure_count = failure
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=[
        'status', 'recipient_count', 'success_count', 'failure_count', 'sent_at'
    ])
    return campaign


def send_test_newsletter(newsletter, recipient):
    context = {
        'newsletter': newsletter,
        'subscriber': None,
        'unsubscribe_url': '#',
        'open_url': '',
        'click_url': newsletter.cta_url or newsletter.get_absolute_url(),
        'is_test': True,
    }
    html = render_to_string('newsletters/email.html', context)
    message = EmailMultiAlternatives(
        f'[TEST] {newsletter.subject}',
        strip_tags(unescape(html)),
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
    )
    message.attach_alternative(html, 'text/html')
    attach_brand_logo(message)
    return message.send(fail_silently=False)