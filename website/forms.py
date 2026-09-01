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

    # Overrides the auto-generated field just to swap Django's default
    # "---------" empty option for a real label — ContactMessage.selected_package
    # is a plain CharField (not a FK), so ModelForm can't infer a better one.
    selected_package = forms.ChoiceField(
        choices=[("", "Alege un pachet")] + ContactMessage.PACKAGE_CHOICES,
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
            "industry": forms.TextInput(attrs={"placeholder": "ex. restaurant, clinică, salon..."}),
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
        fields = ["name", "role", "company", "business_url", "project_note", "rating", "message"]
        widgets = {
            "role": forms.TextInput(attrs={"placeholder": "ex. Fondator, Manager"}),
            "business_url": forms.URLInput(attrs={"placeholder": "https://..."}),
            "project_note": forms.TextInput(attrs={"placeholder": "ex. Sistem de rezervări"}),
            "message": forms.Textarea(attrs={"rows": 4}),
        }
