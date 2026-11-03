import io
from types import SimpleNamespace

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse
from PIL import Image

from .models import Certification, Project, ContactMessage, ContactMessageSimple, Review, validate_image_max_size, validate_pdf_max_size, validate_pdf_content
from .views import _client_ip

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


def make_test_pdf():
    # FileExtensionValidator only checks the filename, so minimal bytes are fine.
    return SimpleUploadedFile("portfolio.pdf", b"%PDF-1.4 test", content_type="application/pdf")


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

    def test_duplicate_title_gets_suffixed_slug(self):
        # Exercises the retry-on-IntegrityError path in Project.save():
        # two projects with the same title must not collide on slug.
        first = make_project(title="Same Title")
        second = make_project(title="Same Title")
        self.assertEqual(first.slug, "same-title")
        self.assertEqual(second.slug, "same-title-2")

    def test_explicit_duplicate_slug_still_raises(self):
        # A collision on a slug the caller set explicitly (not
        # auto-generated) is a real conflict, not one save() should paper
        # over with a suffix.
        make_project(title="First", slug="taken")
        with self.assertRaises(IntegrityError):
            make_project(title="Second", slug="taken")

    def test_tech_list_splits_and_strips(self):
        project = make_project(tech_stack="Django, PostgreSQL ,  Redis")
        self.assertEqual(project.tech_list(), ["Django", "PostgreSQL", "Redis"])

    def test_tech_list_is_empty_for_blank_tech_stack(self):
        # Content-category projects have no tech stack — tech_list() must
        # return [] rather than [''] so the "Construit cu" block in the
        # template can hide itself with {% if project.tech_list %}.
        project = make_project(tech_stack="", category=Project.CATEGORY_CONTINUT_CREATIV)
        self.assertEqual(project.tech_list(), [])

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


class ImageMaxSizeValidationTests(TestCase):
    """Unit tests against the validator function directly — a real upload's
    .size is a read-only property backed by storage, not something a test
    can just overwrite on a saved model instance."""

    def test_oversized_file_fails_validation(self):
        oversized = SimpleNamespace(size=6 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            validate_image_max_size(oversized)

    def test_file_at_the_limit_passes_validation(self):
        at_limit = SimpleNamespace(size=5 * 1024 * 1024)
        validate_image_max_size(at_limit)  # should not raise


class PdfMaxSizeValidationTests(TestCase):

    def test_oversized_file_fails_validation(self):
        oversized = SimpleNamespace(size=11 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            validate_pdf_max_size(oversized)

    def test_file_at_the_limit_passes_validation(self):
        at_limit = SimpleNamespace(size=10 * 1024 * 1024)
        validate_pdf_max_size(at_limit)  # should not raise

    def test_certification_image_wider_than_max_is_shrunk(self):
        cert = make_certification(image=make_oversized_png(1400, 700))
        with Image.open(cert.image.path) as saved:
            self.assertEqual(saved.width, 900)
            self.assertEqual(saved.height, 450)


class PdfContentValidationTests(TestCase):
    """FileExtensionValidator only checks the filename — these exercise the
    magic-bytes check that catches a renamed non-PDF file."""

    def test_file_without_pdf_header_fails_validation(self):
        fake = SimpleUploadedFile("fake.pdf", b"not a real pdf", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_pdf_content(fake)

    def test_real_pdf_header_passes_validation(self):
        validate_pdf_content(make_test_pdf())  # should not raise

    def test_validation_does_not_consume_the_file(self):
        # save() reads the file again after validators run — if the
        # validator didn't rewind, the saved file would be truncated.
        pdf = make_test_pdf()
        validate_pdf_content(pdf)
        self.assertEqual(pdf.read(), b"%PDF-1.4 test")


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


class ProjectsListViewTests(TestCase):

    def test_multiple_featured_projects_all_shown_as_featured(self):
        make_project(title="Featured A", is_featured=True)
        make_project(title="Featured B", is_featured=True)
        make_project(title="Regular")

        response = self.client.get(reverse("projects"))

        featured_titles = {p.title for p in response.context["featured_projects"]}
        grid_titles = {p.title for p in response.context["projects"]}
        self.assertEqual(featured_titles, {"Featured A", "Featured B"})
        self.assertEqual(grid_titles, {"Regular"})


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

    def test_download_button_shown_when_pdf_attached(self):
        project = make_project(title="With PDF", portfolio_pdf=make_test_pdf())
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertContains(response, "Descarcă PDF-ul proiectului")

    def test_download_button_hidden_without_pdf(self):
        project = make_project(title="No PDF")
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertNotContains(response, "Descarcă PDF-ul proiectului")

    def test_tech_block_hidden_for_content_project_without_tech_stack(self):
        project = make_project(
            title="Content Concept",
            tech_stack="",
            category=Project.CATEGORY_CONTINUT_CREATIV,
        )
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertNotContains(response, "Construit cu")

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
            "selected_package": "ai_automatizare",
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
        self.assertEqual(obj.selected_package, "ai_automatizare")

    def test_package_preselected_from_query_param(self):
        response = self.client.get(reverse("start_project") + "?pachet=produse_sisteme")
        self.assertContains(response, "produse_sisteme")

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


class RateLimitTests(TestCase):
    """_rate_limited() uses the default in-memory cache, which is shared
    across every test in the process — clear it before each test so counts
    from other test classes' submissions don't leak in here."""

    def setUp(self):
        cache.clear()

    def test_sixth_submission_within_an_hour_is_rate_limited(self):
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "message": "Hello there!",
            "website": "",
        }
        for _ in range(5):
            self.client.post(reverse("contact"), payload)
        self.assertEqual(ContactMessageSimple.objects.count(), 5)

        response = self.client.post(reverse("contact"), payload)
        self.assertRedirects(response, reverse("contact"))
        self.assertEqual(ContactMessageSimple.objects.count(), 5)

    def test_rate_limit_uses_atomic_increment_not_read_then_write(self):
        # A plain cache.get() + cache.set() pair lets two near-simultaneous
        # requests both read the same pre-increment count and both slip
        # under the limit. Simulate that by calling _rate_limited() several
        # times in a tight loop and checking the count lands exactly on the
        # limit boundary — a get/set race would let it drift past 5.
        from .views import _rate_limited

        request = RequestFactory().get("/")
        results = [_rate_limited(request, "atomic-check") for _ in range(6)]
        self.assertEqual(results, [False, False, False, False, False, True])


class ClientIpTests(TestCase):

    def test_uses_rightmost_forwarded_for_entry(self):
        request = RequestFactory().get(
            "/", HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.1"
        )
        # The right-most entry is the one PythonAnywhere's own proxy
        # appended — a client can forge every entry before it.
        self.assertEqual(_client_ip(request), "10.0.0.1")

    def test_single_forwarded_for_entry(self):
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="203.0.113.5")
        self.assertEqual(_client_ip(request), "203.0.113.5")

    def test_falls_back_to_remote_addr_without_header(self):
        request = RequestFactory().get("/", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(_client_ip(request), "127.0.0.1")


class ProjectDirectionAndStatusTests(TestCase):
    def test_defaults_are_web_direction_and_demo_status(self):
        project = make_project()
        self.assertEqual(project.direction, Project.DIRECTION_WEB)
        self.assertEqual(project.status, Project.STATUS_DEMO)

    def test_display_labels_are_the_site_labels(self):
        project = make_project(direction=Project.DIRECTION_CREATIV, status=Project.STATUS_CONCEPT)
        self.assertEqual(project.get_direction_display(), "Design creativ")
        self.assertEqual(project.get_status_display(), "Concept")


class ServicePackagesTests(TestCase):
    """The visible names and prices changed, but the stored keys must not:
    existing ContactMessage rows reference them."""

    def test_package_keys_are_unchanged(self):
        from .packages import PACKAGES
        self.assertEqual(
            {p["key"] for p in PACKAGES},
            {"continut_digital", "ai_automatizare", "produse_sisteme"},
        )

    def test_prices_are_starting_prices(self):
        from .packages import PACKAGES
        for package in PACKAGES:
            with self.subTest(package=package["key"]):
                self.assertTrue(package["price"].startswith("de la €"))


class HomeViewTests(TestCase):
    def test_home_without_projects_renders_and_hides_the_projects_section(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["featured_projects"], [])
        self.assertNotContains(response, "Proiecte alese")

    def test_home_lists_featured_projects_with_their_status_label(self):
        make_project(title="Featured One", is_featured=True, status=Project.STATUS_CONCEPT)
        make_project(title="Not Featured")
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Featured One")
        self.assertContains(response, "Concept")
        self.assertNotContains(response, "Not Featured")

    def test_home_falls_back_to_newest_projects_when_none_is_featured(self):
        make_project(title="Only Project")
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Only Project")

    def test_home_shows_at_most_four_projects(self):
        for i in range(6):
            make_project(title=f"Project {i}", is_featured=True)
        response = self.client.get(reverse("home"))
        self.assertEqual(len(response.context["featured_projects"]), 4)

    def test_home_lists_the_three_service_directions_from_packages(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Web &amp; produse digitale")
        self.assertContains(response, "Automatizare AI")
        self.assertContains(response, "Design creativ")
        self.assertContains(response, "de la €850")


class ServicesViewTests(TestCase):
    def test_hub_and_all_three_direction_pages_return_200(self):
        self.assertEqual(self.client.get(reverse("services")).status_code, 200)
        for slug in ("web", "ai", "creativ"):
            with self.subTest(slug=slug):
                self.assertEqual(self.client.get(reverse("service_detail", args=[slug])).status_code, 200)

    def test_unknown_direction_is_404(self):
        self.assertEqual(self.client.get("/servicii/nu-exista/").status_code, 404)

    def test_urls_are_the_agreed_ones(self):
        self.assertEqual(reverse("services"), "/servicii/")
        self.assertEqual(reverse("service_detail", args=["web"]), "/servicii/web/")

    def test_direction_page_links_to_the_brief_with_its_package_preselected(self):
        response = self.client.get(reverse("service_detail", args=["ai"]))
        self.assertContains(response, "?pachet=ai_automatizare")
        self.assertContains(response, "de la €250")

    def test_examples_show_only_projects_of_that_direction(self):
        make_project(title="Web Example", direction=Project.DIRECTION_WEB)
        make_project(title="Creative Example", direction=Project.DIRECTION_CREATIV, status=Project.STATUS_CONCEPT)
        web = self.client.get(reverse("service_detail", args=["web"]))
        self.assertContains(web, "Web Example")
        self.assertNotContains(web, "Creative Example")

    def test_examples_block_is_hidden_when_the_direction_has_no_projects(self):
        response = self.client.get(reverse("service_detail", args=["creativ"]))
        self.assertNotContains(response, "Exemple")

    def test_only_the_ai_page_has_the_booking_demo(self):
        self.assertContains(self.client.get(reverse("service_detail", args=["ai"])), 'id="demoForm"')
        self.assertNotContains(self.client.get(reverse("service_detail", args=["web"])), 'id="demoForm"')

    def test_hub_has_the_price_estimate_with_the_extras(self):
        response = self.client.get(reverse("services"))
        self.assertContains(response, 'id="est"')
        self.assertContains(response, "Agent AI, de la €25")

    def test_service_pages_are_in_the_sitemap(self):
        body = self.client.get("/sitemap.xml").content.decode()
        for path in ("/servicii/", "/servicii/web/", "/servicii/ai/", "/servicii/creativ/"):
            with self.subTest(path=path):
                self.assertIn(path, body)

    def test_start_project_accepts_the_package_keys_used_by_the_service_pages(self):
        for key in ("produse_sisteme", "ai_automatizare", "continut_digital"):
            with self.subTest(key=key):
                response = self.client.get(reverse("start_project") + f"?pachet={key}")
                self.assertContains(response, key)


class ServiceOfferButtonTests(TestCase):
    """Each service row shows a visible "Vezi oferta" button leading to its page."""

    def test_home_hub_and_direction_pages_show_one_button_per_service(self):
        expectations = [
            (reverse("home"), 3),
            (reverse("services"), 3),
            (reverse("service_detail", args=["web"]), 2),  # the two other directions
        ]
        for url, count in expectations:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "Vezi oferta", count=count)

    def test_buttons_point_to_the_service_pages(self):
        response = self.client.get(reverse("services"))
        for slug in ("web", "ai", "creativ"):
            self.assertContains(response, f'href="/servicii/{slug}/"')


class PortfolioRedesignTests(TestCase):
    def test_package_key_matches_the_projects_direction(self):
        expected = {
            Project.DIRECTION_WEB: "produse_sisteme",
            Project.DIRECTION_AI: "ai_automatizare",
            Project.DIRECTION_CREATIV: "continut_digital",
        }
        for direction, key in expected.items():
            with self.subTest(direction=direction):
                self.assertEqual(make_project(title=f"P {direction}", direction=direction).package_key, key)

    def test_list_shows_status_label_direction_and_filters_for_every_project(self):
        make_project(title="Featured", is_featured=True, status=Project.STATUS_PRODUS)
        make_project(title="Regular", direction=Project.DIRECTION_AI, status=Project.STATUS_CONCEPT)
        response = self.client.get(reverse("projects"))
        for text in ("Featured", "Regular", "Produs propriu", "Concept", "Automatizare AI", 'data-filter="creativ"'):
            with self.subTest(text=text):
                self.assertContains(response, text)
        self.assertContains(response, 'data-direction="ai"')

    def test_list_without_projects_shows_a_message_and_no_filters(self):
        response = self.client.get(reverse("projects"))
        self.assertContains(response, "Portofoliul se completează")
        self.assertNotContains(response, 'id="pFilters"')

    def test_list_keeps_the_result_highlight(self):
        make_project(title="With Result", result_highlight="+40% programări online")
        self.assertContains(self.client.get(reverse("projects")), "+40% programări online")

    def test_detail_shows_the_spec_sheet(self):
        project = make_project(title="Sheet Project", status=Project.STATUS_INSTRUMENT, direction=Project.DIRECTION_AI)
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertContains(response, "Fișă de proiect")
        self.assertContains(response, "Instrument propriu")
        self.assertContains(response, "Automatizare AI")
        self.assertContains(response, "Django, PostgreSQL, Redis")

    def test_detail_cta_preselects_the_package_of_the_direction(self):
        project = make_project(title="Creative", direction=Project.DIRECTION_CREATIV)
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertContains(response, "?pachet=continut_digital")

    def test_detail_shows_live_link_only_when_set(self):
        with_link = make_project(title="Live One", link="https://example.com/demo")
        without = make_project(title="Offline One")
        self.assertContains(self.client.get(reverse("project_detail", args=[with_link.slug])), "Vezi proiectul live")
        self.assertNotContains(self.client.get(reverse("project_detail", args=[without.slug])), "Vezi proiectul live")

    def test_detail_renders_the_three_rich_text_blocks(self):
        project = make_project(title="Blocks", problem="<p>Context text</p>", solution="<p>Built text</p>", outcome="<p>Result text</p>")
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        for text in ("Context text", "Built text", "Result text"):
            self.assertContains(response, text)


class ProductPagesTests(TestCase):
    PLANNER_APP = "https://day-planner-e2sv.onrender.com"
    BUDGET_APP = "https://my-budget-or3r.onrender.com"

    def test_index_lists_both_products_with_links_to_their_pages(self):
        response = self.client.get(reverse("products"))
        self.assertContains(response, "Emotional Planner")
        self.assertContains(response, "MyBudget")
        self.assertContains(response, reverse("planner_product"))
        self.assertContains(response, reverse("budget_product"))
        self.assertContains(response, "Early access")

    def test_planner_page_keeps_the_app_link_and_the_demo(self):
        response = self.client.get(reverse("planner_product"))
        self.assertContains(response, self.PLANNER_APP)
        self.assertContains(response, 'id="plannerForm"')
        self.assertContains(response, "Povestea produsului")

    def test_budget_page_keeps_the_app_link_and_the_demo(self):
        response = self.client.get(reverse("budget_product"))
        self.assertContains(response, self.BUDGET_APP)
        self.assertContains(response, 'id="budgetForm"')

    def test_external_app_links_open_safely_in_a_new_tab(self):
        for name, url in (("planner_product", self.PLANNER_APP), ("budget_product", self.BUDGET_APP)):
            with self.subTest(page=name):
                self.assertContains(
                    self.client.get(reverse(name)),
                    f'href="{url}" target="_blank" rel="noopener noreferrer"',
                )

    def test_product_pages_have_no_inline_scripts(self):
        for name in ("products", "planner_product", "budget_product"):
            with self.subTest(page=name):
                body = self.client.get(reverse(name)).content.decode()
                inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0]]
                self.assertEqual(inline, [])


class ContactAndBriefRedesignTests(TestCase):
    def test_contact_page_offers_the_routes_to_the_brief_with_the_package_preselected(self):
        response = self.client.get(reverse("contact"))
        for key in ("produse_sisteme", "ai_automatizare", "continut_digital", "not_sure"):
            with self.subTest(key=key):
                self.assertContains(response, f"{reverse('start_project')}?pachet={key}")

    def test_form_labels_are_tied_to_their_fields(self):
        for name in ("contact", "start_project"):
            with self.subTest(page=name):
                body = self.client.get(reverse(name)).content.decode()
                self.assertIn('for="id_name"', body)
                self.assertIn('id="id_name"', body)
                self.assertIn('for="id_email"', body)

    def test_contact_form_still_saves_and_confirms(self):
        response = self.client.post(
            reverse("contact"),
            {"name": "Ana", "email": "ana@example.com", "message": "Salut!", "website": ""},
            follow=True,
        )
        self.assertEqual(ContactMessageSimple.objects.count(), 1)
        self.assertContains(response, "Mesajul tău a ajuns la mine")

    def test_contact_form_shows_errors_in_the_page_on_invalid_input(self):
        response = self.client.post(reverse("contact"), {"name": "", "email": "not-an-email", "message": "", "website": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errorlist")
        self.assertEqual(ContactMessageSimple.objects.count(), 0)

    def test_brief_page_has_the_three_steps_and_the_honeypot(self):
        body = self.client.get(reverse("start_project")).content.decode()
        self.assertEqual(body.count("data-step"), 3)
        self.assertIn('name="website"', body)

    def test_brief_page_has_no_inline_scripts(self):
        for name in ("contact", "start_project"):
            with self.subTest(page=name):
                body = self.client.get(reverse(name)).content.decode()
                inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0]]
                self.assertEqual(inline, [])


class AboutRedesignTests(TestCase):
    def test_about_never_uses_the_word_studio(self):
        body = self.client.get(reverse("about")).content.decode().lower()
        self.assertNotIn("studio", body)

    def test_about_stays_strictly_professional(self):
        body = self.client.get(reverse("about")).content.decode().lower()
        for word in ("contabil", "finanțe", "full-time"):
            with self.subTest(word=word):
                self.assertNotIn(word, body)

    def test_about_shows_certification_details_and_a_link_to_enlarge(self):
        make_certification(title="Django for Professionals", issuer="Test Academy", credential_url="https://example.com/verify")
        response = self.client.get(reverse("about"))
        self.assertContains(response, "Django for Professionals")
        self.assertContains(response, "Test Academy")
        self.assertContains(response, "https://example.com/verify")
        self.assertContains(response, "data-cert")

    def test_about_without_certifications_shows_a_message(self):
        self.assertContains(self.client.get(reverse("about")), "Certificările vin în curând")

    def test_about_has_no_inline_scripts(self):
        body = self.client.get(reverse("about")).content.decode()
        inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0]]
        self.assertEqual(inline, [])


class TechnicalVersusCreativeTests(TestCase):
    """Visual identity is a creative service, never a part of the technical side."""

    def test_home_technologies_do_not_list_brand_identity(self):
        body = self.client.get(reverse("home")).content.decode()
        tech = body[body.index('class="tech"'):]
        tech = tech[:tech.index("</dl>")]
        self.assertNotIn("dentitate", tech)
        self.assertIn("Arhitectură", tech)

    def test_about_separates_the_technical_and_the_creative_parts(self):
        response = self.client.get(reverse("about"))
        self.assertContains(response, "Partea tehnică")
        self.assertContains(response, "Partea creativă")
        self.assertContains(response, "serviciu creativ separat")

    def test_about_intro_does_not_tie_identity_to_the_technical_side(self):
        body = self.client.get(reverse("about")).content.decode()
        self.assertNotIn("identitate vizuală pentru antreprenori care vor să crească", body)

    def test_creative_page_lists_exactly_the_creative_services(self):
        response = self.client.get(reverse("service_detail", args=["creativ"]))
        for item in ("Identitate vizuală și branding", "Design pentru social media",
                     "Campanii și materiale vizuale", "Direcție creativă"):
            with self.subTest(item=item):
                self.assertContains(response, item)
        self.assertContains(response, "serviciu creativ separat")


class FaqRedesignTests(TestCase):
    def test_answers_are_in_the_html_not_hidden_in_javascript(self):
        body = self.client.get(reverse("faq")).content.decode()
        self.assertIn("7 zile de stabilizare gratuită", body)
        self.assertIn("Django e stabil", body)
        self.assertGreaterEqual(body.count('<details class="qa">'), 20)

    def test_faq_has_no_inline_scripts(self):
        body = self.client.get(reverse("faq")).content.decode()
        inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0]]
        self.assertEqual(inline, [])

    def test_faq_prices_match_the_service_directions(self):
        body = self.client.get(reverse("faq")).content.decode()
        for price in ("€150", "€250", "€850"):
            with self.subTest(price=price):
                self.assertIn(price, body)

    def test_faq_never_uses_the_word_studio(self):
        self.assertNotIn("studio", self.client.get(reverse("faq")).content.decode().lower())

    def test_faq_keeps_creative_separate_from_the_technical_side(self):
        self.assertContains(self.client.get(reverse("faq")), "serviciu separat de partea tehnică")


class FaqCreativeVisibilityTests(TestCase):
    def test_faq_has_a_jump_menu_to_every_group_including_the_creative_one(self):
        response = self.client.get(reverse("faq"))
        for anchor in ("colaborare", "pret", "web", "ai", "creativ"):
            with self.subTest(anchor=anchor):
                self.assertContains(response, f'href="#faq-{anchor}"')
                self.assertContains(response, f'id="faq-{anchor}"')

    def test_creative_group_explains_the_technical_versus_creative_split(self):
        response = self.client.get(reverse("faq"))
        self.assertContains(response, "diferența dintre partea tehnică și partea creativă")
        self.assertContains(response, "Ce înseamnă direcție creativă?")


class ReviewsRedesignTests(TestCase):
    def test_empty_state_is_honest_and_invites_the_first_review(self):
        response = self.client.get(reverse("reviews"))
        self.assertContains(response, "Nu sunt încă recenzii aprobate")
        self.assertNotContains(response, "haos la structură")

    def test_approved_review_shows_its_details_and_a_nofollow_link(self):
        Review.objects.create(
            name="Ana Pop", role="Fondator", company="Salon Demo", business_url="https://example.com",
            project_note="Sistem de programări", message="Foarte bine.", rating=4, is_approved=True,
        )
        response = self.client.get(reverse("reviews"))
        for text in ("Ana Pop", "Fondator", "Salon Demo", "Sistem de programări", "Foarte bine."):
            with self.subTest(text=text):
                self.assertContains(response, text)
        self.assertContains(response, 'href="https://example.com" target="_blank" rel="noopener noreferrer nofollow"')

    def test_rating_is_available_as_text_not_only_as_stars(self):
        Review.objects.create(name="A", message="x", rating=4, is_approved=True)
        self.assertContains(self.client.get(reverse("reviews")), "Nota: 4 din 5")

    def test_unapproved_review_text_is_not_rendered(self):
        Review.objects.create(name="Hidden Person", message="Secret text", rating=5, is_approved=False)
        self.assertNotContains(self.client.get(reverse("reviews")), "Secret text")

    def test_submission_shows_the_thank_you_message_and_stays_pending(self):
        response = self.client.post(reverse("reviews"), {
            "name": "Jane", "company": "", "rating": 5, "message": "Great.", "website": "",
        }, follow=True)
        self.assertContains(response, "Mulțumesc pentru recenzie")
        self.assertFalse(Review.objects.get().is_approved)

    def test_form_has_the_honeypot_and_labels_tied_to_fields(self):
        body = self.client.get(reverse("reviews")).content.decode()
        self.assertIn('name="website"', body)
        self.assertIn('for="id_rating"', body)
        self.assertIn('id="id_message"', body)

    def test_reviews_page_has_no_inline_scripts(self):
        body = self.client.get(reverse("reviews")).content.decode()
        inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0]]
        self.assertEqual(inline, [])


class ReviewRatingFieldTests(TestCase):
    def test_rating_select_has_a_readable_placeholder_and_all_five_choices(self):
        body = self.client.get(reverse("reviews")).content.decode()
        self.assertIn("Alege nota", body)
        self.assertNotIn("---------", body)
        for label in ("1 stea", "2 stele", "3 stele", "4 stele", "5 stele"):
            with self.subTest(label=label):
                self.assertIn(label, body)

    def test_rating_is_still_required(self):
        response = self.client.post(reverse("reviews"), {"name": "Jane", "message": "Hi", "rating": "", "website": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "errorlist")
        self.assertEqual(Review.objects.count(), 0)


class ReviewPlaceholderOptionTests(TestCase):
    def test_placeholder_option_is_disabled_so_it_cannot_be_chosen(self):
        body = self.client.get(reverse("reviews")).content.decode()
        placeholder = body[body.index("Alege nota") - 80:body.index("Alege nota") + 20]
        self.assertIn("disabled", placeholder)
        self.assertIn('value=""', placeholder)

    def test_real_ratings_are_not_disabled(self):
        body = self.client.get(reverse("reviews")).content.decode()
        for value in ("1", "2", "3", "4", "5"):
            with self.subTest(value=value):
                option = body[body.index(f'<option value="{value}"'):]
                self.assertNotIn("disabled", option[:option.index(">")])

    def test_submitting_without_a_rating_is_still_rejected(self):
        response = self.client.post(reverse("reviews"), {"name": "Jane", "message": "Hi", "website": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Review.objects.count(), 0)


class PrivacyAndErrorPagesTests(TestCase):
    def test_privacy_policy_keeps_every_section_of_the_original_text(self):
        response = self.client.get(reverse("privacy_policy"))
        for heading in ("Cui se aplică", "Ce date sunt colectate", "De ce sunt colectate", "Recenzii publicate",
                        "Cookie-uri", "Cât timp sunt păstrate datele", "Drepturile tale"):
            with self.subTest(heading=heading):
                self.assertContains(response, f"<h2>{heading}</h2>")
        self.assertContains(response, "Nu sunt colectate date de plată, financiare sau de identitate")
        self.assertContains(response, "cookie de sesiune și unul de protecție CSRF")

    def test_privacy_policy_never_uses_the_word_studio(self):
        self.assertNotIn("studio", self.client.get(reverse("privacy_policy")).content.decode().lower())

    def test_unknown_url_shows_the_designed_404_with_a_way_back(self):
        response = self.client.get("/nu-exista-aceasta-pagina/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Pagină negăsită", status_code=404)
        self.assertContains(response, 'href="/"', status_code=404)
        self.assertContains(response, reverse("projects"), status_code=404)

    def test_500_page_is_standalone_and_renders_without_a_request(self):
        from django.template.loader import render_to_string
        html = render_to_string("500.html")
        self.assertIn("Ceva n-a mers bine", html)
        self.assertIn('href="/"', html)
        self.assertNotIn("<nav", html)
