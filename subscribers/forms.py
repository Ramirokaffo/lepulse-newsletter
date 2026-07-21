from django import forms

from .models import Segment, Subscriber


class SubscriptionForm(forms.ModelForm):
    consent = forms.BooleanField(required=True)

    class Meta:
        model = Subscriber
        fields = ['first_name', 'email', 'consent']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Votre prénom', 'autocomplete': 'given-name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Votre adresse e-mail', 'autocomplete': 'email'}),
        }

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class SubscriberForm(forms.ModelForm):
    class Meta:
        model = Subscriber
        fields = ['email', 'first_name', 'last_name', 'status', 'consent', 'source', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 4})}

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class SubscriberImportForm(forms.Form):
    file = forms.FileField(
        label='Fichier CSV',
        help_text='Colonnes : email, first_name, last_name, consent, segment.',
    )

    def clean_file(self):
        file = self.cleaned_data['file']
        if file.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Le fichier ne doit pas dépasser 2 Mo.')
        if not file.name.lower().endswith('.csv'):
            raise forms.ValidationError('Sélectionnez un fichier CSV.')
        return file


class SegmentForm(forms.ModelForm):
    class Meta:
        model = Segment
        fields = ['name', 'description', 'rule', 'rule_days', 'rule_campaign_id']

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('rule') == Segment.Rule.OPENED and not cleaned.get('rule_campaign_id'):
            self.add_error('rule_campaign_id', 'Indiquez la campagne concernée.')
        return cleaned


class BulkSegmentForm(forms.Form):
    subscriber_ids = forms.CharField(widget=forms.HiddenInput)
    segment = forms.ModelChoiceField(queryset=Segment.objects.all(), label='Segment')