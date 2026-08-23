from django.contrib import admin
from .models import Project, ContactMessage, ContactMessageSimple, Certification, Review


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title","link", "is_featured", "order", "created_at")
    list_editable = ("is_featured", "order")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title",)


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ("title", "issuer", "issue_date", "order")
    list_editable = ("order",)
    search_fields = ("title", "issuer")

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("name", "rating", "is_approved", "created_at")
    list_editable = ("is_approved",)
    list_filter = ("rating", "is_approved")
    search_fields = ("name", "company")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "industry",
        "selected_package",
        "required_features",
        "is_read",
        "created_at",
    )
    list_filter = ("selected_package", "is_read")
    search_fields = ("name", "email", "industry")
    list_editable = ("is_read",)


@admin.register(ContactMessageSimple)
class ContactMessageSimpleAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email")
    list_editable = ("is_read",)
