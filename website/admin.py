from django.contrib import admin
from .models import Project, ContactMessage, ContactMessageSimple, Certification, Review, SiteSettings


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "direction", "status", "category", "link", "is_featured", "order", "created_at")
    list_editable = ("direction", "status", "is_featured", "order")
    list_filter = ("direction", "status", "category", "is_featured")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title",)


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ("title", "issuer", "issue_date", "order")
    list_editable = ("order",)
    search_fields = ("title", "issuer")

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "rating", "is_approved", "created_at")
    list_editable = ("is_approved",)
    list_filter = ("rating", "is_approved")
    search_fields = ("name", "company", "business_url")


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


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """One row only: it can be edited but not duplicated or deleted."""

    list_display = ("__str__", "show_availability", "availability_text")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
