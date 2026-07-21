from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import Segment, Subscriber, SubscriptionEvent


class SubscriptionFlowTests(TestCase):
    def test_subscription_sends_confirmation_then_activates(self):
        response = self.client.post(reverse('subscribers:subscribe'), {
            'first_name': 'Amina', 'email': 'AMINA@example.com', 'consent': True,
        })
        self.assertEqual(response.status_code, 200)
        subscriber = Subscriber.objects.get(email='amina@example.com')
        self.assertEqual(subscriber.status, Subscriber.Status.PENDING)
        self.assertTrue(subscriber.consent)
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0].content
        clean_url = reverse('subscribers:confirm', args=[subscriber.confirmation_token])
        self.assertIn(f'href="http://testserver{clean_url}"', html)
        self.assertIn('src="cid:accent-logo"', html)
        mime_types = [part.get_content_type() for part in mail.outbox[0].message().walk()]
        self.assertIn('text/html', mime_types)
        self.assertIn('image/png', mime_types)

        response = self.client.get(reverse('subscribers:confirm', args=[subscriber.confirmation_token]))
        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, Subscriber.Status.ACTIVE)
        self.assertIsNotNone(subscriber.confirmed_at)

    def test_confirmation_accepts_legacy_link_with_equals_sign(self):
        subscriber = Subscriber.objects.create(email='legacy@example.com')
        raw_token = str(subscriber.confirmation_token)
        malformed_token = f'{raw_token[:6]}={raw_token[6:]}'
        response = self.client.get(
            reverse('subscribers:confirm', args=[malformed_token])
        )
        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, Subscriber.Status.ACTIVE)

    def test_unsubscribe_requires_post(self):
        subscriber = Subscriber.objects.create(
            email='active@example.com', status=Subscriber.Status.ACTIVE, consent=True
        )
        url = reverse('subscribers:unsubscribe', args=[subscriber.unsubscribe_token])
        self.assertEqual(self.client.get(url).status_code, 200)
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, Subscriber.Status.ACTIVE)

        self.client.post(url)
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, Subscriber.Status.UNSUBSCRIBED)
        self.assertIsNotNone(subscriber.unsubscribed_at)

    def test_subscriber_list_is_restricted_to_staff(self):
        response = self.client.get(reverse('subscribers:list'))
        self.assertEqual(response.status_code, 302)


class SubscriberManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='audience-admin', password='test-pass', is_staff=True
        )
        self.client.force_login(self.admin)

    def test_csv_preview_and_confirmation_import_subscriber_and_segment(self):
        upload = SimpleUploadedFile(
            'abonnes.csv',
            b'email,first_name,last_name,consent,segment\nlea@example.com,Lea,Nana,oui,Parents\n',
            content_type='text/csv',
        )
        response = self.client.post(reverse('subscribers:import'), {
            'action': 'preview', 'file': upload,
        })
        self.assertContains(response, 'lea@example.com')
        response = self.client.post(reverse('subscribers:import'), {'action': 'confirm'})
        self.assertRedirects(response, reverse('subscribers:list'))
        subscriber = Subscriber.objects.get(email='lea@example.com')
        self.assertEqual(subscriber.status, Subscriber.Status.ACTIVE)
        self.assertTrue(subscriber.consent)
        self.assertTrue(Segment.objects.get(name='Parents').subscribers.filter(pk=subscriber.pk).exists())

    def test_anonymization_removes_personal_data_and_records_event(self):
        subscriber = Subscriber.objects.create(
            email='private@example.com', first_name='Privé', notes='Donnée personnelle',
            status=Subscriber.Status.ACTIVE, consent=True,
        )
        self.client.post(reverse('subscribers:anonymize', args=[subscriber.pk]))
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.email.startswith('anonymized-'))
        self.assertEqual(subscriber.first_name, '')
        self.assertFalse(subscriber.consent)
        self.assertTrue(SubscriptionEvent.objects.filter(
            subscriber=subscriber, event_type=SubscriptionEvent.Type.ANONYMIZED
        ).exists())

    def test_active_and_recent_dynamic_segments_only_return_consenting_members(self):
        active = Subscriber.objects.create(
            email='member@example.com', status=Subscriber.Status.ACTIVE, consent=True
        )
        Subscriber.objects.create(
            email='no-consent@example.com', status=Subscriber.Status.ACTIVE, consent=False
        )
        active_segment = Segment.objects.create(name='Actifs', rule=Segment.Rule.ACTIVE)
        recent_segment = Segment.objects.create(name='Récents', rule=Segment.Rule.RECENT, rule_days=7)
        self.assertEqual(list(active_segment.get_subscribers()), [active])
        self.assertEqual(list(recent_segment.get_subscribers()), [active])