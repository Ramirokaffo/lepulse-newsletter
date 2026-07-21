import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from core.html import sanitize_html
from subscribers.models import Segment, Subscriber


class Newsletter(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Brouillon'
        PUBLISHED = 'published', 'Publiée'

    title = models.CharField('titre', max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    subject = models.CharField('objet de l’e-mail', max_length=200)
    summary = models.TextField('résumé', max_length=500)
    content = models.TextField('contenu')
    cta_label = models.CharField('libellé du bouton', max_length=80, blank=True)
    cta_url = models.URLField('lien du bouton', blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='newsletters')
    published_at = models.DateTimeField('publiée le', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.content = sanitize_html(self.content)
        if not self.slug:
            root = slugify(self.title)[:200] or 'newsletter'
            slug, counter = root, 2
            while Newsletter.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug, counter = f'{root}-{counter}', counter + 1
            self.slug = slug
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('newsletters:detail', args=[self.slug])


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Brouillon'
        SCHEDULED = 'scheduled', 'Planifiée'
        SENDING = 'sending', 'En cours'
        SENT = 'sent', 'Envoyée'
        FAILED = 'failed', 'Échec'
        CANCELLED = 'cancelled', 'Annulée'

    name = models.CharField('nom', max_length=180)
    newsletter = models.ForeignKey(Newsletter, on_delete=models.PROTECT, related_name='campaigns')
    segment = models.ForeignKey(Segment, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    recipient_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField('envoi planifié', null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    test_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [('send_campaign', 'Peut envoyer et planifier une campagne')]

    def __str__(self):
        return self.name

    def recipients(self):
        queryset = Subscriber.objects.filter(status=Subscriber.Status.ACTIVE, consent=True)
        return self.segment.get_subscribers() if self.segment_id else queryset

    @property
    def open_count(self):
        return self.deliveries.filter(opened_at__isnull=False).count()

    @property
    def click_count(self):
        return self.deliveries.filter(clicked_at__isnull=False).count()

    @property
    def delivery_rate(self):
        return round(self.success_count * 100 / self.recipient_count, 1) if self.recipient_count else 0

    @property
    def open_rate(self):
        return round(self.open_count * 100 / self.success_count, 1) if self.success_count else 0

    @property
    def click_rate(self):
        return round(self.click_count * 100 / self.success_count, 1) if self.success_count else 0


class Delivery(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        SENT = 'sent', 'Envoyé'
        FAILED = 'failed', 'Échec'

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='deliveries')
    subscriber = models.ForeignKey(Subscriber, on_delete=models.PROTECT, related_name='deliveries')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['campaign', 'subscriber'], name='unique_campaign_delivery')]

    def __str__(self):
        return f'{self.campaign} → {self.subscriber}'


class TrackingEvent(models.Model):
    class Type(models.TextChoices):
        OPEN = 'open', 'Ouverture'
        CLICK = 'click', 'Clic'

    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=Type.choices)
    target_url = models.URLField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_event_type_display()} · {self.delivery}'