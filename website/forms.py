from django import forms

from .models import ContactMessage, ContactMessageSimple, Review


class StartProjectForm(forms.ModelForm):

    FEATURE_CHOICES = [
        ("booking", "Sistem de rezervări / programări"),
        ("dashboard", "Dashboard de administrare"),
        ("website", "Website de prezentare"),
        ("automation", "Automatizare simplă (confirmări, mesaje de reamintire)"),
        ("ai_agent", "Agent AI (telefon/WhatsApp, conversații)"),
    ]

    required_features = forms.MultipleChoiceField(
        choices=FEATURE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    # Honeypot: real visitors never see or fill this field, bots that
    # auto-fill every input do. Checked (not saved) in the view.
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = ContactMessage
        fields = [
            "name",
            "email",
            "industry",
            "selected_package",
            "project_description",
            "hosting_info",
            "deadline_communication",
            "required_features",
        ]
        widgets = {
            "industry": forms.TextInput(attrs={"placeholder": "ex. restaurant, clinică, consultanță, retail..."}),
        }


class ContactForm(forms.ModelForm):
    # Honeypot: real visitors never see or fill this field, bots that
    # auto-fill every input do. Checked (not saved) in the view.
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = ContactMessageSimple
        fields = ["name", "email", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 5}),
        }


class ReviewForm(forms.ModelForm):
    # Honeypot: real visitors never see or fill this field, bots that
    # auto-fill every input do. Checked (not saved) in the view.
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Review
        fields = ["name", "company", "rating", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
        }
