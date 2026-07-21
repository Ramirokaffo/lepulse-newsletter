from django.core.management.base import BaseCommand
from django.utils import timezone

from newsletters.models import Campaign
from newsletters.services import send_campaign


class Command(BaseCommand):
    help = 'Envoie les campagnes planifiées dont la date est arrivée.'

    def handle(self, *args, **options):
        campaigns = Campaign.objects.filter(
            status=Campaign.Status.SCHEDULED,
            scheduled_at__lte=timezone.now(),
        )
        sent = failed = 0
        for campaign in campaigns:
            try:
                result = send_campaign(campaign)
                sent += result.success_count
                failed += result.failure_count
            except ValueError:
                continue
        self.stdout.write(self.style.SUCCESS(
            f'Campagnes traitées. Envoyés : {sent}. Échecs : {failed}.'
        ))