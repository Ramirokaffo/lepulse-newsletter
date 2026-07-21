import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


class Subscriber(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        ACTIVE = 'active', 'Actif'
        UNSUBSCRIBED = 'unsubscribed', 'Désinscrit'

    class Source(models.TextChoices):
        PUBLIC = 'public', 'Formulaire public'
        MANUAL = 'manual', 'Ajout manuel'
        IMPORT = 'import', 'Import CSV'

    email = models.EmailField('adresse e-mail', unique=True)
    first_name = models.CharField('prénom', max_length=100, blank=True)
    last_name = models.CharField('nom', max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.PUBLIC)
    consent = models.BooleanField('consentement', default=False)
    notes = models.TextField(blank=True)
    consented_at = models.DateTimeField('consentement donné le', null=True, blank=True)
    confirmed_at = models.DateTimeField('confirmé le', null=True, blank=True)
    unsubscribed_at = models.DateTimeField('désinscrit le', null=True, blank=True)
    created_at = models.DateTimeField('créé le', auto_now_add=True)
    updated_at = models.DateTimeField('modifié le', auto_now=True)
    anonymized_at = models.DateTimeField('anonymisé le', null=True, blank=True)
    confirmation_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    unsubscribe_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'abonné'
        verbose_name_plural = 'abonnés'

    def __str__(self):
        return self.email

    def confirm(self):
        if self.status == self.Status.PENDING:
            self.status = self.Status.ACTIVE
            self.confirmed_at = timezone.now()
            self.save(update_fields=['status', 'confirmed_at'])
            SubscriptionEvent.objects.create(subscriber=self, event_type='confirmed')

    def unsubscribe(self):
        self.status = self.Status.UNSUBSCRIBED
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=['status', 'unsubscribed_at'])
        SubscriptionEvent.objects.create(subscriber=self, event_type='unsubscribed')

    def anonymize(self):
        self.email = f'anonymized-{self.pk}@invalid.local'
        self.first_name = ''
        self.last_name = ''
        self.notes = ''
        self.status = self.Status.UNSUBSCRIBED
        self.consent = False
        self.anonymized_at = timezone.now()
        self.unsubscribe_token = uuid.uuid4()
        self.confirmation_token = uuid.uuid4()
        self.save()
        SubscriptionEvent.objects.create(subscriber=self, event_type='anonymized')


class Segment(models.Model):
    class Rule(models.TextChoices):
        MANUAL = 'manual', 'Sélection manuelle'
        ACTIVE = 'active', 'Tous les abonnés actifs'
        RECENT = 'recent', 'Abonnés récents'
        OPENED = 'opened', 'Ayant ouvert une campagne'
        NEVER_OPENED = 'never_opened', 'N’ayant jamais ouvert'

    name = models.CharField('nom', max_length=120, unique=True)
    description = models.TextField(blank=True)
    rule = models.CharField(max_length=30, choices=Rule.choices, default=Rule.MANUAL)
    rule_days = models.PositiveSmallIntegerField('nombre de jours', default=30)
    rule_campaign_id = models.PositiveBigIntegerField('campagne', null=True, blank=True)
    subscribers = models.ManyToManyField(Subscriber, blank=True, related_name='segments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'segment'
        verbose_name_plural = 'segments'

    def __str__(self):
        return self.name

    def get_subscribers(self):
        queryset = Subscriber.objects.filter(status=Subscriber.Status.ACTIVE, consent=True)
        if self.rule == self.Rule.MANUAL:
            return queryset.filter(segments=self)
        if self.rule == self.Rule.RECENT:
            return queryset.filter(created_at__gte=timezone.now() - timedelta(days=self.rule_days))
        if self.rule == self.Rule.OPENED:
            return queryset.filter(
                deliveries__campaign_id=self.rule_campaign_id,
                deliveries__opened_at__isnull=False,
            ).distinct()
        if self.rule == self.Rule.NEVER_OPENED:
            return queryset.exclude(deliveries__opened_at__isnull=False).distinct()
        return queryset

    @property
    def member_count(self):
        return self.get_subscribers().count()


class SubscriptionEvent(models.Model):
    class Type(models.TextChoices):
        SUBSCRIBED = 'subscribed', 'Inscription'
        CONFIRMED = 'confirmed', 'Confirmation'
        UNSUBSCRIBED = 'unsubscribed', 'Désinscription'
        IMPORTED = 'imported', 'Import CSV'
        UPDATED = 'updated', 'Modification'
        ANONYMIZED = 'anonymized', 'Anonymisation'

    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=30, choices=Type.choices)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_event_type_display()} · {self.subscriber}'