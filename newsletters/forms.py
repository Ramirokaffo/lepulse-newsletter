from django import forms
from django.utils import timezone

from .models import Campaign, Newsletter


class TinyMCETextarea(forms.Textarea):
    """Laisse la validation obligatoire à Django quand TinyMCE masque le champ."""

    def use_required_attribute(self, initial):
        return False


class NewsletterForm(forms.ModelForm):
    class Meta:
        model = Newsletter
        fields = ['title', 'subject', 'summary', 'content', 'cta_label', 'cta_url', 'status']
        widgets = {
            'summary': TinyMCETextarea(attrs={'rows': 3}),
            'content': TinyMCETextarea(attrs={'class': 'tinymce-editor'}),
        }


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'newsletter', 'segment', 'scheduled_at']
        widgets = {'scheduled_at': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

    def clean_scheduled_at(self):
        value = self.cleaned_data.get('scheduled_at')
        if value and value <= timezone.now():
            raise forms.ValidationError('Choisissez une date future.')
        return value


class TestEmailForm(forms.Form):
    email = forms.EmailField(label='Adresse de test')


class ScheduleCampaignForm(forms.Form):
    scheduled_at = forms.DateTimeField(
        label='Date et heure',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )

    def clean_scheduled_at(self):
        value = self.cleaned_data['scheduled_at']
        if value <= timezone.now():
            raise forms.ValidationError('Choisissez une date future.')
        return value