import smtplib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from subscribers.models import Subscriber

from .models import Campaign, Delivery, Newsletter, TrackingEvent
from .services import send_campaign


class NewsletterTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='editor', password='test-pass-123', is_staff=True
        )
        self.newsletter = Newsletter.objects.create(
            title='Édition innovation', subject='Le Pulse de juin',
            summary='Les tendances du mois.', content='<p>Notre contenu</p>',
            cta_label='Découvrir', cta_url='https://accentmedia.cm/',
            status=Newsletter.Status.PUBLISHED, author=self.staff,
        )

    def test_published_newsletter_is_in_public_archive(self):
        response = self.client.get(reverse('newsletters:archive'))
        self.assertContains(response, self.newsletter.title)
        self.assertContains(response, '/static/images/logo-ACCENT.png')
        self.assertContains(self.client.get(self.newsletter.get_absolute_url()), 'Notre contenu')

    def test_editor_is_staff_only_and_uses_tinymce(self):
        url = reverse('newsletters:create')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.staff)
        response = self.client.get(url)
        self.assertContains(response, 'tinymce.min.js')
        self.assertContains(response, "tinymce.init")
        self.assertContains(response, 'tinymce-config')

    def test_staff_can_submit_new_newsletter(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('newsletters:create'), {
            'title': 'Nouvelle édition',
            'subject': 'Le sujet',
            'summary': 'Le résumé',
            'content': '<p>Contenu créé avec TinyMCE</p>',
            'cta_label': '',
            'cta_url': '',
            'status': Newsletter.Status.DRAFT,
        })
        self.assertRedirects(response, reverse('newsletters:list'))
        created = Newsletter.objects.get(title='Nouvelle édition')
        self.assertEqual(created.author, self.staff)

    def test_newsletter_html_is_sanitized_before_storage(self):
        item = Newsletter.objects.create(
            title='Contenu sûr', subject='Test', summary='Résumé', author=self.staff,
            content='<p onclick="alert(1)">Bonjour <strong>équipe</strong></p>'
                    '<script>alert(2)</script><a href="javascript:alert(3)">Lien</a>',
        )
        self.assertIn('<strong>équipe</strong>', item.content)
        self.assertNotIn('onclick', item.content)
        self.assertNotIn('script', item.content)
        self.assertNotIn('javascript:', item.content)

    def test_campaign_targets_only_active_consenting_subscribers(self):
        active = Subscriber.objects.create(
            email='active@example.com', status=Subscriber.Status.ACTIVE, consent=True
        )
        Subscriber.objects.create(
            email='pending@example.com', status=Subscriber.Status.PENDING, consent=True
        )
        Subscriber.objects.create(
            email='optout@example.com', status=Subscriber.Status.ACTIVE, consent=False
        )
        campaign = Campaign.objects.create(
            name='Envoi de juin', newsletter=self.newsletter, created_by=self.staff
        )

        send_campaign(campaign)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.SENT)
        self.assertEqual(campaign.recipient_count, 1)
        self.assertEqual(campaign.success_count, 1)
        self.assertEqual(Delivery.objects.get().subscriber, active)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        html = email.alternatives[0].content
        self.assertEqual(email.alternatives[0].mimetype, 'text/html')
        self.assertIn('Se désinscrire', html)
        self.assertIn('<p>Notre contenu</p>', html)
        self.assertNotIn('&lt;p&gt;Notre contenu&lt;/p&gt;', html)
        self.assertNotIn('<p>Notre contenu</p>', email.body)
        self.assertIn('src="cid:accent-logo"', html)
        mime_types = [part.get_content_type() for part in email.message().walk()]
        self.assertIn('text/plain', mime_types)
        self.assertIn('text/html', mime_types)
        self.assertIn('image/png', mime_types)

        with self.assertRaises(ValueError):
            send_campaign(campaign)

    @patch('newsletters.services.EmailMultiAlternatives.send')
    def test_failed_campaign_shows_smtp_error_and_can_be_retried(self, send):
        subscriber = Subscriber.objects.create(
            email='retry@example.com', status=Subscriber.Status.ACTIVE, consent=True
        )
        campaign = Campaign.objects.create(name='Nouvelle tentative', newsletter=self.newsletter)
        send.side_effect = smtplib.SMTPSenderRefused(
            550, b'Sender address is not allowed', 'sender@example.com'
        )

        with self.assertLogs('newsletters.services', level='ERROR') as logs:
            send_campaign(campaign)
        campaign.refresh_from_db()
        delivery = Delivery.objects.get(campaign=campaign, subscriber=subscriber)
        self.assertEqual(campaign.status, Campaign.Status.FAILED)
        self.assertEqual(
            delivery.error_message,
            'Expéditeur refusé par le serveur SMTP (code 550).',
        )
        self.assertIn('code=550', logs.output[0])
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('newsletters:campaign_detail', args=[campaign.pk])
        )
        self.assertContains(response, 'Expéditeur refusé')
        self.assertContains(response, 'Réessayer les échecs')

        send.side_effect = None
        send.return_value = 1
        send_campaign(campaign)
        campaign.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.SENT)
        self.assertEqual(delivery.status, Delivery.Status.SENT)
        self.assertEqual(campaign.success_count, 1)

    def test_tracking_records_first_open_and_click(self):
        subscriber = Subscriber.objects.create(
            email='reader@example.com', status=Subscriber.Status.ACTIVE, consent=True
        )
        campaign = Campaign.objects.create(name='Suivi', newsletter=self.newsletter)
        delivery = Delivery.objects.create(campaign=campaign, subscriber=subscriber)

        response = self.client.get(
            reverse('newsletters:track_open', args=[delivery.token]),
            HTTP_USER_AGENT='LePulseTest/1.0', REMOTE_ADDR='203.0.113.9',
        )
        self.assertEqual(response['Content-Type'], 'image/gif')
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.opened_at)

        response = self.client.get(reverse('newsletters:track_click', args=[delivery.token]))
        self.assertRedirects(response, self.newsletter.cta_url, fetch_redirect_response=False)
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.clicked_at)
        event = TrackingEvent.objects.filter(event_type=TrackingEvent.Type.OPEN).get()
        self.assertEqual(event.ip_address, '203.0.113.9')
        self.assertEqual(event.user_agent, 'LePulseTest/1.0')

    def test_editor_cannot_send_or_schedule_campaign(self):
        self.staff.role = get_user_model().Role.EDITOR
        self.staff.save(update_fields=['role'])
        campaign = Campaign.objects.create(name='Validation requise', newsletter=self.newsletter)
        self.client.force_login(self.staff)
        send_response = self.client.post(reverse('newsletters:campaign_send', args=[campaign.pk]))
        schedule_response = self.client.post(
            reverse('newsletters:campaign_schedule', args=[campaign.pk]),
            {'scheduled_at': '2099-01-01T10:00'},
        )
        self.assertEqual(send_response.status_code, 302)
        self.assertEqual(schedule_response.status_code, 302)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.DRAFT)