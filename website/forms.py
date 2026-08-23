from django import forms

from .models import ContactMessage, ContactMessageSimple, Review


class StartProjectForm(forms.ModelForm):

    FEATURE_CHOICES = [
        ("booking", "Sistem de rezervări / programări"),
        ("dashboard", "Dashboard de administrare"),
        ("website", "Website de prezentare"),
        ("automation", "Automatizare simplă (confirmări, remindere)"),
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
            "name": forms.TextInput(attrs={
                "class": "w-full p-3 rounded-lg bg-slate-800 border border-slate-700 text-white"
            }),
            "email": forms.EmailInput(attrs={
                "class": "w-full p-3 rounded-lg bg-slate-800 border border-slate-700 text-white"
            }),
            "message": forms.Textarea(attrs={
                "rows": 5,
                "class": "w-full p-3 rounded-lg bg-slate-800 border border-slate-700 text-white"
            }),
        }


class ReviewForm(forms.ModelForm):
    # Honeypot: real visitors never see or fill this field, bots that
    # auto-fill every input do. Checked (not saved) in the view.
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Review
        fields = ["name", "company", "rating", "message"]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full p-3 rounded-lg bg-slate-900 border border-slate-700"
            }),
            "company": forms.TextInput(attrs={
                "class": "w-full p-3 rounded-lg bg-slate-900 border border-slate-700"
            }),
            "rating": forms.Select(attrs={
                "class": "w-full p-3 rounded-lg bg-slate-900 border border-slate-700"
            }),
            "message": forms.Textarea(attrs={
                "class": "w-full p-3 rounded-lg bg-slate-900 border border-slate-700",
                "rows": 4
            }),
        }
