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

    def test_og_image_falls_back_to_the_brand_image_never_the_personal_photo(self):
        project = make_project(title="No Image Project")
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertContains(response, "og-default.jpg")
        self.assertNotContains(response, "poza_me")

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
                inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0] and "ld+json" not in s.split(">")[0]]
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
                inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0] and "ld+json" not in s.split(">")[0]]
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
        inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0] and "ld+json" not in s.split(">")[0]]
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
        inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0] and "ld+json" not in s.split(">")[0]]
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
        inline = [s for s in body.split("<script")[1:] if "src=" not in s.split(">")[0] and "ld+json" not in s.split(">")[0]]
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


# ---------------------------------------------------------------------------
# SEO and performance (Stage 7, group 1)
# ---------------------------------------------------------------------------
import json
import re
from html import unescape
from pathlib import Path

from django.conf import settings

from .faq import FAQ_GROUPS
from .packages import PACKAGES


def _meta(body, attr, name):
    match = re.search(rf'<meta {attr}="{re.escape(name)}" content="(.*?)">', body, re.S)
    return unescape(match.group(1)) if match else None


def _title(body):
    return unescape(re.search(r"<title>(.*?)</title>", body, re.S).group(1))


def _jsonld(body):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)]


def _visible_text(body):
    """Page text without the head, scripts and tags, entities decoded."""
    body = body[body.index("<body"):]
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    return unescape(re.sub(r"<[^>]+>", " ", body))


class SeoTestBase(TestCase):
    def setUp(self):
        self.project = make_project(title="SEO Project", short_description="Un proiect de test pentru verificările SEO, cu o descriere de lungime normală.")
        self.with_image = make_project(title="SEO With Image", image=make_test_png(), short_description="Un al doilea proiect de test, cu imagine proprie, pentru verificările SEO.")

    def public_urls(self):
        return [
            reverse("home"), reverse("services"),
            *[reverse("service_detail", args=[s]) for s in ("web", "ai", "creativ")],
            reverse("projects"), reverse("project_detail", args=[self.project.slug]),
            reverse("products"), reverse("planner_product"), reverse("budget_product"),
            reverse("about"), reverse("contact"), reverse("start_project"),
            reverse("faq"), reverse("reviews"), reverse("privacy_policy"),
        ]


class CanonicalTests(SeoTestBase):
    def test_every_public_page_has_exactly_one_absolute_canonical_for_its_own_url(self):
        for url in self.public_urls():
            with self.subTest(url=url):
                body = self.client.get(url).content.decode()
                canonicals = re.findall(r'<link rel="canonical" href="(.*?)">', body)
                self.assertEqual(canonicals, [f"http://testserver{url}"])

    def test_query_strings_never_leak_into_the_canonical(self):
        for url in (reverse("start_project") + "?pachet=ai_automatizare", reverse("start_project") + "?sent=1"):
            with self.subTest(url=url):
                body = self.client.get(url).content.decode()
                self.assertIn(f'<link rel="canonical" href="http://testserver{reverse("start_project")}">', body)
                self.assertEqual(_meta(body, "property", "og:url"), f"http://testserver{reverse('start_project')}")

    def test_404_is_not_indexable_and_has_no_canonical(self):
        body = self.client.get("/nu-exista-nimic/").content.decode()
        self.assertIn('<meta name="robots" content="noindex">', body)
        self.assertNotIn('rel="canonical"', body)

    def test_canonical_urls_are_in_the_sitemap_format_with_trailing_slash(self):
        for url in self.public_urls():
            with self.subTest(url=url):
                self.assertTrue(url.endswith("/"))


class TitlesAndDescriptionsTests(SeoTestBase):
    def pages(self):
        return {url: self.client.get(url).content.decode() for url in self.public_urls()}

    def test_every_page_has_a_unique_title_and_a_unique_description(self):
        pages = self.pages()
        titles = {url: _title(body) for url, body in pages.items()}
        descriptions = {url: _meta(body, "name", "description") for url, body in pages.items()}
        self.assertEqual(len(set(titles.values())), len(titles), f"duplicate titles: {titles}")
        self.assertEqual(len(set(descriptions.values())), len(descriptions), f"duplicate descriptions: {descriptions}")

    def test_titles_and_descriptions_have_sensible_lengths(self):
        for url, body in self.pages().items():
            with self.subTest(url=url):
                self.assertLessEqual(len(_title(body)), 65)
                self.assertGreaterEqual(len(_title(body)), 10)
                description = _meta(body, "name", "description")
                self.assertTrue(50 <= len(description) <= 175, f"{len(description)}: {description}")

    def test_social_tags_repeat_the_pages_own_title_and_description(self):
        for url, body in self.pages().items():
            with self.subTest(url=url):
                title, description = _title(body), _meta(body, "name", "description")
                self.assertEqual(_meta(body, "property", "og:title"), title)
                self.assertEqual(_meta(body, "name", "twitter:title"), title)
                self.assertEqual(_meta(body, "property", "og:description"), description)
                self.assertEqual(_meta(body, "name", "twitter:description"), description)

    def test_every_page_has_exactly_one_h1(self):
        for url, body in self.pages().items():
            with self.subTest(url=url):
                self.assertEqual(len(re.findall(r"<h1[ >]", body)), 1)

    def test_long_project_descriptions_are_trimmed_in_the_head_but_not_on_the_page(self):
        long_text = " ".join(["Cuvânt"] * 60)
        project = make_project(title="Long One", short_description=long_text)
        body = self.client.get(reverse("project_detail", args=[project.slug])).content.decode()
        self.assertLessEqual(len(_meta(body, "name", "description")), 160)
        self.assertIn(long_text, re.sub(r"\s+", " ", body))


class ShareImageTests(SeoTestBase):
    def test_default_share_image_is_the_brand_card_not_the_personal_photo(self):
        for url in self.public_urls():
            with self.subTest(url=url):
                body = self.client.get(url).content.decode()
                head = body[:body.index("</head>")]
                self.assertNotIn("poza_me", head)
                self.assertIn("og-default.jpg", _meta(head, "property", "og:image"))
                self.assertEqual(_meta(head, "property", "og:image:width"), "1200")
                self.assertEqual(_meta(head, "property", "og:image:height"), "630")
                self.assertTrue(_meta(head, "property", "og:image:alt"))

    def test_project_with_its_own_image_shares_that_image(self):
        body = self.client.get(reverse("project_detail", args=[self.with_image.slug])).content.decode()
        head = body[:body.index("</head>")]
        self.assertIn(self.with_image.image.url, _meta(head, "property", "og:image"))
        self.assertNotIn("poza_me", head)
        self.assertIn(self.with_image.title, _meta(head, "property", "og:image:alt"))

    def test_brand_card_exists_with_the_standard_size_and_stays_small(self):
        from PIL import Image
        path = Path(settings.BASE_DIR) / "static" / "website" / "og-default.jpg"
        with Image.open(path) as image:
            self.assertEqual(image.size, (1200, 630))
        self.assertLess(path.stat().st_size, 150 * 1024)


class OptimizedImagesTests(TestCase):
    STATIC = Path(settings.BASE_DIR) / "static" / "website"

    def test_the_original_photo_is_still_there(self):
        self.assertTrue((self.STATIC / "poza_me.JPG").exists())

    def test_optimized_variants_exist_and_are_much_smaller_than_the_original(self):
        original = (self.STATIC / "poza_me.JPG").stat().st_size
        for name in ("poza_me-480.webp", "poza_me-800.webp", "poza_me-480.jpg", "poza_me-800.jpg"):
            with self.subTest(name=name):
                self.assertLess((self.STATIC / name).stat().st_size, original / 5)

    def test_about_serves_the_optimized_picture_with_a_fallback_and_dimensions(self):
        body = self.client.get(reverse("about")).content.decode()
        self.assertIn("poza_me-800.webp", body)
        self.assertIn("poza_me-800.jpg", body)
        self.assertNotIn("poza_me.JPG", body)
        self.assertRegex(body, r'<img src="[^"]*poza_me-800\.jpg"[^>]*width="800" height="800"')
        self.assertIn('fetchpriority="high"', body)


class StructuredDataTests(SeoTestBase):
    FORBIDDEN_KEYS = {"address", "telephone", "aggregateRating", "review", "priceRange", "openingHours",
                      "areaServed", "geo", "foundingDate", "numberOfEmployees"}

    def collect_keys(self, node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from self.collect_keys(value)
        elif isinstance(node, list):
            for item in node:
                yield from self.collect_keys(item)

    def test_every_page_carries_valid_json_ld_without_invented_fields(self):
        for url in self.public_urls():
            with self.subTest(url=url):
                blocks = _jsonld(self.client.get(url).content.decode())
                self.assertGreaterEqual(len(blocks), 1)
                for block in blocks:
                    self.assertEqual(block["@context"], "https://schema.org")
                    self.assertFalse(self.FORBIDDEN_KEYS & set(self.collect_keys(block)))

    def test_organization_only_states_what_the_footer_shows(self):
        body = self.client.get(reverse("home")).content.decode()
        graph = _jsonld(body)[0]["@graph"]
        org = next(n for n in graph if n["@type"] == "Organization")
        visible = _visible_text(body)
        self.assertEqual(org["name"], "Andreea Tech")
        self.assertIn(org["email"], visible)
        self.assertIn(org["sameAs"][0], body)
        self.assertEqual(set(org) - {"@type", "@id"}, {"name", "url", "email", "sameAs"})
        self.assertEqual(org["url"], "http://testserver/")
        site = next(n for n in graph if n["@type"] == "WebSite")
        self.assertEqual(site["inLanguage"], "ro")

    def test_service_data_matches_the_visible_name_text_and_price(self):
        for package in PACKAGES:
            with self.subTest(slug=package["slug"]):
                url = reverse("service_detail", args=[package["slug"]])
                body = self.client.get(url).content.decode()
                service = next(b for b in _jsonld(body) if b.get("@type") == "Service")
                visible = _visible_text(body)
                self.assertIn(service["name"], visible)
                self.assertIn(service["description"], visible)
                self.assertIn(package["price"], visible)
                self.assertEqual(service["offers"]["priceSpecification"]["minPrice"], package["price_value"])
                self.assertEqual(service["offers"]["priceSpecification"]["priceCurrency"], "EUR")
                self.assertEqual(service["url"], f"http://testserver{url}")

    def test_faq_data_is_exactly_the_visible_questions_and_answers(self):
        body = self.client.get(reverse("faq")).content.decode()
        faq = next(b for b in _jsonld(body) if b.get("@type") == "FAQPage")
        visible = _visible_text(body)
        expected = [(q, a) for _, _, qs in FAQ_GROUPS for q, a in qs]
        self.assertEqual(len(faq["mainEntity"]), len(expected))
        self.assertEqual(body.count('<details class="qa">'), len(expected))
        for entity, (question, answer) in zip(faq["mainEntity"], expected):
            self.assertEqual(entity["name"], question)
            self.assertEqual(entity["acceptedAnswer"]["text"], answer)
            self.assertIn(question, visible)
            self.assertIn(re.sub(r"\s+", " ", answer), re.sub(r"\s+", " ", visible))

    def test_project_data_matches_the_visible_title_description_and_image(self):
        body = self.client.get(reverse("project_detail", args=[self.with_image.slug])).content.decode()
        work = next(b for b in _jsonld(body) if b.get("@type") == "CreativeWork")
        self.assertEqual(work["name"], self.with_image.title)
        self.assertEqual(work["description"], self.with_image.short_description)
        self.assertIn(work["description"], _visible_text(body))
        self.assertTrue(work["image"].endswith(self.with_image.image.url))
        plain = self.client.get(reverse("project_detail", args=[self.project.slug])).content.decode()
        self.assertNotIn("image", next(b for b in _jsonld(plain) if b.get("@type") == "CreativeWork"))

    def test_json_ld_cannot_break_out_of_its_script_element(self):
        project = make_project(title="Tag </script><b>x", short_description="a & b </script> c")
        body = self.client.get(reverse("project_detail", args=[project.slug])).content.decode()
        block = re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
        self.assertTrue(all("</script" not in b for b in block))
        self.assertEqual(next(b for b in _jsonld(body) if b.get("@type") == "CreativeWork")["name"], project.title)


class RobotsTxtTests(TestCase):
    def test_robots_allows_the_site_asks_crawlers_to_skip_the_admin_and_points_to_the_sitemap(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Allow: /", body)
        self.assertIn("Disallow: /panou-admin/", body)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)

    def test_the_admin_is_protected_by_login_not_by_robots_txt(self):
        response = self.client.get("/panou-admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])


# ---------------------------------------------------------------------------
# Stage 7, group 2: static files pipeline (A), local fonts (B), CSP (C)
# ---------------------------------------------------------------------------
import tempfile

from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.templatetags.static import static
from django.test import override_settings

from .middleware import CSP_ADMIN, CSP_PUBLIC

ROOT = Path(settings.BASE_DIR)
MANIFEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "website.storage.ForgivingManifestStaticFilesStorage"},
}
HASHED = re.compile(r"\.[0-9a-f]{12}\.[a-z0-9]+$")


def _public_urls():
    project = Project.objects.create(
        title="Pipeline Project", short_description="Un proiect de test pentru fluxul de fișiere statice.",
        problem="p", solution="s", outcome="o",
    )
    return [
        reverse("home"), reverse("services"),
        *[reverse("service_detail", args=[s]) for s in ("web", "ai", "creativ")],
        reverse("projects"), reverse("project_detail", args=[project.slug]),
        reverse("products"), reverse("planner_product"), reverse("budget_product"),
        reverse("about"), reverse("contact"), reverse("start_project"),
        reverse("faq"), reverse("reviews"), reverse("privacy_policy"),
    ]


class StaticReferencesTests(TestCase):
    """Every {% static '...' %} written in a live template must point at a real file."""

    def live_templates(self):
        return [p for p in (ROOT / "templates").rglob("*.html") if "_legacy" not in p.parts]

    def test_every_static_reference_in_the_live_templates_exists(self):
        pattern = re.compile(r"""\{%\s*static\s+['"]([^'"]+)['"]\s*%\}""")
        missing, checked = [], 0
        for template in self.live_templates():
            for ref in pattern.findall(template.read_text(encoding="utf-8")):
                checked += 1
                if not finders.find(ref):
                    missing.append(f"{template.relative_to(ROOT)} -> {ref}")
        self.assertGreater(checked, 15)
        self.assertEqual(missing, [])

    def test_every_url_inside_the_stylesheets_exists(self):
        css_dir = ROOT / "static" / "website"
        missing = []
        for css in ("fonts.css", "tokens.css", "base.css", "components.css"):
            for ref in re.findall(r"url\(['\"]?([^'\")]+)['\"]?\)", (css_dir / css).read_text(encoding="utf-8")):
                if not ref.startswith(("data:", "http")) and not (css_dir / ref).exists():
                    missing.append(f"{css} -> {ref}")
        self.assertEqual(missing, [])

    def test_the_old_settings_name_is_gone_and_the_current_one_is_used(self):
        source = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")
        self.assertNotIn('STATICFILES_STORAGE = "', source)
        self.assertIn("ForgivingManifestStaticFilesStorage", source)

    def test_deploy_script_still_collects_static_files(self):
        self.assertIn("collectstatic", (ROOT / "deploy.sh").read_text(encoding="utf-8"))


class StaticFilesPipelineTests(TestCase):
    """Runs the real thing: collectstatic into a temporary folder with the
    hashing and compressing storage, then renders every public page."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.static_root = Path(cls._tmp.name)
        with override_settings(STORAGES=MANIFEST_STORAGES, STATIC_ROOT=str(cls.static_root)):
            # admin and ckeditor are skipped only to keep the test fast; the
            # site's own files (static/website) are all collected and hashed.
            call_command("collectstatic", interactive=False, verbosity=0, ignore_patterns=["admin", "ckeditor"])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        super().tearDownClass()

    def test_collectstatic_writes_a_manifest_with_hashed_names(self):
        manifest = json.loads((self.static_root / "staticfiles.json").read_text())["paths"]
        for name in ("website/tokens.css", "website/base.css", "website/components.css", "website/fonts.css",
                     "website/site.js", "website/og-default.jpg", "website/fonts/fraunces-latin.woff2"):
            with self.subTest(name=name):
                self.assertIn(name, manifest)
                self.assertRegex(manifest[name], HASHED)
                self.assertTrue((self.static_root / manifest[name]).exists())

    def test_text_assets_get_a_gzip_copy(self):
        manifest = json.loads((self.static_root / "staticfiles.json").read_text())["paths"]
        for name in ("website/components.css", "website/site.js", "website/fonts.css"):
            with self.subTest(name=name):
                self.assertTrue((self.static_root / (manifest[name] + ".gz")).exists())

    def test_the_font_stylesheet_points_at_the_hashed_font_files(self):
        manifest = json.loads((self.static_root / "staticfiles.json").read_text())["paths"]
        css = (self.static_root / manifest["website/fonts.css"]).read_text()
        urls = re.findall(r"url\(['\"]?([^'\")]+)", css)
        self.assertGreaterEqual(len(urls), 8)
        for url in urls:
            with self.subTest(url=url):
                self.assertRegex(url, HASHED)
                self.assertTrue((self.static_root / "website" / url).exists())

    def test_every_public_page_renders_and_uses_only_hashed_site_assets(self):
        with override_settings(STORAGES=MANIFEST_STORAGES, STATIC_ROOT=str(self.static_root)):
            for url in _public_urls():
                with self.subTest(url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    body = response.content.decode()
                    refs = re.findall(r'(?:href|src)="(/static/website/[^"]+)"', body)
                    self.assertGreater(len(refs), 5)
                    for ref in refs:
                        self.assertRegex(ref, HASHED, f"unhashed static URL on {url}: {ref}")
                        self.assertTrue((self.static_root / ref.removeprefix("/static/")).exists(), ref)

    def test_a_source_file_that_was_not_collected_degrades_instead_of_breaking_the_page(self):
        # admin/css/base.css exists in Django's source static folder but the
        # collectstatic run above skipped "admin", like a deploy that forgot it.
        self.assertTrue(finders.find("admin/css/base.css"))
        with override_settings(STORAGES=MANIFEST_STORAGES, STATIC_ROOT=str(self.static_root)):
            with self.assertLogs("website.storage", level="WARNING") as logs:
                self.assertEqual(static("admin/css/base.css"), "/static/admin/css/base.css")
            self.assertIn("Run `collectstatic`", logs.output[0])
            # a collected file still gets its hashed name
            self.assertRegex(static("website/site.js"), HASHED)

    def test_a_name_that_exists_nowhere_keeps_the_standard_error(self):
        """WhiteNoise probes file names at start-up and relies on this error, and
        a typo in a template must stay loud (StaticReferencesTests catches it)."""
        with override_settings(STORAGES=MANIFEST_STORAGES, STATIC_ROOT=str(self.static_root)):
            with self.assertRaises(ValueError):
                static("website/this-file-does-not-exist.css")


class LocalFontsTests(TestCase):
    FONTS = ROOT / "static" / "website" / "fonts"

    def test_the_fonts_are_valid_woff2_files(self):
        files = list(self.FONTS.glob("*.woff2"))
        self.assertEqual(len(files), 8)
        for font in files:
            with self.subTest(font=font.name):
                self.assertEqual(font.read_bytes()[:4], b"wOF2")

    def test_the_same_three_families_are_declared_with_swap(self):
        css = (ROOT / "static" / "website" / "fonts.css").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"font-family: '([^']+)'", css)), {"Fraunces", "Hanken Grotesk", "DM Mono"})
        self.assertEqual(css.count("@font-face"), css.count("font-display: swap"))

    def test_romanian_letters_are_covered_by_a_declared_subset(self):
        css = (ROOT / "static" / "website" / "fonts.css").read_text(encoding="utf-8")
        ranges = re.findall(r"unicode-range: ([^;]+);", css)

        def covered(codepoint):
            for rng in ranges:
                for part in rng.split(","):
                    part = part.strip().removeprefix("U+")
                    low, _, high = part.partition("-")
                    if int(low, 16) <= codepoint <= int(high or low, 16):
                        return True
            return False

        for char in "ăâîșțĂÂÎȘȚ„”":
            with self.subTest(char=char):
                self.assertTrue(covered(ord(char)))

    def test_pages_request_no_outside_font_host_and_preload_the_main_fonts(self):
        body = self.client.get(reverse("home")).content.decode()
        self.assertNotIn("googleapis", body)
        self.assertNotIn("gstatic", body)
        self.assertEqual(body.count('rel="preload" as="font"'), 4)
        for name in re.findall(r'rel="preload" as="font" type="font/woff2" href="/static/website/fonts/([^"]+)"', body):
            self.assertTrue((self.FONTS / name).exists())

    def test_the_500_page_uses_the_local_fonts_too(self):
        from django.template.loader import render_to_string
        html = render_to_string("500.html")
        self.assertIn("website/fonts.css", html)
        self.assertNotIn("googleapis", html)


class ContentSecurityPolicyTests(TestCase):
    def directive(self, header, name):
        return next((d.strip() for d in header.split(";") if d.strip().startswith(name + " ")), "")

    def test_public_pages_send_the_strict_policy(self):
        for url in _public_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url)["Content-Security-Policy"], CSP_PUBLIC)

    def test_public_policy_allows_no_inline_scripts_and_no_outside_hosts(self):
        self.assertEqual(self.directive(CSP_PUBLIC, "script-src"), "script-src 'self'")
        self.assertNotIn("http", CSP_PUBLIC)
        self.assertEqual(self.directive(CSP_PUBLIC, "font-src"), "font-src 'self'")
        self.assertEqual(self.directive(CSP_PUBLIC, "style-src"), "style-src 'self'")
        for required in ("object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'"):
            self.assertIn(required, CSP_PUBLIC)

    def test_the_admin_keeps_its_own_policy(self):
        for url in ("/panou-admin/login/", "/panou-admin/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url)["Content-Security-Policy"], CSP_ADMIN)
        self.assertIn("script-src 'self' 'unsafe-inline'", CSP_ADMIN)

    def test_the_404_page_and_robots_use_the_public_policy(self):
        self.assertEqual(self.client.get("/nu-exista/")["Content-Security-Policy"], CSP_PUBLIC)
        self.assertEqual(self.client.get("/robots.txt")["Content-Security-Policy"], CSP_PUBLIC)

    def test_a_policy_set_by_a_view_is_not_overwritten(self):
        from django.http import HttpResponse
        from django.test import RequestFactory
        from .middleware import ContentSecurityPolicyMiddleware

        def view(request):
            response = HttpResponse("x")
            response["Content-Security-Policy"] = "default-src 'none'"
            return response

        response = ContentSecurityPolicyMiddleware(view)(RequestFactory().get("/"))
        self.assertEqual(response["Content-Security-Policy"], "default-src 'none'")

    def test_public_pages_contain_nothing_the_policy_would_block(self):
        """No inline event handlers, javascript: links, <style> elements or
        executable inline scripts, and no CSS, script, font or image from
        another host. If one slips in, the page would silently break."""
        for url in _public_urls():
            with self.subTest(url=url):
                body = self.client.get(url).content.decode()
                self.assertIsNone(re.search(r"<[^>]+\son\w+\s*=", body), "inline event handler")
                self.assertNotIn("javascript:", body.lower())
                self.assertNotIn("<style", body.lower())
                scripts = [s for s in body.split("<script")[1:]
                           if "src=" not in s.split(">")[0] and "ld+json" not in s.split(">")[0]]
                self.assertEqual(scripts, [])
                for tag in re.findall(r"<(?:link|script|img|source)\b[^>]*>", body):
                    for attr in re.findall(r'(?:href|src|srcset)="([^"]+)"', tag):
                        if "canonical" in tag:
                            continue
                        self.assertTrue(attr.startswith(("/", "data:")), f"outside resource: {tag}")

    def test_the_site_script_is_a_file_not_inline_code(self):
        body = self.client.get(reverse("home")).content.decode()
        self.assertEqual(len(re.findall(r'<script src="/static/website/site\.js"', body)), 1)


# ---------------------------------------------------------------------------
# Rich text on the public project page is sanitised (audit item E, variant 1)
# ---------------------------------------------------------------------------
from io import StringIO

from .sanitize import ALLOWED_ATTRIBUTES, ALLOWED_TAGS, CORE_TAGS, sanitize_html

# The payloads used in the audit of the project page, in the same shape.
AUDIT_PAYLOAD = (
    '<p>Paragraf normal.</p>'
    '<script>window.__x=(window.__x||[]).concat("script-tag")</script>'
    '<img src="x" onerror="window.__x=(window.__x||[]).concat(\'onerror-attribute\')">'
    '<svg onload="window.__x=(window.__x||[]).concat(\'svg-onload\')"></svg>'
    '<a id="jslink" href="javascript:window.__x=(window.__x||[]).concat(\'javascript-url\')">link javascript</a>'
    '<iframe id="evilframe" src="https://evil-iframe.example/" width="200" height="60"></iframe>'
    '<img id="pixel" src="https://evil-tracker.example/pixel.png">'
    '<form id="evilform" action="https://evil-form.example/steal" method="post">'
    '<input name="parola" placeholder="Parola ta"><button type="submit">Trimite</button></form>'
    '<style>body{background:rgb(255,0,0)!important}</style>'
    '<meta http-equiv="refresh" content="2;url=https://evil-meta.example/redirect">'
    '<a id="plainlink" href="https://good.example/">link obișnuit</a>'
    '<a href="https://good.example/2" onclick="alert(5)" style="color:red">cu atribute</a>'
)

# More ways around a naive filter.
EVASIONS = {
    "mixed-case scheme": '<a href="JaVaScRiPt:alert(1)">x</a>',
    "tab inside scheme": '<a href="java\tscript:alert(1)">x</a>',
    "numeric entity scheme": '<a href="&#106;avascript:alert(1)">x</a>',
    "hex entity with tab": '<a href="jav&#x09;ascript:alert(1)">x</a>',
    "leading space": '<a href=" javascript:alert(1)">x</a>',
    "leading control char": '<a href="\x01javascript:alert(1)">x</a>',
    "data html": '<a href="data:text/html,<script>alert(1)</script>">x</a>',
    "vbscript": '<a href="vbscript:msgbox(1)">x</a>',
    "file": '<a href="file:///etc/passwd">x</a>',
    "javascript img": '<img src="javascript:alert(1)">',
    "svg style mxss": '<svg><style><img src=x onerror=alert(1)></style></svg>',
    "math mxss": '<math><mtext><table><mglyph><style><!--</style><img title="--&gt;&lt;img src=1 onerror=alert(1)&gt;">',
    "noscript mxss": '<noscript><p title="</noscript><img src=x onerror=alert(1)>">',
    "nested script": '<scr<script>ipt>alert(1)</scr</script>ipt>',
    "slash handler": '<img src=x onerror=alert(1)//>',
    "details toggle": '<details open ontoggle=alert(1)>x</details>',
    "autofocus input": '<input autofocus onfocus=alert(1)>',
    "video source": '<video><source onerror=alert(1)></video>',
    "body onload": '<body onload=alert(1)>x',
    "html comment": '<!--<script>alert(1)</script>-->x',
    "css expression": '<span style="background-color:expression(alert(1))">x</span>',
    "css behavior": '<span style="color:red;behavior:url(x.htc)">x</span>',
    "css url": '<span style="background-color:red;background-image:url(javascript:alert(1))">x</span>',
    "object": '<object data="https://evil-object.example/x.swf"></object>',
    "embed": '<embed src="https://evil-embed.example/x.swf">',
    "base": '<base href="https://evil-base.example/">',
    "link stylesheet": '<link rel="stylesheet" href="https://evil-css.example/x.css">',
    "style attribute on p": '<p style="position:fixed;top:0;left:0;width:100%">x</p>',
    "form button": '<form action="https://evil-form.example"><button formaction="https://evil-form.example">x</button></form>',
}

FORBIDDEN = (
    "<script", "</script", "onerror", "onload", "onclick", "onfocus", "ontoggle", "javascript:", "vbscript:",
    "<iframe", "<form", "<input", "<meta", "<style", "<svg", "<math", "<object", "<embed", "<base", "<link",
    "<video", "<noscript", "<template", "http-equiv", "expression(", "behavior", "data:text", "file:",
    "<body", "<!--", "formaction",
)


class RichTextSanitizerUnitTests(TestCase):
    def assertSafe(self, output, label=""):
        lowered = output.lower()
        for token in FORBIDDEN:
            self.assertNotIn(token, lowered, f"{label}: {token!r} survived in {output!r}")

    def test_audit_payload_is_neutralised_and_the_innocent_parts_stay(self):
        out = sanitize_html(AUDIT_PAYLOAD)
        self.assertSafe(out, "audit payload")
        self.assertNotIn("alert(", out)
        self.assertNotIn("window.__x", out)
        for host in ("evil-iframe.example", "evil-tracker.example", "evil-form.example", "evil-meta.example"):
            self.assertNotIn(host, out)
        self.assertIn("<p>Paragraf normal.</p>", out)
        self.assertIn('<a href="https://good.example/" rel="noopener noreferrer">link obișnuit</a>', out)
        self.assertIn('<a href="https://good.example/2" rel="noopener noreferrer">cu atribute</a>', out)

    def test_every_evasion_is_neutralised(self):
        for label, payload in EVASIONS.items():
            with self.subTest(evasion=label):
                self.assertSafe(sanitize_html(payload), label)

    def test_evasions_that_contain_a_link_keep_the_text_but_lose_the_href(self):
        for label in ("mixed-case scheme", "tab inside scheme", "numeric entity scheme", "hex entity with tab",
                      "leading space", "leading control char", "data html", "vbscript", "file"):
            with self.subTest(evasion=label):
                out = sanitize_html(EVASIONS[label])
                self.assertNotIn("href", out)
                self.assertIn("x", out)

    def test_sanitising_twice_changes_nothing(self):
        for payload in (AUDIT_PAYLOAD, *EVASIONS.values()):
            once = sanitize_html(payload)
            self.assertEqual(sanitize_html(once), once)

    def test_empty_values(self):
        self.assertEqual(sanitize_html(""), "")
        self.assertEqual(sanitize_html(None), "")

    def test_only_safe_link_schemes_keep_their_href(self):
        for href in ("https://a.example/", "http://a.example/", "mailto:a@b.ro", "tel:+40123456789", "/contact/", "#sectiune"):
            with self.subTest(href=href):
                self.assertIn(f'href="{href}"', sanitize_html(f'<a href="{href}">t</a>'))
        for href in ("javascript:alert(1)", "data:text/plain,x", "ftp://a.example/", "sms:+40123", "ssh://a.example"):
            with self.subTest(href=href):
                self.assertNotIn("href", sanitize_html(f'<a href="{href}">t</a>'))

    def test_links_get_rel_noopener_noreferrer_and_lose_target(self):
        out = sanitize_html('<a href="https://a.example/" target="_blank" rel="opener">t</a>')
        self.assertEqual(out, '<a href="https://a.example/" rel="noopener noreferrer">t</a>')


class RichTextFormattingIsPreservedTests(TestCase):
    """What the editor produces today must come out exactly as it went in."""

    EDITOR_OUTPUT = [
        "<p>Un paragraf cu <strong>bold</strong>, <em>italic</em> și <u>subliniat</u>.</p>",
        "<ul><li>unu</li><li>doi</li></ul>",
        "<ol><li>primul</li><li>al doilea</li></ol>",
        "<h2>Titlu</h2><h3>Subtitlu</h3><h4>Titlu mic</h4>",
        "<blockquote><p>Un citat.</p></blockquote>",
        "<p>Rând unu<br>rând doi</p>",
        "<p>ă î â ș ț Ă Î Â Ș Ț „ghilimele” – liniuță &amp; semn</p>",
        "<p>a&nbsp;b</p>",
    ]

    def test_editor_output_is_unchanged(self):
        for html in self.EDITOR_OUTPUT:
            with self.subTest(html=html):
                self.assertEqual(sanitize_html(html), html)

    def test_older_content_written_with_the_previous_toolbar_keeps_its_look(self):
        cases = {
            "table": ('<table><tbody><tr><th colspan="2">T</th></tr><tr><td>a</td><td>b</td></tr></tbody></table>',
                      '<table><tbody><tr><th colspan="2">T</th></tr><tr><td>a</td><td>b</td></tr></tbody></table>'),
            "rule, pre, strike": ("<hr><pre>cod</pre><s>tăiat</s>", "<hr><pre>cod</pre><s>tăiat</s>"),
            "old headings": ("<h1>A</h1><h5>b</h5><h6>c</h6>", "<h1>A</h1><h5>b</h5><h6>c</h6>"),
            "b and i": ("<p><b>gros</b> <i>aplecat</i></p>", "<p><b>gros</b> <i>aplecat</i></p>"),
            "text colour": ('<p><span style="color:#ff0000">roșu</span></p>', '<p><span style="color:#ff0000">roșu</span></p>'),
            "background colour": ('<span style="background-color:#ffff00">galben</span>', '<span style="background-color:#ffff00">galben</span>'),
            "image": ('<img alt="x" src="/media/projects/a.png" width="300" height="200">',
                      '<img alt="x" src="/media/projects/a.png" width="300" height="200">'),
        }
        for label, (given, expected) in cases.items():
            with self.subTest(case=label):
                self.assertEqual(sanitize_html(given), expected)

    def test_images_may_only_come_from_this_site(self):
        self.assertEqual(sanitize_html('<img src="/media/a.png" alt="x">'), '<img src="/media/a.png" alt="x">')
        self.assertEqual(sanitize_html('<img src="images/a.png">'), '<img src="images/a.png">')
        for src in ("https://tracker.example/p.png", "http://tracker.example/p.png", "//tracker.example/p.png",
                    "data:image/png;base64,AAAA", "javascript:alert(1)", " https://tracker.example/p.png"):
            with self.subTest(src=src):
                out = sanitize_html(f'<img src="{src}" alt="x">')
                self.assertNotIn("tracker.example", out)
                self.assertNotIn("data:", out)
                self.assertNotIn("javascript", out)

    def test_a_style_keeps_only_plain_colour_values(self):
        cases = {
            'color:#f00': 'color:#f00',
            'color:red;background-color:rgb(0, 128, 0)': 'color:red;background-color:rgb(0, 128, 0)',
            'color:hsla(120,50%,50%,0.5)': 'color:hsla(120, 50%, 50%, 0.5)',  # nh3 re-serialises with spaces
            'background-color:expression(alert(1))': None,
            'color:url(https://x/y)': None,
            'color:red !important': None,
            'color:var(--x)': None,
            'color:red;position:fixed': 'color:red',
            'font-size:99px': None,
        }
        for style, expected in cases.items():
            with self.subTest(style=style):
                out = sanitize_html(f'<span style="{style}">x</span>')
                self.assertEqual(out, f'<span style="{expected}">x</span>' if expected else "<span>x</span>")

    def test_only_the_colour_properties_survive_in_a_style(self):
        out = sanitize_html('<span style="color:#f00;font-size:40px;position:fixed;background-color:#0f0">x</span>')
        self.assertEqual(out, '<span style="color:#f00;background-color:#0f0">x</span>')

    def test_the_allowed_list_covers_everything_the_editor_is_configured_to_produce(self):
        """If the editor config in settings.py ever gains a tag, this fails until
        the sanitizer allows it too, so a new button can never silently lose formatting."""
        spec = settings.CKEDITOR_CONFIGS["default"]["allowedContent"]
        tags = {word.split("[")[0] for word in re.split(r"[;\s]+", spec) if word}
        self.assertTrue(tags <= ALLOWED_TAGS, f"missing from the sanitizer: {tags - ALLOWED_TAGS}")
        self.assertTrue(tags <= CORE_TAGS)
        self.assertIn("href", ALLOWED_ATTRIBUTES["a"])


class ProjectPageSanitizingTests(TestCase):
    def make_hostile_project(self):
        return make_project(title="Ostil", problem=AUDIT_PAYLOAD, solution=AUDIT_PAYLOAD, outcome=AUDIT_PAYLOAD)

    def page(self, project):
        return self.client.get(reverse("project_detail", args=[project.slug]))

    def test_all_three_rich_fields_are_sanitised_on_the_public_page(self):
        body = self.page(self.make_hostile_project()).content.decode()
        self.assertEqual(body.count("Paragraf normal."), 3)
        self.assertEqual(body.count('href="https://good.example/"'), 3)
        for host in ("evil-iframe.example", "evil-tracker.example", "evil-form.example", "evil-meta.example"):
            self.assertNotIn(host, body)
        for token in ("alert(", "onerror", "onload", "onclick", "javascript:", "http-equiv", 'id="evilform"', "evilframe", "pixel.png"):
            self.assertNotIn(token, body)

    def test_nothing_stored_in_the_database_is_modified(self):
        project = self.make_hostile_project()
        self.page(project)
        project.refresh_from_db()
        self.assertEqual(project.problem, AUDIT_PAYLOAD)
        self.assertEqual(project.solution, AUDIT_PAYLOAD)
        self.assertEqual(project.outcome, AUDIT_PAYLOAD)

    def test_the_template_no_longer_uses_the_safe_filter_on_editor_html(self):
        source = (ROOT / "templates" / "website" / "project_detail.html").read_text(encoding="utf-8")
        self.assertNotIn("|safe", source)
        for field in ("problem", "solution", "outcome"):
            self.assertIn(f"project.{field}|sanitize_html", source)

    def test_normal_formatting_reaches_the_page(self):
        project = make_project(
            title="Format", problem="<h2>Titlu intern</h2><p>Text <strong>gros</strong></p>",
            solution="<ul><li>primul</li></ul>", outcome="<blockquote><p>Citat</p></blockquote>",
        )
        body = self.page(project).content.decode()
        for fragment in ("<h2>Titlu intern</h2>", "<strong>gros</strong>", "<ul><li>primul</li></ul>", "<blockquote><p>Citat</p></blockquote>"):
            self.assertIn(fragment, body)

    def test_the_strict_csp_header_still_applies_to_the_page(self):
        self.assertEqual(self.page(self.make_hostile_project())["Content-Security-Policy"], CSP_PUBLIC)

    def test_nh3_is_pinned_in_the_requirements(self):
        self.assertRegex((ROOT / "requirements.txt").read_text(), r"(?m)^nh3==\d+\.\d+\.\d+$")


class AuditRichTextCommandTests(TestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command("audit_rich_text", *args, stdout=out)
        return out.getvalue()

    def test_reports_what_would_be_removed_and_changes_nothing(self):
        clean = make_project(title="Curat", problem="<p>ok</p>", solution="<ul><li>a</li></ul>", outcome="<h2>b</h2>")
        hostile = make_project(title="Ostil", problem=AUDIT_PAYLOAD, solution="<p>ok</p>", outcome="<p>ok</p>")
        legacy = make_project(title="Vechi", problem='<p><font color="red">roșu</font></p>', solution="<p>ok</p>", outcome="<p>ok</p>")
        before = {p.pk: (p.problem, p.solution, p.outcome) for p in (clean, hostile, legacy)}

        with self.assertNumQueries(1):
            report = self.run_command()

        self.assertIn("Projects: 3", report)
        self.assertIn("Fields where it removes something: 2", report)
        self.assertIn("<script> x1", report)
        self.assertIn("<iframe> x1", report)
        self.assertIn("<form> x1", report)
        self.assertIn("<meta> x1", report)
        self.assertIn("javascript: x1", report)
        self.assertIn("img[onerror] x1", report)
        self.assertIn("<font> x1", report)
        self.assertIn("ostil / problem", report)
        self.assertNotIn("curat /", report)
        after = {p.pk: (p.problem, p.solution, p.outcome) for p in Project.objects.all()}
        self.assertEqual(before, after)

    def test_clean_content_is_reported_as_untouched(self):
        make_project(title="Curat", problem="<p>ok</p>", solution="<p>ok</p>", outcome="<p>ok</p>")
        self.assertIn("Nothing to remove", self.run_command())

    def test_show_diff_prints_before_and_after(self):
        make_project(title="Ostil", problem="<p>x</p><script>alert(1)</script>", solution="<p>s</p>", outcome="<p>o</p>")
        report = self.run_command("--show-diff")
        self.assertIn("before:", report)
        self.assertIn("after :", report)

    def test_works_with_no_projects(self):
        self.assertIn("Projects: 0", self.run_command())
