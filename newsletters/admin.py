from django.contrib import admin

from .models import Campaign, Delivery, Newsletter


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'author', 'published_at', 'updated_at')
    list_filter = ('status', 'published_at')
    search_fields = ('title', 'subject', 'summary')


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'newsletter', 'status', 'recipient_count', 'sent_at')
    list_filter = ('status', 'sent_at')


admin.site.register(Delivery)