from django.contrib import admin
from .models import Project, ContactMessage, ContactMessageSimple


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title","link", "is_featured", "order", "created_at")
    list_editable = ("is_featured", "order")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title",)

from .models import Review

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
        "required_features",
        "is_read",
        "created_at",
    )
    list_filter = ("industry", "is_read")
    search_fields = ("name", "email")
    list_editable = ("is_read",)


@admin.register(ContactMessageSimple)
class ContactMessageSimpleAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email")
    list_editable = ("is_read",)
