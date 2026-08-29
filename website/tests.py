import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import Certification, Project, ContactMessage, ContactMessageSimple, Review

# 1x1 PNG, generated fresh per call (not a shared SimpleUploadedFile): an
# UploadedFile wraps a BytesIO with a read cursor, so a single shared
# instance gets exhausted — and silently written as a truncated/empty file
# — the second time any test reuses it.
def make_test_png():
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), color="blue").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile("test.png", buffer.read(), content_type="image/png")


def make_oversized_png(width, height):
    """An in-memory PNG at an exact size, for testing the resize-on-save hook."""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color="red").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile("oversized.png", buffer.read(), content_type="image/png")


def make_certification(**overrides):
    defaults = {
        "title": "Django for Professionals",
        "issuer": "Test Academy",
        "image": make_test_png(),
    }
    defaults.update(overrides)
    return Certification.objects.create(**defaults)


def make_project(**overrides):
    defaults = {
        "title": "Test Project",
        "short_description": "A short description.",
        "problem": "The problem.",
        "solution": "The solution.",
        "outcome": "The outcome.",
        "tech_stack": "Django, PostgreSQL, Redis",
    }
    defaults.update(overrides)
    return Project.objects.create(**defaults)


class ProjectModelTests(TestCase):

    def test_slug_is_auto_generated_from_title(self):
        project = make_project(title="My Cool Project")
        self.assertEqual(project.slug, "my-cool-project")

    def test_explicit_slug_is_not_overwritten(self):
        project = make_project(title="My Cool Project", slug="custom-slug")
        self.assertEqual(project.slug, "custom-slug")

    def test_tech_list_splits_and_strips(self):
        project = make_project(tech_stack="Django, PostgreSQL ,  Redis")
        self.assertEqual(project.tech_list(), ["Django", "PostgreSQL", "Redis"])

    def test_str_returns_title(self):
        project = make_project(title="My Cool Project")
        self.assertEqual(str(project), "My Cool Project")


class ImageResizeOnSaveTests(TestCase):

    def test_project_image_wider_than_max_is_shrunk(self):
        project = make_project(image=make_oversized_png(2000, 1000))
        with Image.open(project.image.path) as saved:
            self.assertEqual(saved.width, 1600)
            self.assertEqual(saved.height, 800)

    def test_project_image_under_max_is_untouched(self):
        project = make_project(image=make_oversized_png(800, 400))
        with Image.open(project.image.path) as saved:
            self.assertEqual(saved.width, 800)

    def test_certification_image_wider_than_max_is_shrunk(self):
        cert = make_certification(image=make_oversized_png(1400, 700))
        with Image.open(cert.image.path) as saved:
            self.assertEqual(saved.width, 900)
            self.assertEqual(saved.height, 450)


class ContactMessageModelTests(TestCase):

    def test_str_includes_name_and_email(self):
        obj = ContactMessage.objects.create(
            name="Jane Doe",
            email="jane@example.com",
            industry="restaurant",
            project_description="A restaurant website.",
        )
        self.assertEqual(str(obj), "Jane Doe (jane@example.com)")


class ContactMessageSimpleModelTests(TestCase):

    def test_str_includes_name_and_email(self):
        obj = ContactMessageSimple.objects.create(
            name="Jane Doe",
            email="jane@example.com",
            message="Hello!",
        )
        self.assertEqual(str(obj), "Jane Doe (jane@example.com)")


class ReviewModelTests(TestCase):

    def test_str_includes_name_and_rating(self):
        obj = Review.objects.create(name="Jane Doe", message="Great work!", rating=5)
        self.assertIn("Jane Doe", str(obj))
        self.assertIn("5", str(obj))


class CertificationModelTests(TestCase):

    def test_str_returns_title(self):
        cert = make_certification(title="Django for Professionals")
        self.assertEqual(str(cert), "Django for Professionals")


class AboutViewTests(TestCase):

    def test_about_returns_200(self):
        response = self.client.get(reverse("about"))
        self.assertEqual(response.status_code, 200)

    def test_about_lists_certifications(self):
        cert = make_certification()
        response = self.client.get(reverse("about"))
        self.assertIn(cert, response.context["certifications"])


class StaticPageViewTests(TestCase):
    """Every page that takes no arguments should render without error."""

    def test_static_pages_return_200(self):
        url_names = [
            "home",
            "products",
            "planner_product",
            "budget_product",
            "projects",
            "about",
            "faq",
            "reviews",
            "contact",
            "start_project",
            "privacy_policy",
        ]
        for name in url_names:
            with self.subTest(url_name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)


class ProjectDetailViewTests(TestCase):

    def test_existing_project_returns_200(self):
        project = make_project()
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertEqual(response.status_code, 200)

    def test_missing_project_returns_404(self):
        response = self.client.get(reverse("project_detail", args=["does-not-exist"]))
        self.assertEqual(response.status_code, 404)

    def test_og_image_falls_back_to_default_without_project_image(self):
        project = make_project(title="No Image Project")
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertContains(response, "poza_me")

    def test_og_image_uses_project_image_when_present(self):
        project = make_project(title="With Image Project", image=make_test_png())
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertContains(response, project.image.url)


class ContactFormViewTests(TestCase):

    def test_valid_submission_creates_message_and_redirects(self):
        response = self.client.post(reverse("contact"), {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "message": "Hello there!",
            "website": "",
        })
        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(ContactMessageSimple.objects.count(), 1)

    def test_honeypot_filled_silently_drops_submission(self):
        response = self.client.post(reverse("contact"), {
            "name": "Bot",
            "email": "bot@example.com",
            "message": "Spam",
            "website": "http://spam.example.com",
        })
        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(ContactMessageSimple.objects.count(), 0)

    def test_invalid_submission_does_not_create_message(self):
        response = self.client.post(reverse("contact"), {
            "name": "",
            "email": "not-an-email",
            "message": "",
            "website": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessageSimple.objects.count(), 0)


class StartProjectFormViewTests(TestCase):

    def valid_payload(self, **overrides):
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "industry": "restaurant",
            "selected_package": "full_experience",
            "project_description": "I need a booking system.",
            "hosting_info": "",
            "deadline_communication": "",
            "required_features": ["booking", "dashboard"],
            "website": "",
        }
        payload.update(overrides)
        return payload

    def test_valid_submission_creates_message_with_joined_features(self):
        response = self.client.post(reverse("start_project"), self.valid_payload())
        self.assertRedirects(response, reverse("start_project") + "?sent=1")
        self.assertEqual(ContactMessage.objects.count(), 1)
        obj = ContactMessage.objects.first()
        self.assertEqual(obj.required_features, "booking, dashboard")
        self.assertEqual(obj.selected_package, "full_experience")

    def test_package_preselected_from_query_param(self):
        response = self.client.get(reverse("start_project") + "?pachet=premium_system")
        self.assertContains(response, "premium_system")

    def test_thank_you_state_shown_only_after_submit(self):
        response = self.client.get(reverse("start_project"))
        self.assertNotContains(response, "sp-thanks")

        response = self.client.get(reverse("start_project") + "?sent=1")
        self.assertContains(response, "sp-thanks")

    def test_honeypot_filled_silently_drops_submission(self):
        response = self.client.post(
            reverse("start_project"),
            self.valid_payload(website="http://spam.example.com"),
        )
        self.assertRedirects(response, reverse("start_project"))
        self.assertEqual(ContactMessage.objects.count(), 0)


class ReviewsViewTests(TestCase):

    def test_only_approved_reviews_are_listed(self):
        Review.objects.create(name="Approved", message="Great!", rating=5, is_approved=True)
        Review.objects.create(name="Pending", message="Ok.", rating=3, is_approved=False)

        response = self.client.get(reverse("reviews"))

        names = [r.name for r in response.context["reviews"]]
        self.assertIn("Approved", names)
        self.assertNotIn("Pending", names)

    def test_valid_submission_creates_unapproved_review(self):
        response = self.client.post(reverse("reviews"), {
            "name": "Jane Doe",
            "company": "",
            "rating": 5,
            "message": "Loved working together.",
            "website": "",
        })
        self.assertRedirects(response, reverse("reviews"))
        review = Review.objects.get()
        self.assertFalse(review.is_approved)

    def test_honeypot_filled_silently_drops_submission(self):
        response = self.client.post(reverse("reviews"), {
            "name": "Bot",
            "company": "",
            "rating": 5,
            "message": "Spam",
            "website": "http://spam.example.com",
        })
        self.assertRedirects(response, reverse("reviews"))
        self.assertEqual(Review.objects.count(), 0)


class SeoEndpointTests(TestCase):

    def test_robots_txt(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertIn(b"Sitemap:", response.content)

    def test_sitemap_xml(self):
        make_project()
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<urlset", response.content)
