from PIL import Image

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import IntegrityError, models, transaction
from ckeditor.fields import RichTextField
from django.utils.text import slugify

from .packages import NOT_SURE_KEY, NOT_SURE_LABEL, PACKAGES

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB — a design deck with photos runs bigger than a single image


def validate_image_max_size(image_field):
    if image_field.size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError("Imaginea depășește dimensiunea maximă permisă (5 MB).")


def validate_pdf_max_size(file_field):
    if file_field.size > MAX_PDF_SIZE_BYTES:
        raise ValidationError("Fișierul depășește dimensiunea maximă permisă (10 MB).")


def validate_pdf_content(file_field):
    # FileExtensionValidator only checks the filename, so a renamed file
    # with a .pdf extension would otherwise pass untouched. Read just the
    # magic bytes real PDFs start with, then rewind — the file is read
    # again right after by the storage backend to actually save it.
    file_field.seek(0)
    header = file_field.read(5)
    file_field.seek(0)
    if header != b"%PDF-":
        raise ValidationError("Fișierul nu este un PDF valid.")


def shrink_image_if_needed(image_field, max_width):
    """Resize an ImageField's file in place if it's wider than max_width.

    Runs after the model has been saved (so image_field.path exists).
    No-op once the file is already at or under max_width, so re-saving
    an already-shrunk image never re-compresses it further.
    """
    if not image_field:
        return
    img = Image.open(image_field.path)
    img.load()  # reads pixel data into memory and closes the underlying
    # file handle — required on Windows, which won't allow writing to a
    # path that's still open for reading.
    if img.width <= max_width:
        return
    ratio = max_width / img.width
    resized = img.resize((max_width, round(img.height * ratio)), Image.LANCZOS)
    resized.save(image_field.path, optimize=True)


class Project(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    link = models.URLField(blank=True)

    CATEGORY_SISTEM = "sistem"
    CATEGORY_CONTINUT_CREATIV = "continut_creativ"
    CATEGORY_CHOICES = [
        (CATEGORY_SISTEM, "Sistem"),
        (CATEGORY_CONTINUT_CREATIV, "Conținut creativ"),
    ]
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_SISTEM,
        help_text="Sistem = website/platformă construită. Conținut creativ = concept de conținut/strategie, fără stack tehnic.",
    )

    short_description = models.TextField()

    result_highlight = models.CharField(
        max_length=100,
        blank=True,
        help_text="Un rezultat scurt și cuantificat (opțional), ex. „+40% programări online”. "
                   "Apare la hover pe cardul din Portofoliu. Lasă gol dacă nu ai o cifră reală."
    )

    problem = RichTextField()
    solution = RichTextField()
    outcome = RichTextField()

    tech_stack = models.CharField(
        max_length=300,
        blank=True,
        help_text="Doar pentru proiecte de tip Sistem. Separă tehnologiile prin virgulă. Exemplu: Django, PostgreSQL, Redis. Lasă gol la Conținut creativ."
    )

    image = models.ImageField(upload_to="projects/", blank=True, validators=[validate_image_max_size])

    portfolio_pdf = models.FileField(
        upload_to="project_files/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["pdf"]), validate_pdf_max_size, validate_pdf_content],
        help_text="PDF descărcabil (ex. un concept/portofoliu demonstrativ) — opțional. Apare ca buton de descărcare pe pagina proiectului.",
    )

    is_featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at", "pk"]

    def tech_list(self):
        if not self.tech_stack:
            return []
        return [tech.strip() for tech in self.tech_stack.split(",")]

    def save(self, *args, **kwargs):
        auto_slug = not self.slug
        if auto_slug:
            self.slug = slugify(self.title)

        # Two concurrent saves can both see the slug as free before either
        # writes — retry on the unique-constraint violation instead of
        # racing on a check-then-write query.
        suffix = 2
        while True:
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                break
            except IntegrityError:
                if not auto_slug:
                    raise
                self.slug = f"{slugify(self.title)}-{suffix}"
                suffix += 1
        shrink_image_if_needed(self.image, max_width=1600)

    def __str__(self):
        return self.title


class ContactMessage(models.Model):

    PACKAGE_CHOICES = [
        (p["key"], f'{p["name"]} — {p["price"]}') for p in PACKAGES
    ] + [
        ("automation_only", "Doar automatizare / agent AI (am deja un website)"),
        (NOT_SURE_KEY, NOT_SURE_LABEL),
    ]

    name = models.CharField(max_length=150)
    email = models.EmailField()

    industry = models.CharField(
        max_length=100,
        help_text="Domeniul afacerii (liber, ex. restaurant, clinică, consultanță)."
    )

    selected_package = models.CharField(
        max_length=30,
        choices=PACKAGE_CHOICES,
        blank=True,
        help_text="Pachetul ales de pe homepage, dacă a venit de acolo."
    )

    project_description = models.TextField(max_length=5000)

    hosting_info = models.TextField(max_length=2000, blank=True)

    deadline_communication = models.TextField(max_length=2000, blank=True)

    required_features = models.CharField(
        max_length=300,
        blank=True
    )

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.email})"


class ContactMessageSimple(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    message = models.TextField(max_length=3000)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.email})"


class Review(models.Model):

    RATING_CHOICES = [
        (1, "1 stea"),
        (2, "2 stele"),
        (3, "3 stele"),
        (4, "4 stele"),
        (5, "5 stele"),
    ]

    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120, blank=True, help_text="Ex: Fondator, Manager.")
    company = models.CharField(max_length=150, blank=True)
    business_url = models.URLField(blank=True, help_text="Site-ul afacerii, ca vizitatorii sa poata verifica.")
    project_note = models.CharField(max_length=200, blank=True, help_text="Ce s-a construit, pe scurt.")
    message = models.TextField(max_length=2000)
    rating = models.IntegerField(choices=RATING_CHOICES)

    is_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.rating}⭐"


class Certification(models.Model):
    title = models.CharField(max_length=200)
    issuer = models.CharField(max_length=150, blank=True)
    issue_date = models.DateField(blank=True, null=True)
    credential_url = models.URLField(blank=True, help_text="Link de verificare a certificatului (opțional).")

    image = models.ImageField(upload_to="certifications/", validators=[validate_image_max_size])

    order = models.IntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-issue_date", "pk"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        shrink_image_if_needed(self.image, max_width=900)

    def __str__(self):
        return self.title
