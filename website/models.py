from django.db import models
from ckeditor.fields import RichTextField
from django.utils.text import slugify


class Project(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    link = models.URLField(blank=True, null=True)

    short_description = models.TextField()

    problem = RichTextField()
    solution = RichTextField()
    outcome = RichTextField()

    tech_stack = models.CharField(
        max_length=300,
        help_text="Separate technologies with comma. Example: Django, PostgreSQL, Redis"
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

    def __str__(self):
        return self.title


class ContactMessage(models.Model):

    INDUSTRY_CHOICES = [
        ("hospitality", "Restaurant"),
        ("service_business", "Appointment-based business"),
    ]

    name = models.CharField(max_length=150)
    email = models.EmailField()

    industry = models.CharField(
        max_length=50,
        choices=INDUSTRY_CHOICES
    )

    project_description = models.TextField()

    hosting_info = models.TextField(blank=True)

    deadline_communication = models.TextField(blank=True)

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
    message = models.TextField()

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.email})"


class Review(models.Model):

    RATING_CHOICES = [
        (1, "1 star"),
        (2, "2 stars"),
        (3, "3 stars"),
        (4, "4 stars"),
        (5, "5 stars"),
    ]

    name = models.CharField(max_length=120)
    company = models.CharField(max_length=150, blank=True)
    message = models.TextField()
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
    credential_url = models.URLField(blank=True, help_text="Link to verify the credential (optional).")

    image = models.ImageField(upload_to="certifications/")

    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-issue_date"]

    def __str__(self):
        return self.title
