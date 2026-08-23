from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Project


class StaticViewSitemap(Sitemap):
    priority = 0.7
    changefreq = "monthly"

    def items(self):
        return [
            "home",
            "about",
            "products",
            "planner_product",
            "budget_product",
            "projects",
            "faq",
            "reviews",
            "contact",
            "start_project",
            "privacy_policy",
        ]

    def location(self, item):
        return reverse(item)


class ProjectSitemap(Sitemap):
    priority = 0.6
    changefreq = "yearly"

    def items(self):
        return Project.objects.order_by("order", "-created_at")

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return reverse("project_detail", args=[obj.slug])
