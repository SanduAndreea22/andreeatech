from django import forms
from django.core.validators import MaxLengthValidator

from .models import ContactMessage, ContactMessageSimple, Review


class HoneypotFormMixin(forms.Form):
    # Real visitors never see or fill this field, bots that auto-fill
    # every input do. Checked (not saved) in the view.
    website = forms.CharField(required=False, widget=forms.HiddenInput())


class FriendlyErrorsMixin:
    """Server-side validation messages in the same informal voice as the rest of the site
    (Django's Romanian defaults are formal: "Introduceți o adresă…")."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.EmailField):
                field.error_messages["invalid"] = "Adresa de email nu pare validă. Verifică-o și încearcă din nou."
            elif isinstance(field, forms.URLField):
                field.error_messages["invalid"] = "Adresa site-ului nu pare validă. Începe cu https://"
            elif isinstance(field, (forms.ChoiceField, forms.MultipleChoiceField)):
                field.error_messages["invalid_choice"] = "Alege una dintre opțiunile din listă."
            field.error_messages["required"] = "Completează acest câmp."
            for validator in field.validators:
                if isinstance(validator, MaxLengthValidator):
                    validator.message = "Textul e prea lung: poți folosi cel mult %(limit_value)d de caractere."


class StartProjectForm(FriendlyErrorsMixin, HoneypotFormMixin, forms.ModelForm):

    FEATURE_CHOICES = [
        ("content", "Conținut & postări social media"),
        ("booking", "Sistem de rezervări / programări"),
        ("dashboard", "Panou de administrare (unde îți gestionezi singur rezervările, clienții sau conținutul)"),
        ("website", "Website de prezentare (pagini despre afacerea ta, fără rezervări)"),
        ("automation", "Automatizare simplă (confirmări, mesaje de reamintire)"),
        ("ai_agent", "Asistent AI care răspunde clienților (telefon, WhatsApp)"),
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
        choices=[("", "Alege o direcție")] + ContactMessage.PACKAGE_CHOICES,
        required=False,
    )

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
            "project_description": forms.Textarea(attrs={
                "rows": 6,
                "placeholder": "ex. Am o clinică cu trei cabinete. Programările se fac pe telefon și multe rămân neconfirmate. Vreau programări online cu confirmare automată.",
            }),
            "hosting_info": forms.TextInput(attrs={"placeholder": "ex. am domeniul, caut hosting / nu am nimic"}),
            "deadline_communication": forms.TextInput(attrs={"placeholder": "ex. până în martie / nu e urgent"}),
        }


class ContactForm(FriendlyErrorsMixin, HoneypotFormMixin, forms.ModelForm):
    class Meta:
        model = ContactMessageSimple
        fields = ["name", "email", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 5}),
        }


class PlaceholderSelect(forms.Select):
    """A select whose empty option is only a label: it is shown while nothing
    is chosen but can never be picked again, so "Alege nota" is not an answer."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value in ("", None):
            option["attrs"]["disabled"] = True
        return option


class ReviewForm(FriendlyErrorsMixin, HoneypotFormMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ["name", "role", "company", "business_url", "project_note", "rating", "message"]
        widgets = {
            "role": forms.TextInput(attrs={"placeholder": "ex. Fondator, Manager"}),
            "business_url": forms.URLInput(attrs={"placeholder": "https://..."}),
            "project_note": forms.TextInput(attrs={"placeholder": "ex. Sistem de rezervări"}),
            "message": forms.Textarea(attrs={"rows": 4}),
            "rating": PlaceholderSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django's default empty option reads "---------". Swap it for a real
        # label; the field stays required and the stored choices are unchanged.
        self.fields["rating"].choices = [("", "Alege nota")] + [
            choice for choice in self.fields["rating"].choices if choice[0] != ""
        ]
