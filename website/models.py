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
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ContactMessage(models.Model):

    INDUSTRY_CHOICES = [
        ("3d_design", "3D Design"),
        ("ecommerce", "E-commerce"),
        ("accounting", "Accounting"),
        ("marketing", "Marketing"),
        ("saas", "SaaS"),
        ("other", "Other"),
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

from django.db import models


class Review(models.Model):

    RATING_CHOICES = [
        (1, "1 Star"),
        (2, "2 Stars"),
        (3, "3 Stars"),
        (4, "4 Stars"),
        (5, "5 Stars"),
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