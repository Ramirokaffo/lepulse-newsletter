import uuid
import csv
import io

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from core.email import attach_brand_logo
from core.audit import log_action
from core.permissions import administrator_required

from .forms import BulkSegmentForm, SegmentForm, SubscriberForm, SubscriberImportForm, SubscriptionForm
from .models import Segment, Subscriber, SubscriptionEvent

staff_required = administrator_required


def subscribe(request):
    if request.method != 'POST':
        return redirect('core:home')
    form = SubscriptionForm(request.POST)
    if not form.is_valid():
        return render(request, 'core/home.html', {'form': form, 'latest_newsletters': []}, status=400)

    email = form.cleaned_data['email']
    subscriber, created = Subscriber.objects.get_or_create(email=email, defaults={
        'first_name': form.cleaned_data['first_name'], 'consent': True,
        'consented_at': timezone.now(),
    })
    if subscriber.status == Subscriber.Status.ACTIVE:
        messages.info(request, 'Cette adresse est déjà abonnée à Le Pulse.')
        return redirect('core:home')

    if not created:
        subscriber.first_name = form.cleaned_data['first_name']
        subscriber.consent = True
        subscriber.consented_at = timezone.now()
        subscriber.status = Subscriber.Status.PENDING
        subscriber.confirmation_token = uuid.uuid4()
        subscriber.save()
    else:
        SubscriptionEvent.objects.create(subscriber=subscriber, event_type='subscribed')

    confirmation_url = request.build_absolute_uri(
        reverse('subscribers:confirm', args=[subscriber.confirmation_token])
    )
    text_body = (
        f'Bonjour {subscriber.first_name or ""},\n\n'
        f'Confirmez votre inscription : {confirmation_url}\n\n'
        'Accent Média & Technologies'
    )
    html_body = render_to_string('subscribers/confirmation_email.html', {
        'subscriber': subscriber,
        'confirmation_url': confirmation_url,
    })
    message = EmailMultiAlternatives(
        'Confirmez votre inscription à Le Pulse',
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [subscriber.email],
    )
    message.attach_alternative(html_body, 'text/html')
    attach_brand_logo(message)
    message.send(fail_silently=False)
    return render(request, 'subscribers/result.html', {
        'title': 'Encore une étape',
        'message': 'Consultez votre boîte e-mail et cliquez sur le lien de confirmation.',
    })


def confirm(request, token):
    try:
        clean_token = uuid.UUID(str(token).replace('=', ''))
    except (ValueError, AttributeError):
        raise Http404('Lien de confirmation invalide')
    subscriber = get_object_or_404(Subscriber, confirmation_token=clean_token)
    subscriber.confirm()
    return render(request, 'subscribers/result.html', {
        'title': 'Bienvenue dans Le Pulse !',
        'message': 'Votre inscription est confirmée. Vous recevrez notre prochaine édition.',
    })


def unsubscribe(request, token):
    subscriber = get_object_or_404(Subscriber, unsubscribe_token=token)
    if request.method == 'POST':
        subscriber.unsubscribe()
        return render(request, 'subscribers/result.html', {
            'title': 'Désinscription confirmée',
            'message': 'Votre adresse a été retirée de nos prochaines diffusions.',
        })
    return render(request, 'subscribers/unsubscribe.html', {'subscriber': subscriber})


@staff_required
def subscriber_list(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    subscribers = Subscriber.objects.all()
    if query:
        subscribers = subscribers.filter(Q(email__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
    if status:
        subscribers = subscribers.filter(status=status)
    page = Paginator(subscribers, 50).get_page(request.GET.get('page'))
    return render(request, 'subscribers/list.html', {
        'subscribers': page, 'page_obj': page, 'query': query,
        'selected_status': status, 'statuses': Subscriber.Status.choices,
        'segments': Segment.objects.all(),
    })


@staff_required
def subscriber_detail(request, pk):
    subscriber = get_object_or_404(Subscriber, pk=pk)
    return render(request, 'subscribers/detail.html', {
        'subscriber': subscriber,
        'events': subscriber.events.all()[:30],
        'deliveries': subscriber.deliveries.select_related('campaign')[:30],
    })


@staff_required
def subscriber_edit(request, pk=None):
    subscriber = get_object_or_404(Subscriber, pk=pk) if pk else None
    form = SubscriberForm(request.POST or None, instance=subscriber)
    if request.method == 'POST' and form.is_valid():
        subscriber = form.save(commit=False)
        if subscriber.consent and not subscriber.consented_at:
            subscriber.consented_at = timezone.now()
        if not subscriber.pk:
            subscriber.source = Subscriber.Source.MANUAL
        subscriber.save()
        SubscriptionEvent.objects.create(subscriber=subscriber, event_type='updated')
        log_action(request, 'subscriber.saved', subscriber, 'Fiche abonné mise à jour')
        messages.success(request, 'Abonné enregistré.')
        return redirect('subscribers:detail', subscriber.pk)
    return render(request, 'subscribers/form.html', {'form': form, 'subscriber': subscriber})


@staff_required
def subscriber_anonymize(request, pk):
    subscriber = get_object_or_404(Subscriber, pk=pk)
    if request.method == 'POST':
        subscriber.anonymize()
        log_action(request, 'subscriber.anonymized', subscriber, 'Demande RGPD')
        messages.success(request, 'Les données personnelles ont été anonymisées.')
    return redirect('subscribers:detail', pk)


@staff_required
def subscriber_export(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="abonnes-le-pulse.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['email', 'first_name', 'last_name', 'status', 'consent', 'source', 'created_at'])
    for subscriber in Subscriber.objects.all():
        writer.writerow([
            subscriber.email, subscriber.first_name, subscriber.last_name,
            subscriber.status, subscriber.consent, subscriber.source, subscriber.created_at,
        ])
    log_action(request, 'subscribers.exported', description='Export CSV des abonnés')
    return response


def _parse_csv(upload):
    try:
        content = upload.read().decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValidationError('Le fichier doit être encodé en UTF-8.') from error
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or 'email' not in reader.fieldnames:
        raise ValidationError('La colonne email est obligatoire.')
    rows, errors = [], []
    for number, raw in enumerate(reader, start=2):
        if len(rows) >= 1000:
            errors.append('Import limité aux 1 000 premières lignes.')
            break
        email = (raw.get('email') or '').strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            errors.append(f'Ligne {number} : adresse e-mail invalide.')
            continue
        consent = (raw.get('consent') or '').strip().lower() in ('1', 'true', 'yes', 'oui', 'o')
        rows.append({
            'email': email,
            'first_name': (raw.get('first_name') or '').strip()[:100],
            'last_name': (raw.get('last_name') or '').strip()[:100],
            'consent': consent,
            'segment': (raw.get('segment') or '').strip()[:120],
        })
    return rows, errors


@staff_required
def subscriber_import(request):
    form = SubscriberImportForm()
    rows, errors = [], []
    if request.method == 'POST' and request.POST.get('action') == 'preview':
        form = SubscriberImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                rows, errors = _parse_csv(form.cleaned_data['file'])
                request.session['subscriber_import_rows'] = rows
            except ValidationError as error:
                form.add_error('file', error)
    elif request.method == 'POST' and request.POST.get('action') == 'confirm':
        rows = request.session.pop('subscriber_import_rows', [])
        created_count = updated_count = skipped_count = 0
        for row in rows:
            subscriber = Subscriber.objects.filter(email=row['email']).first()
            if subscriber and subscriber.status == Subscriber.Status.UNSUBSCRIBED:
                skipped_count += 1
                continue
            if not subscriber:
                subscriber = Subscriber(
                    email=row['email'], source=Subscriber.Source.IMPORT,
                    status=Subscriber.Status.ACTIVE if row['consent'] else Subscriber.Status.PENDING,
                )
                created_count += 1
            else:
                updated_count += 1
            subscriber.first_name = row['first_name']
            subscriber.last_name = row['last_name']
            subscriber.consent = row['consent']
            if row['consent'] and not subscriber.consented_at:
                subscriber.consented_at = timezone.now()
            subscriber.save()
            SubscriptionEvent.objects.create(subscriber=subscriber, event_type='imported')
            if row['segment']:
                segment, _ = Segment.objects.get_or_create(name=row['segment'])
                segment.subscribers.add(subscriber)
        log_action(request, 'subscribers.imported', description=f'{created_count} créés')
        messages.success(request, f'Import terminé : {created_count} créé(s), {updated_count} mis à jour, {skipped_count} ignoré(s).')
        return redirect('subscribers:list')
    return render(request, 'subscribers/import.html', {
        'form': form, 'rows': rows, 'errors': errors,
    })


@staff_required
def subscriber_bulk_segment(request):
    form = BulkSegmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        segment = form.cleaned_data['segment']
        if segment.rule != Segment.Rule.MANUAL:
            messages.error(request, 'Les membres d’un segment dynamique sont calculés automatiquement.')
        else:
            ids = [value for value in form.cleaned_data['subscriber_ids'].split(',') if value.isdigit()]
            segment.subscribers.add(*Subscriber.objects.filter(pk__in=ids))
            log_action(request, 'segment.members_added', segment, f'{len(ids)} membre(s)')
            messages.success(request, 'Les abonnés ont été ajoutés au segment.')
    return redirect('subscribers:list')


@staff_required
def segment_list(request):
    return render(request, 'subscribers/segment_list.html', {'segments': Segment.objects.all()})


@staff_required
def segment_edit(request, pk=None):
    segment = get_object_or_404(Segment, pk=pk) if pk else None
    form = SegmentForm(request.POST or None, instance=segment)
    if request.method == 'POST' and form.is_valid():
        segment = form.save()
        log_action(request, 'segment.saved', segment, segment.name)
        messages.success(request, 'Segment enregistré.')
        return redirect('subscribers:segment_detail', segment.pk)
    return render(request, 'subscribers/segment_form.html', {'form': form, 'segment': segment})


@staff_required
def segment_detail(request, pk):
    segment = get_object_or_404(Segment, pk=pk)
    return render(request, 'subscribers/segment_detail.html', {
        'segment': segment, 'members': segment.get_subscribers()[:200],
    })


@staff_required
def segment_delete(request, pk):
    segment = get_object_or_404(Segment, pk=pk)
    if request.method == 'POST':
        log_action(request, 'segment.deleted', segment, segment.name)
        segment.delete()
        messages.success(request, 'Segment supprimé.')
    return redirect('subscribers:segment_list')