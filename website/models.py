from PIL import Image

from django.db import models
from ckeditor.fields import RichTextField
from django.utils.text import slugify

from .packages import NOT_SURE_KEY, NOT_SURE_LABEL, PACKAGES


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
    link = models.URLField(blank=True, null=True)

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
        help_text="Separă tehnologiile prin virgulă. Exemplu: Django, PostgreSQL, Redis"
    )

    image = models.ImageField(upload_to="projects/", blank=True, null=True)

    is_featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def tech_list(self):
        return [tech.strip() for tech in self.tech_stack.split(",")]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            suffix = 2
            while Project.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)
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

    image = models.ImageField(upload_to="certifications/")

    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-issue_date"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        shrink_image_if_needed(self.image, max_width=900)

    def __str__(self):
        return self.title
