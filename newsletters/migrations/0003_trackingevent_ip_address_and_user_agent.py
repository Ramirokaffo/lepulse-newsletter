from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('newsletters', '0002_alter_campaign_options_campaign_cancelled_at_and_more')]

    operations = [
        migrations.AddField(
            model_name='trackingevent',
            name='ip_address',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='trackingevent',
            name='user_agent',
            field=models.CharField(blank=True, max_length=300),
        ),
    ]