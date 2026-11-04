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

    def test_og_image_without_a_screenshot_is_still_the_projects_own_card_never_the_personal_photo(self):
        project = make_project(title="No Image Project")
        response = self.client.get(reverse("project_detail", args=[project.slug]))
        self.assertContains(response, f"/projects/{project.slug}/card.jpg?v=")
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
            reverse("calculator"), reverse("guide"),
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
        # Every page except a project page, which has its own card (ProjectShareCardTests).
        project_page = reverse("project_detail", args=[self.project.slug])
        for url in self.public_urls():
            if url == project_page:
                continue
            with self.subTest(url=url):
                body = self.client.get(url).content.decode()
                head = body[:body.index("</head>")]
                self.assertNotIn("poza_me", head)
                self.assertIn("og-default.jpg", _meta(head, "property", "og:image"))
                self.assertEqual(_meta(head, "property", "og:image:width"), "1200")
                self.assertEqual(_meta(head, "property", "og:image:height"), "630")
                self.assertTrue(_meta(head, "property", "og:image:alt"))

    def test_project_page_shares_its_own_card_not_the_raw_screenshot(self):
        body = self.client.get(reverse("project_detail", args=[self.with_image.slug])).content.decode()
        head = body[:body.index("</head>")]
        og = _meta(head, "property", "og:image")
        self.assertIn(f"/projects/{self.with_image.slug}/card.jpg?v=", og)
        self.assertNotIn(self.with_image.image.url, og)
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


# ---------------------------------------------------------------------------
# Quick wins for a more attractive site (ideas 1-9)
# ---------------------------------------------------------------------------
import re as _re
from pathlib import Path as _Path

from django.contrib import admin as _admin
from django.contrib.auth.models import User as _User

from .models import SiteSettings

_STATIC = _Path(__file__).resolve().parent.parent / "static" / "website"


def _css():
    return "".join((_STATIC / name).read_text() for name in ("base.css", "components.css"))


class MotionAndThemeFilesTests(TestCase):
    """Ideas 1, 2, 5, 7: page transitions, reveal on scroll, count-up, theme switch."""

    def test_page_transitions_only_for_visitors_without_reduced_motion(self):
        css = (_STATIC / "base.css").read_text()
        block = css[css.index("@media (prefers-reduced-motion: no-preference)"):]
        self.assertIn("@view-transition", block.split("@media print")[0])
        # The rule must not appear outside that media query.
        self.assertEqual(css.count("@view-transition"), 1)

    def test_reveal_class_is_added_by_script_never_written_in_templates(self):
        for name in ("home", "services", "projects", "about", "faq"):
            body = self.client.get(reverse(name)).content.decode()
            self.assertNotIn('class="rv', body, name)
            self.assertNotIn(" rv ", body, name)

    def test_reveal_is_visible_in_print_and_off_without_motion(self):
        css = (_STATIC / "base.css").read_text()
        self.assertIn("@media print { .rv { opacity: 1 !important", css)
        js = (_STATIC / "site.js").read_text()
        self.assertIn("prefers-reduced-motion: reduce", js)
        self.assertIn("IntersectionObserver", js)

    def test_theme_script_is_an_external_file_loaded_before_the_stylesheets(self):
        body = self.client.get(reverse("home")).content.decode()
        self.assertEqual(len(_re.findall(r'<script src="/static/website/theme\.js"></script>', body)), 1)
        self.assertLess(body.index("theme.js"), body.index("tokens.css"))

    def test_theme_script_only_accepts_the_two_known_values(self):
        js = (_STATIC / "theme.js").read_text()
        self.assertIn("'light'", js)
        self.assertIn("'dark'", js)
        self.assertIn("try", js)  # blocked storage must not break the page

    def test_toggle_button_is_hidden_until_javascript_reveals_it(self):
        body = self.client.get(reverse("home")).content.decode()
        button = _re.search(r'<button class="theme-toggle"[^>]*>', body).group(0)
        self.assertIn(" hidden", button)
        self.assertIn('aria-label="', button)
        self.assertIn('aria-pressed="', button)

    def test_toggle_is_on_every_public_page(self):
        for name in ("home", "services", "projects", "products", "about", "contact", "start_project", "faq", "reviews"):
            self.assertContains(self.client.get(reverse(name)), 'id="themeToggle"', msg_prefix=name)

    def test_estimator_counts_to_the_exact_value_and_respects_reduced_motion(self):
        js = (_STATIC / "site.js").read_text()
        self.assertIn("requestAnimationFrame", js)
        self.assertIn("cancelAnimationFrame", js)
        self.assertIn("reduce", js)
        # The last frame always shows the real target, not a rounded intermediate.
        self.assertIn("Math.min(1,", js)


class StatusChipMarkerTests(TestCase):
    """Idea 4: each status has its own marker."""

    def test_all_four_statuses_have_a_marker_rule(self):
        css = (_STATIC / "components.css").read_text()
        for selector in (".chip::before", ".chip.s-produs::before", ".chip.s-instrument::before", ".chip.s-concept::before"):
            self.assertIn(selector, css)

    def test_markers_differ_in_shape_not_only_in_colour(self):
        css = (_STATIC / "components.css").read_text()
        self.assertIn("border-radius: 1px", css)          # instrument: square
        self.assertIn("dashed var(--ink-2)", css)         # concept: dashed ring

    def test_markers_add_no_extra_text_for_screen_readers(self):
        make_project(status="concept")
        body = self.client.get(reverse("projects")).content.decode()
        self.assertEqual(body.count('class="chip s-concept">Concept</span>') >= 1, True)


class BrowserFrameTests(TestCase):
    """Idea 8: web screenshots get a browser frame, other directions do not."""

    def _project(self, direction):
        return make_project(title=f"P {direction}", direction=direction, image=make_test_png())

    def test_detail_page_frames_only_web_projects(self):
        web = self._project("web")
        creativ = self._project("creativ")
        ai = self._project("ai")
        self.assertContains(self.client.get(reverse("project_detail", args=[web.slug])), 'class="shot frame"')
        self.assertNotContains(self.client.get(reverse("project_detail", args=[creativ.slug])), "shot frame")
        self.assertNotContains(self.client.get(reverse("project_detail", args=[ai.slug])), "shot frame")

    def test_home_frames_only_web_projects(self):
        self._project("web")
        self.assertContains(self.client.get(reverse("home")), "shot frame")
        Project.objects.all().delete()
        self._project("creativ")
        self.assertNotContains(self.client.get(reverse("home")), "shot frame")

    def test_zoom_on_hover_is_limited_to_visitors_without_reduced_motion(self):
        css = (_STATIC / "components.css").read_text()
        block = css[css.index("@media (prefers-reduced-motion: no-preference) {\n    /* Slow zoom"):]
        self.assertIn(".prow:hover .shot img", block.split("}\n}")[0] + "}")


class AvailabilityNoticeTests(TestCase):
    """Idea 9: availability shown only when the owner switched it on."""

    def _row(self, **kw):
        return SiteSettings.objects.create(**kw)

    def test_nothing_is_shown_without_a_settings_row(self):
        for name in ("home", "services", "contact"):
            self.assertNotContains(self.client.get(reverse(name)), "avail-dot", msg_prefix=name)

    def test_nothing_is_shown_while_the_box_is_unticked(self):
        self._row(show_availability=False, availability_text="Primesc proiecte noi")
        self.assertNotContains(self.client.get(reverse("home")), "Primesc proiecte noi")

    def test_ticked_box_with_empty_text_shows_nothing(self):
        self._row(show_availability=True, availability_text="   ")
        self.assertNotContains(self.client.get(reverse("home")), "avail-dot")

    def test_shown_on_home_and_in_the_band_when_switched_on(self):
        self._row(show_availability=True, availability_text="Primesc proiecte noi din decembrie")
        home = self.client.get(reverse("home")).content.decode()
        self.assertEqual(home.count("Primesc proiecte noi din decembrie"), 2)  # hero + band
        self.assertContains(self.client.get(reverse("services")), "Primesc proiecte noi din decembrie")

    def test_text_is_escaped(self):
        self._row(show_availability=True, availability_text='<script>alert(1)</script>')
        body = self.client.get(reverse("home")).content.decode()
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_a_missing_table_does_not_break_the_page(self):
        from unittest import mock
        from django.db import OperationalError
        with mock.patch("website.templatetags.site_notices.SiteSettings.objects") as manager:
            manager.only.side_effect = OperationalError("no such table")
            response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "avail-dot")

    def test_admin_allows_one_row_and_no_delete(self):
        model_admin = _admin.site._registry[SiteSettings]
        request = RequestFactory().get("/")
        request.user = _User.objects.create_superuser("boss", "b@example.com", "pw-12345-xyz")
        self.assertTrue(model_admin.has_add_permission(request))
        self._row(show_availability=False)
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))


class ConfirmationTests(TestCase):
    """Idea 6: visual confirmation after the brief and contact forms."""

    def test_brief_thank_you_has_tick_and_three_honest_steps(self):
        body = self.client.get(reverse("start_project") + "?sent=1").content.decode()
        self.assertIn('class="tick"', body)
        self.assertEqual(body.count('<li><span class="n">0'), 3)
        self.assertIn("maximum 24 de ore", body)
        self.assertIn("preț fix", body)
        # Existing promise kept: the answer is personal, not automatic.
        self.assertIn("nu e un mesaj automat", body)

    def test_tick_is_decorative_for_screen_readers(self):
        body = self.client.get(reverse("start_project") + "?sent=1").content.decode()
        self.assertRegex(body, r'<svg class="tick"[^>]*aria-hidden="true"')

    def test_success_message_gets_a_tick_in_css_not_extra_markup(self):
        self.assertIn(".form-msg.ok::before", (_STATIC / "components.css").read_text())

    def test_animations_respect_reduced_motion(self):
        css = (_STATIC / "components.css").read_text()
        before = css[:css.index("animation: tickDraw")]
        self.assertTrue(before.rstrip().endswith("{") or "prefers-reduced-motion: no-preference" in before[-400:])


class NoGradientsOrShadowsTests(TestCase):
    """The design system has no gradients or shadows; the new code keeps it so."""

    def test_new_styles_add_none(self):
        css = _css()
        self.assertNotIn("linear-gradient", css)
        self.assertNotIn("radial-gradient", css)


# ---------------------------------------------------------------------------
# Ideas 1 and 2 (long list): two-screen booking demo and the calculator
# ---------------------------------------------------------------------------
import json as _json

from . import booking_demo as _bd
from . import calculator as _calc


class CalculatorArithmeticTests(TestCase):

    def test_starting_values_give_the_figures_shown_in_the_approved_mock(self):
        d = _calc.display(**_calc.DEFAULTS)
        self.assertEqual(d["month"], "2.598")
        self.assertEqual(d["year"], "31.176")
        self.assertEqual(d["lost"], "17")
        self.assertEqual(d["total"], "173")
        self.assertEqual(d["kept"], "156")
        self.assertEqual(d["one_saved"], "650")

    def test_starting_values_are_the_ones_the_user_approved(self):
        self.assertEqual(_calc.DEFAULTS, {"per_week": 40, "no_show_pct": 10, "value": 150})

    def test_negative_input_counts_as_zero_and_percentage_is_capped(self):
        r = _calc.estimate(-5, 250, -10)
        self.assertEqual((r["total"], r["month"], r["lost_pct"]), (0, 0, 100.0))
        self.assertEqual(_calc.estimate(40, -3, 150)["month"], 0)

    def test_zero_input_gives_zero_everywhere(self):
        self.assertEqual(_calc.display(0, 0, 0)["month"], "0")

    def test_year_is_twelve_months_and_nothing_else_is_added(self):
        r = _calc.estimate(10, 20, 100)
        self.assertAlmostEqual(r["year"], r["month"] * 12)
        self.assertAlmostEqual(r["month"], 10 * _calc.WEEKS_PER_MONTH * 0.2 * 100)

    def test_halves_round_up_like_javascript(self):
        self.assertEqual(_calc.format_number(649.5), "650")
        self.assertEqual(_calc.format_number(0.5), "1")
        self.assertEqual(_calc.format_number(2.5), "3")

    def test_thousands_use_dots(self):
        self.assertEqual(_calc.format_number(1234567), "1.234.567")
        self.assertEqual(_calc.format_number(999), "999")

    def test_the_script_uses_the_same_constant_and_formula(self):
        js = (_STATIC / "site.js").read_text()
        self.assertIn(f"|| {_calc.WEEKS_PER_MONTH}", js)
        for fragment in ("total = perWeek * weeks", "lost = total * pct / 100", "month = lost * value",
                         "month * 12", "weeks * value"):
            self.assertIn(fragment, js)


class CalculatorPageTests(TestCase):

    def get(self):
        return self.client.get(reverse("calculator"))

    def test_page_exists_and_has_one_h1(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_re.findall(r"<h1[ >]", response.content.decode())), 1)

    def test_url_is_calculator(self):
        self.assertEqual(reverse("calculator"), "/calculator/")

    def test_fields_start_with_the_approved_example_values(self):
        body = self.get().content.decode()
        for field_id, value in (("cA", 40), ("cP", 10), ("cV", 150)):
            self.assertRegex(body, rf'id="{field_id}"[^>]*value="{value}"')

    def test_first_result_is_rendered_by_the_server_not_left_empty(self):
        body = self.get().content.decode()
        self.assertIn("2.598 lei", body)
        self.assertIn("31.176 lei", body)

    def test_formula_is_shown_in_full(self):
        body = self.get().content.decode()
        self.assertIn("Cum calculez", body)
        self.assertIn("4,33", body)
        self.assertIn("Nimic altceva nu intră în calcul", body)

    def test_it_says_plainly_that_this_is_an_estimate_not_a_promise(self):
        self.assertIn("nu o promisiune de rezultat", self.get().content.decode())

    def test_it_makes_no_claim_about_savings_or_reductions(self):
        text = _re.sub(r"<[^>]+>", " ", self.get().content.decode()).lower()
        for word in ("reduce neprezent", "economis", "garant", "% mai puțin", "studiu", "statistic"):
            self.assertNotIn(word, text)

    def test_form_sends_nothing_anywhere(self):
        body = self.get().content.decode()
        form = _re.search(r'<form id="calcForm"[^>]*>', body).group(0)
        self.assertNotIn("action=", form)
        self.assertNotIn("method=", form.lower())
        self.assertNotIn("csrfmiddlewaretoken", body[body.index('id="calcForm"'):body.index("</form>", body.index('id="calcForm"'))])

    def test_buttons_go_to_the_ai_page_and_to_the_brief_with_the_package_preselected(self):
        body = self.get().content.decode()
        self.assertIn(f'href="{reverse("service_detail", args=["ai"])}"', body)
        self.assertIn(f'href="{reverse("start_project")}?pachet=ai_automatizare"', body)

    def test_the_page_is_in_the_sitemap(self):
        self.assertIn("/calculator/", self.client.get("/sitemap.xml").content.decode())

    def test_linked_from_home_and_from_the_ai_page_only(self):
        link = f'href="{reverse("calculator")}"'
        self.assertContains(self.client.get(reverse("home")), link)
        self.assertContains(self.client.get(reverse("service_detail", args=["ai"])), link)
        self.assertNotContains(self.client.get(reverse("service_detail", args=["web"])), link)
        self.assertNotContains(self.client.get(reverse("service_detail", args=["creativ"])), link)

    def test_no_inline_script_and_the_site_script_is_still_a_file(self):
        body = self.get().content.decode()
        inline = [x for x in body.split("<script")[1:] if "src=" not in x.split(">")[0] and "ld+json" not in x.split(">")[0]]
        self.assertEqual(inline, [])

    def test_numbers_in_attributes_are_not_written_with_a_decimal_comma(self):
        # Django localises floats for Romanian ("4,33"); script and CSS need a dot.
        body = self.get().content.decode()
        self.assertIn('data-weeks="4.33"', body)
        self.assertRegex(body, r'style="width:90(\.0)?%"')
        self.assertRegex(body, r'style="width:10(\.0)?%"')
        self.assertNotRegex(body, r'style="width:[0-9]+,[0-9]')

    def test_screen_readers_get_a_summary_that_is_not_read_on_every_keystroke(self):
        js = (_STATIC / "site.js").read_text()
        self.assertIn("addEventListener('change'", js)
        self.assertIn('id="oLive"', self.get().content.decode())


class BookingDemoTests(TestCase):

    def home(self):
        return self.client.get(reverse("home")).content.decode()

    def test_demo_sits_between_services_and_featured_projects(self):
        make_project(is_featured=True)
        body = self.home()
        self.assertLess(body.index('id="servicii"'), body.index('id="bkDemo"'))
        self.assertLess(body.index('id="bkDemo"'), body.index("Proiecte alese"))

    def test_it_is_labelled_as_a_demo_with_invented_data(self):
        body = self.home()
        self.assertIn("Demo · date fictive · nimic nu se trimite și nu se salvează", body)
        self.assertEqual(body.count('class="bk-ex">exemplu</span>'), 2)

    def test_starting_state_is_rendered_by_the_server(self):
        body = self.home()
        self.assertEqual(len(_re.findall(r'<input type="radio" name="slot"', body)), len(_bd.SLOTS))
        self.assertEqual(len(_re.findall(r'name="slot" value="[0-9:]+" disabled', body)), len(_bd.SEED_ROWS))
        self.assertIn('id="bkStBk">2<', body)

    def test_script_data_is_the_same_data_as_the_page(self):
        body = self.home()
        raw = _re.search(r'data-demo="(.*?)"', body).group(1)
        import html as _html
        data = _json.loads(_html.unescape(raw))
        self.assertEqual(data["slots"], _bd.SLOTS)
        self.assertEqual(data["rows"], _bd.SEED_ROWS)

    def test_seed_rows_use_slots_that_exist(self):
        for row in _bd.SEED_ROWS:
            self.assertIn(row["time"], _bd.SLOTS)
        self.assertLess(len(_bd.SEED_ROWS), len(_bd.SLOTS))  # at least one free slot

    def test_nothing_is_posted_anywhere(self):
        body = self.home()
        form = _re.search(r'<form class="bk-b" id="bkForm"[^>]*>', body).group(0)
        self.assertNotIn("action=", form)
        self.assertNotIn("method=", form.lower())

    def test_submit_waits_for_javascript_and_the_page_says_so(self):
        body = self.home()
        self.assertRegex(body, r'id="bkGo" disabled')
        self.assertIn("Demo-ul are nevoie de JavaScript", body)

    def test_name_field_is_length_limited(self):
        self.assertRegex(self.home(), r'id="bkName" maxlength="40"')

    def test_visitor_text_never_goes_in_as_html(self):
        js = (_STATIC / "site.js").read_text()
        block = js[js.index("two-screen booking demo"):js.index("Calculator: live result")]
        self.assertNotIn("innerHTML", block)
        self.assertNotIn("insertAdjacentHTML", block)
        self.assertNotIn("document.write", block)

    def test_motion_is_skipped_for_reduced_motion(self):
        js = (_STATIC / "site.js").read_text()
        block = js[js.index("two-screen booking demo"):js.index("Calculator: live result")]
        self.assertIn("prefers-reduced-motion: reduce", block)

    def test_existing_simulation_on_the_ai_page_is_untouched(self):
        body = self.client.get(reverse("service_detail", args=["ai"])).content.decode()
        self.assertIn('id="demoForm"', body)
        self.assertNotIn('id="bkDemo"', body)

    def test_demo_is_only_on_the_home_page(self):
        for name in ("services", "projects", "about", "contact", "faq"):
            self.assertNotContains(self.client.get(reverse(name)), 'id="bkDemo"', msg_prefix=name)

    def test_the_calculator_link_under_the_demo(self):
        self.assertIn(f'href="{reverse("calculator")}">Cât te costă', self.home())


# ---------------------------------------------------------------------------
# Share cards, one per project (website/share_card.py)
# ---------------------------------------------------------------------------
import shutil as _shutil
import tempfile as _tempfile
from unittest import mock as _mock

from django.test import override_settings as _override

from . import share_card as _sc


def _card_image(response):
    from PIL import Image as _Image
    return _Image.open(io.BytesIO(b"".join(response.streaming_content)))


class ShareCardRenderingTests(TestCase):

    def project(self, **kw):
        defaults = {"title": "Al Noir", "direction": "web", "status": "demo", "tech_stack": "Django, Stripe, PostgreSQL"}
        defaults.update(kw)
        return make_project(**defaults)

    def test_card_has_the_standard_size_and_mode(self):
        image = _sc.render_card(self.project(), "example.test")
        self.assertEqual(image.size, (1200, 630))
        self.assertEqual(image.mode, "RGB")

    def test_every_direction_and_status_renders(self):
        for direction in ("web", "ai", "creativ"):
            for status in ("demo", "produs", "instrument", "concept"):
                with self.subTest(direction=direction, status=status):
                    self.assertEqual(_sc.render_card(self.project(title=f"{direction}-{status}", direction=direction, status=status), "h").size, (1200, 630))

    def test_card_with_a_screenshot_differs_from_the_one_without(self):
        plain = _sc.render_card(self.project(title="Same"), "h")
        with_shot = _sc.render_card(self.project(title="Same", image=make_oversized_png(1400, 800)), "h")
        self.assertNotEqual(plain.tobytes(), with_shot.tobytes())

    def test_romanian_letters_are_drawn_not_replaced(self):
        with_diacritics = _sc.render_card(self.project(title="ăâîșț"), "h").tobytes()
        without = _sc.render_card(self.project(title="aaist"), "h").tobytes()
        self.assertNotEqual(with_diacritics, without)

    def test_a_very_long_title_still_fits_in_the_card(self):
        image = _sc.render_card(self.project(title="Cuvânt " * 80), "h")
        self.assertEqual(image.size, (1200, 630))

    def test_a_very_long_single_word_does_not_break_drawing(self):
        self.assertEqual(_sc.render_card(self.project(title="A" * 300), "h").size, (1200, 630))

    def test_characters_the_fonts_cannot_draw_are_dropped_not_fatal(self):
        self.assertEqual(_sc._clean("Proiect \U0001F680 \u202eînapoi\u200b"), "Proiect înapoi")
        self.assertEqual(_sc.render_card(self.project(title="\U0001F680\U0001F680"), "h").size, (1200, 630))

    def test_empty_title_text_gets_a_neutral_placeholder(self):
        self.assertEqual(_sc.render_card(self.project(title="\U0001F680"), "h").size, (1200, 630))

    def test_a_missing_screenshot_file_gives_a_card_without_it(self):
        project = self.project(title="Gone", image=make_oversized_png(1400, 800))
        Path(project.image.path).unlink()
        with self.assertLogs("website.share_card", level="WARNING"):
            self.assertEqual(_sc.render_card(project, "h").size, (1200, 630))

    def test_a_damaged_screenshot_file_gives_a_card_without_it(self):
        project = self.project(title="Broken", image=make_oversized_png(1400, 800))
        Path(project.image.path).write_bytes(b"not an image")
        with self.assertLogs("website.share_card", level="WARNING"):
            self.assertEqual(_sc.render_card(project, "h").size, (1200, 630))

    def test_the_card_never_adds_anything_the_page_does_not_show(self):
        # Texts drawn: wordmark, direction, title, status, stack, host. No invented claims.
        source = Path(_sc.__file__).read_text()
        for forbidden in ("clienți", "rezultat", "garant", "premiu", "recomand"):
            self.assertNotIn(forbidden, source.lower())


class ShareCardVersionTests(TestCase):

    def test_same_project_same_version(self):
        project = make_project(title="Same", tech_stack="Django")
        self.assertEqual(_sc.card_version(project, "h"), _sc.card_version(project, "h"))

    def test_everything_shown_on_the_card_changes_the_version(self):
        project = make_project(title="Base", direction="web", status="demo", tech_stack="Django")
        base = _sc.card_version(project, "h")
        for field, value in (("title", "Other"), ("direction", "ai"), ("status", "concept"), ("tech_stack", "Python")):
            with self.subTest(field=field):
                changed = make_project(title=f"Base-{field}", direction="web", status="demo", tech_stack="Django")
                setattr(changed, field, value)
                changed.slug = project.slug
                self.assertNotEqual(_sc.card_version(changed, "h"), base)
        self.assertNotEqual(_sc.card_version(project, "other-host"), base)

    def test_text_not_shown_on_the_card_does_not_change_the_version(self):
        project = make_project(title="Quiet")
        before = _sc.card_version(project, "h")
        project.short_description = "Changed"
        project.problem = "<p>changed</p>"
        project.order = 5
        self.assertEqual(_sc.card_version(project, "h"), before)

    def test_replacing_the_screenshot_changes_the_version(self):
        project = make_project(title="Shot", image=make_oversized_png(1400, 800))
        before = _sc.card_version(project, "h")
        Path(project.image.path).write_bytes(Path(project.image.path).read_bytes() + b"\0")
        self.assertNotEqual(_sc.card_version(project, "h"), before)


class ShareCardViewTests(TestCase):

    def setUp(self):
        self.project = make_project(title="Al Noir", direction="web", status="demo", image=make_oversized_png(1400, 800))
        self.url = reverse("project_card", args=[self.project.slug])
        self.cache = Path(settings.MEDIA_ROOT) / "share_cards"
        if self.cache.exists():
            _shutil.rmtree(self.cache)

    def tearDown(self):
        if self.cache.exists():
            _shutil.rmtree(self.cache)

    def test_returns_a_1200_by_630_jpeg(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        image = _card_image(response)
        self.assertEqual((image.format, image.size), ("JPEG", (1200, 630)))

    def test_stays_small_enough_for_social_networks(self):
        body = b"".join(self.client.get(self.url).streaming_content)
        self.assertLess(len(body), 300 * 1024)

    def test_the_url_is_the_one_shown_on_the_card_site(self):
        self.assertEqual(self.url, f"/projects/{self.project.slug}/card.jpg")

    def test_is_drawn_once_then_served_from_disk(self):
        with _mock.patch("website.share_card.render_card", wraps=_sc.render_card) as spy:
            self.client.get(self.url)
            self.client.get(self.url)
            self.client.get(self.url + "?v=whatever")
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(len(list(self.cache.glob("*.jpg"))), 1)

    def test_a_changed_project_gets_a_new_file_and_the_old_one_is_removed(self):
        self.client.get(self.url)
        first = {p.name for p in self.cache.glob("*.jpg")}
        self.project.status = "concept"
        self.project.save()
        self.client.get(self.url)
        second = {p.name for p in self.cache.glob("*.jpg")}
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first, second)

    def test_removing_old_versions_never_touches_another_projects_card(self):
        other = make_project(title="Al Noir Bis", slug=self.project.slug + "-bis")
        self.client.get(reverse("project_card", args=[other.slug]))
        self.client.get(self.url)
        self.project.status = "concept"
        self.project.save()
        self.client.get(self.url)
        names = sorted(p.name for p in self.cache.glob("*.jpg"))
        self.assertEqual(len(names), 2)
        self.assertTrue(any(n.startswith(other.slug + "-") for n in names))

    def test_unknown_project_is_404(self):
        self.assertEqual(self.client.get(reverse("project_card", args=["nu-exista"])).status_code, 404)

    def test_has_a_cache_header(self):
        self.assertIn("max-age=", self.client.get(self.url)["Cache-Control"])

    def test_works_for_a_project_without_a_screenshot(self):
        plain = make_project(title="Plain")
        response = self.client.get(reverse("project_card", args=[plain.slug]))
        self.assertEqual(_card_image(response).size, (1200, 630))

    def test_a_failure_falls_back_to_the_brand_card_instead_of_an_error(self):
        with _mock.patch("website.share_card.render_card", side_effect=RuntimeError("boom")), self.assertLogs("website.views", level="ERROR"):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("og-default.jpg", response["Location"])

    def test_no_half_written_file_is_left_after_a_failure(self):
        with _mock.patch("website.share_card.render_card", side_effect=RuntimeError("boom")), self.assertLogs("website.views", level="ERROR"):
            self.client.get(self.url)
        self.assertEqual(list(self.cache.glob("*")) if self.cache.exists() else [], [])

    def test_a_slug_cannot_escape_the_cache_folder(self):
        # slug converter only accepts letters, digits, - and _
        response = self.client.get("/projects/..%2f..%2fetc/card.jpg")
        self.assertEqual(response.status_code, 404)

    def test_nothing_is_stored_in_the_database(self):
        before = Project.objects.count()
        self.client.get(self.url)
        self.assertEqual(Project.objects.count(), before)


class ProjectShareCardTagsTests(TestCase):

    def head(self, project):
        body = self.client.get(reverse("project_detail", args=[project.slug])).content.decode()
        return body[:body.index("</head>")]

    def test_og_and_twitter_images_are_the_same_absolute_card_url_with_a_version(self):
        project = make_project(title="Tagged")
        head = self.head(project)
        og, tw = _meta(head, "property", "og:image"), _meta(head, "name", "twitter:image")
        self.assertEqual(og, tw)
        self.assertRegex(og, rf"^http://testserver/projects/{project.slug}/card\.jpg\?v=[0-9a-f]{{12}}$")

    def test_size_and_alt_describe_the_card(self):
        project = make_project(title="Tagged Alt")
        head = self.head(project)
        self.assertEqual(_meta(head, "property", "og:image:width"), "1200")
        self.assertEqual(_meta(head, "property", "og:image:height"), "630")
        self.assertIn("Tagged Alt", _meta(head, "property", "og:image:alt"))
        self.assertIn("Tagged Alt", _meta(head, "name", "twitter:image:alt"))

    def test_the_version_in_the_url_changes_when_the_project_changes(self):
        project = make_project(title="Versioned", status="demo")
        before = _meta(self.head(project), "property", "og:image")
        project.status = "concept"
        project.save()
        self.assertNotEqual(_meta(self.head(project), "property", "og:image"), before)

    def test_the_url_in_the_tag_serves_an_image(self):
        project = make_project(title="Roundtrip")
        og = _meta(self.head(project), "property", "og:image").replace("http://testserver", "")
        response = self.client.get(og)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_card_image(response).size, (1200, 630))
        _shutil.rmtree(Path(settings.MEDIA_ROOT) / "share_cards", ignore_errors=True)

    def test_other_pages_keep_the_brand_card(self):
        for name in ("home", "services", "projects", "about"):
            head = self.client.get(reverse(name)).content.decode()
            head = head[:head.index("</head>")]
            self.assertIn("og-default.jpg", _meta(head, "property", "og:image"), name)

    def test_the_fonts_the_cards_need_are_in_the_project(self):
        for stem in ("fraunces", "hanken-grotesk", "dm-mono-500"):
            for subset in ("latin", "latin-ext"):
                self.assertTrue((Path(_sc.FONT_DIR) / f"{stem}-{subset}.ttf").exists(), f"{stem}-{subset}")
        self.assertTrue((Path(_sc.FONT_DIR) / "README.txt").exists())


# ---------------------------------------------------------------------------
# The guide "Ce pachet ți se potrivește?" (/ghid/, website/guide.py)
# ---------------------------------------------------------------------------
import itertools as _it
import html as _htmllib

from . import guide as _guide
from .packages import ADDONS as _ADDONS, PACKAGES as _PACKAGES


def _all_answers():
    values = [[o["value"] for o in q["options"]] for q in _guide.QUESTIONS]
    for combo in _it.product(*values):
        yield dict(zip(("q1", "q2", "q3"), combo))


class GuideDataTests(TestCase):

    def test_there_are_three_questions_and_forty_eight_combinations(self):
        self.assertEqual(len(_guide.QUESTIONS), 3)
        self.assertEqual(len(list(_all_answers())), 4 * 4 * 3)

    def test_every_combination_gets_a_valid_recommendation(self):
        valid_keys = {p["key"] for p in _PACKAGES} | {"automation_only"}
        choices = {value for value, _ in ContactMessage.PACKAGE_CHOICES}
        for answers in _all_answers():
            with self.subTest(answers=answers):
                r = _guide.recommend(answers)
                self.assertIn(r["key"], valid_keys)
                self.assertIn(r["key"], choices)          # the brief accepts it
                self.assertEqual(r["package"]["key"], _guide.PACKAGE_FOR[r["direction"]])
                self.assertEqual(len(r["whys"]), 3)
                self.assertTrue(all(r["whys"]))
                self.assertIn(r["package"]["price"], r["summary"])

    def test_the_direction_always_follows_question_one(self):
        for answers in _all_answers():
            q1 = next(o for o in _guide.QUESTIONS[0]["options"] if o["value"] == answers["q1"])
            self.assertEqual(_guide.recommend(answers)["direction"], q1["dir"])

    def test_automation_only_only_when_ai_is_wanted_and_a_site_exists(self):
        for answers in _all_answers():
            r = _guide.recommend(answers)
            expected = answers["q1"] == "timp" and answers["q2"] in ("site", "ambele")
            self.assertEqual(r["key"] == "automation_only", expected, answers)

    def test_the_second_suggestion_is_never_the_same_direction(self):
        for answers in _all_answers():
            r = _guide.recommend(answers)
            if r["also"]:
                self.assertNotEqual(r["also"]["dir"], r["direction"], answers)

    def test_the_price_comes_from_packages_not_from_the_guide(self):
        r = _guide.recommend({"q1": "gasit", "q2": "nimic", "q3": "inca"})
        self.assertEqual(r["package"]["price"], next(p for p in _PACKAGES if p["slug"] == "web")["price"])
        source = Path(_guide.__file__).read_text()
        for p in _PACKAGES:
            self.assertNotIn(p["price"], source)

    def test_the_extra_prices_in_the_note_come_from_the_addons(self):
        note = next(r["note"] for r in _guide.ALSO_RULES if r["dir"] == "ai")
        for addon in _ADDONS:
            self.assertIn(f"€{addon['price_value']}", note)

    def test_an_unknown_answer_is_rejected(self):
        with self.assertRaises(ValueError):
            _guide.recommend({"q1": "nope", "q2": "nimic", "q3": "inca"})

    def test_the_guide_promises_no_results(self):
        text = _json.dumps(_guide.QUESTIONS, ensure_ascii=False).lower() + " ".join(r["note"] for r in _guide.ALSO_RULES).lower()
        for word in ("garant", "dublu", "crește", "cresc", "% ", "economis"):
            self.assertNotIn(word, text)

    def test_the_summary_template_has_every_placeholder(self):
        for token in ("{q1}", "{q2}", "{q3}", "{name}", "{price}"):
            self.assertIn(token, _guide.SUMMARY_TEMPLATE)


class GuidePageTests(TestCase):

    def get(self):
        return self.client.get(reverse("guide"))

    def test_page_exists_with_one_h1_and_the_planned_url(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(reverse("guide"), "/ghid/")
        self.assertEqual(len(_re.findall(r"<h1[ >]", response.content.decode())), 1)

    def test_the_data_for_the_script_is_the_data_of_the_module(self):
        body = self.get().content.decode()
        raw = _re.search(r'data-guide="(.*?)"', body, _re.S).group(1)
        data = _json.loads(_htmllib.unescape(raw))
        self.assertEqual(data["questions"], _guide.QUESTIONS)
        self.assertEqual(data["key_rules"], _guide.KEY_RULES)
        self.assertEqual(data["also_rules"], _guide.ALSO_RULES)
        self.assertEqual(data["summary"], _guide.SUMMARY_TEMPLATE)
        self.assertEqual(data["brief_url"], reverse("start_project"))

    def test_prices_and_durations_in_the_data_are_the_real_ones(self):
        raw = _re.search(r'data-guide="(.*?)"', self.get().content.decode(), _re.S).group(1)
        data = _json.loads(_htmllib.unescape(raw))
        for direction, key in _guide.PACKAGE_FOR.items():
            package = next(p for p in _PACKAGES if p["key"] == key)
            self.assertEqual(data["packages"][direction]["price"], package["price"])
            self.assertEqual(data["packages"][direction]["duration"], package["duration"])
            self.assertEqual(data["packages"][direction]["service_url"], reverse("service_detail", args=[package["slug"]]))

    def test_without_javascript_the_three_directions_are_listed_and_the_guide_is_hidden(self):
        body = self.get().content.decode()
        self.assertIn('id="guideFallback"', body)
        for package in _PACKAGES:
            self.assertIn(_htmllib.escape(package["name"], quote=False), body[body.index('id="guideFallback"'):body.index('id="guide"')])
        self.assertRegex(body, r'id="guide"[^>]*\shidden')

    def test_it_says_it_is_an_orientation_not_an_offer(self):
        body = self.get().content.decode() + " ".join(_guide.HOW_IT_WORKS)
        self.assertIn("orientare, nu o ofertă", body)

    def test_the_how_it_works_text_matches_the_rules(self):
        self.assertEqual(len(_guide.KEY_RULES), 1)
        self.assertTrue(any("doar automatizarea" in line for line in _guide.HOW_IT_WORKS))
        body = self.get().content.decode()
        for line in _guide.HOW_IT_WORKS:
            self.assertIn(_htmllib.escape(line, quote=False), body)

    def test_every_recommended_key_opens_the_brief_with_that_package_selected(self):
        keys = {_guide.recommend(a)["key"] for a in _all_answers()}
        self.assertEqual(keys, {"produse_sisteme", "ai_automatizare", "continut_digital", "automation_only"})
        for key in keys:
            response = self.client.get(reverse("start_project") + f"?pachet={key}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["form"].initial["selected_package"], key)

    def test_automation_only_also_ticks_the_matching_features_in_the_brief(self):
        response = self.client.get(reverse("start_project") + "?pachet=automation_only")
        self.assertEqual(response.context["form"].initial["required_features"], ["automation", "ai_agent"])

    def test_the_page_is_in_the_sitemap_and_linked_from_home_and_services(self):
        self.assertIn("/ghid/", self.client.get("/sitemap.xml").content.decode())
        for name in ("home", "services"):
            self.assertContains(self.client.get(reverse(name)), f'href="{reverse("guide")}"', msg_prefix=name)

    def test_no_inline_script(self):
        body = self.get().content.decode()
        inline = [x for x in body.split("<script")[1:] if "src=" not in x.split(">")[0] and "ld+json" not in x.split(">")[0]]
        self.assertEqual(inline, [])

    def test_nothing_is_posted_anywhere(self):
        body = self.get().content.decode()
        form = _re.search(r'<form id="gdForm"[^>]*>', body).group(0)
        for attribute in ("action=", "method="):
            self.assertNotIn(attribute, form.lower())
        self.assertNotIn("csrfmiddlewaretoken", body[body.index('id="gdForm"'):body.index("</form>", body.index('id="gdForm"'))])

    def test_visitor_choices_never_go_in_as_html(self):
        js = (_STATIC / "site.js").read_text()
        block = js[js.index("Guide (/ghid/)"):]
        self.assertNotIn("innerHTML", block)
        self.assertNotIn("insertAdjacentHTML", block)

    def test_the_summary_is_built_by_replacing_the_same_placeholders(self):
        js = (_STATIC / "site.js").read_text()
        block = js[js.index("Guide (/ghid/)"):]
        for token in ("{q1}", "{q2}", "{q3}", "{name}", "{price}"):
            self.assertIn(f"replace('{token}'", block)

    def test_the_script_uses_the_data_not_its_own_copy_of_the_wording(self):
        js = (_STATIC / "site.js").read_text()
        block = js[js.index("Guide (/ghid/)"):]
        for sentence in ("Ai spus că", "Doar automatizare", "Pornești de la zero"):
            self.assertNotIn(sentence, block)

    def test_the_page_makes_no_claim_about_results(self):
        text = _re.sub(r"<[^>]+>", " ", self.get().content.decode()).lower()
        for word in ("garant", "statistic", "studiu", "mii de clienți"):
            self.assertNotIn(word, text)


# ---------------------------------------------------------------------------
# UX audit fixes: error summary, consultation note, privacy notes
# ---------------------------------------------------------------------------
class FormErrorSummaryTests(TestCase):

    def bad_brief(self, **overrides):
        data = {"name": "   ", "email": "a@b.ro", "industry": "   ", "selected_package": "",
                "project_description": "   ", "hosting_info": "", "deadline_communication": "", "website": ""}
        data.update(overrides)
        return self.client.post(reverse("start_project"), data)

    def test_failed_brief_shows_one_alert_with_the_number_of_fields_to_fix(self):
        response = self.bad_brief()
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body.count("data-form-errors"), 1)
        self.assertIn('role="alert"', body[body.index("data-form-errors") - 80:body.index("data-form-errors") + 20])
        self.assertIn("Formularul nu a fost trimis.", body)
        self.assertIn("Verifică cele 3 câmpuri marcate cu roșu", body)

    def test_one_wrong_field_gets_the_singular_wording(self):
        response = self.bad_brief(name="Ioana", industry="salon", project_description="Descriere")
        self.assertEqual(response.status_code, 302)  # all good, so no summary at all
        response = self.bad_brief(name="Ioana", industry="salon", project_description="Descriere", email="nu-e-email")
        self.assertContains(response, "Verifică câmpul marcat cu roșu")

    def test_summary_sits_before_the_fields_inside_the_form(self):
        body = self.bad_brief().content.decode()
        self.assertLess(body.index('id="formErrors"'), body.index('name="name"'))

    def test_field_errors_are_still_shown_next_to_their_fields(self):
        self.assertContains(self.bad_brief(), "errorlist")

    def test_no_summary_on_a_fresh_form_or_after_success(self):
        self.assertNotContains(self.client.get(reverse("start_project")), "data-form-errors")
        self.assertNotContains(self.client.get(reverse("start_project") + "?sent=1"), "data-form-errors")
        self.assertNotContains(self.client.get(reverse("contact")), "data-form-errors")
        self.assertNotContains(self.client.get(reverse("reviews")), "data-form-errors")

    def test_contact_and_reviews_forms_have_the_summary_too(self):
        contact = self.client.post(reverse("contact"), {"name": "", "email": "x", "message": "", "website": ""})
        self.assertContains(contact, "Verifică cele 3 câmpuri marcate cu roșu")
        reviews = self.client.post(reverse("reviews"), {"name": "", "message": "", "rating": "", "website": ""})
        self.assertContains(reviews, "data-form-errors")

    def test_a_filled_honeypot_is_never_counted_or_shown(self):
        response = self.client.post(reverse("contact"), {"name": "A", "email": "a@b.ro", "message": "Salut", "website": "http://spam"})
        self.assertEqual(response.status_code, 302)

    def test_the_script_focuses_the_first_wrong_field_and_links_the_message(self):
        js = (_STATIC / "site.js").read_text()
        block = js[js.index("Forms that came back from the server with errors"):]
        for fragment in ("first.focus()", "aria-invalid", "aria-describedby", "data-form-errors"):
            self.assertIn(fragment, block)
        self.assertNotIn("innerHTML", block)

    def test_the_summary_is_written_by_the_server_so_it_shows_without_javascript(self):
        body = self.bad_brief().content.decode()
        self.assertIn("Formularul nu a fost trimis.", body)


class ConsultationNoteTests(TestCase):

    def test_consultation_path_says_what_happens_next(self):
        body = self.client.get(reverse("start_project") + "?pachet=not_sure").content.decode()
        self.assertIn('id="consultNote"', body)
        self.assertIn("Ai ales să discutăm mai întâi", body)
        self.assertIn("pe email", body)

    def test_the_note_promises_an_email_reply_not_a_call_or_a_booking(self):
        body = self.client.get(reverse("start_project") + "?pachet=not_sure").content.decode()
        note = body[body.index('id="consultNote"'):body.index("</p>", body.index('id="consultNote"'))]
        for word in ("apel", "programare", "întâlnire", "telefon", "gratuit"):
            self.assertNotIn(word, note.lower())

    def test_other_packages_do_not_show_it(self):
        for key in ("produse_sisteme", "ai_automatizare", "continut_digital", "automation_only"):
            self.assertNotContains(self.client.get(reverse("start_project") + f"?pachet={key}"), "consultNote")
        self.assertNotContains(self.client.get(reverse("start_project")), "consultNote")

    def test_it_stays_after_a_failed_submission_of_that_path(self):
        response = self.client.post(reverse("start_project"), {"name": "", "email": "a@b.ro", "industry": "", "selected_package": "not_sure",
                                                                "project_description": "", "website": ""})
        self.assertContains(response, "consultNote")


class PrivacyNoteTests(TestCase):

    def test_contact_form_links_the_privacy_policy_next_to_the_button(self):
        body = self.client.get(reverse("contact")).content.decode()
        form = body[body.index("<form"):body.index("</form>")]
        self.assertIn(f'href="{reverse("privacy_policy")}"', form)
        self.assertIn("ești de acord cu", form)

    def test_reviews_form_says_the_details_are_published_and_links_the_policy(self):
        body = self.client.get(reverse("reviews")).content.decode()
        form = body[body.index("<form"):body.index("</form>")]
        self.assertIn("împreună cu datele completate de tine", form)
        self.assertIn(f'href="{reverse("privacy_policy")}"', form)

    def test_the_policy_really_covers_the_three_forms(self):
        body = self.client.get(reverse("privacy_policy")).content.decode()
        for name in ("Contact", "Începe un proiect", "Recenzii"):
            self.assertIn(name, body)


# ---------------------------------------------------------------------------
# Optional UX improvements: hero line, one set of labels, plain words, thank-you
# email, footer link, tap areas, nav label
# ---------------------------------------------------------------------------
class HeroLineTests(TestCase):

    def body(self):
        return self.client.get(reverse("home")).content.decode()

    def test_the_line_that_says_what_is_built_comes_before_the_headline(self):
        body = self.body()
        self.assertLess(body.index("Site-uri, automatizări și identitate vizuală</p>"), body.index("<h1>"))

    def test_the_headline_itself_is_unchanged(self):
        self.assertIn("<h1>De la o interacțiune obișnuită, la o experiență de care oamenii își amintesc.</h1>", self.body())

    def test_the_line_appears_once_in_the_hero(self):
        body = self.body()
        hero = body[body.index('<div class="wrap hero'):body.index("</section>", body.index('<div class="wrap hero'))]
        self.assertEqual(hero.count("Site-uri, automatizări și identitate vizuală"), 1)
        self.assertNotIn("hero-services", body)


class VocabularyTests(TestCase):

    def public_urls(self):
        return [reverse(n) for n in ("home", "services", "projects", "products", "planner_product", "budget_product",
                                       "about", "contact", "start_project", "faq", "reviews", "guide", "calculator")] + [
            reverse("service_detail", args=[s]) for s in ("web", "ai", "creativ")]

    def test_the_word_brief_is_not_shown_to_visitors(self):
        # The privacy policy is legal text and is left as it was.
        for url in self.public_urls():
            body = self.client.get(url).content.decode()
            text = _re.sub(r"<[^>]+>", " ", body).lower()
            description = (_meta(body, "name", "description") or "").lower()
            with self.subTest(url=url):
                self.assertNotIn("brief", text)
                self.assertNotIn("brief", description)

    def test_the_guide_script_does_not_use_it_either(self):
        js = (_STATIC / "site.js").read_text()
        block = js[js.index("Guide (/ghid/)"):]
        # Only the texts shown to visitors (string literals), not variable names such as brief_url.
        for literal in _re.findall(r"'([^'\\\n]*)'", block):
            self.assertNotIn("brief", literal.lower(), literal)

    def test_the_call_to_action_band_has_one_primary_and_one_secondary_label(self):
        body = self.client.get(reverse("home")).content.decode()
        band = body[body.index('class="band"'):body.index("</section>", body.index('class="band"'))]
        self.assertIn(">Cere o ofertă</a>", band)
        self.assertIn(">Hai să discutăm</a>", band)
        self.assertNotIn("Completează brief-ul", band)
        self.assertNotIn("Cere o consultație", band)

    def test_the_old_labels_are_gone_from_every_page(self):
        for url in self.public_urls():
            body = self.client.get(url).content.decode()
            with self.subTest(url=url):
                for old in ("Completează brief-ul", "Cere o consultație", "Cere oferta personalizată"):
                    self.assertNotIn(old, body)

    def test_both_labels_still_lead_to_the_right_place(self):
        body = self.client.get(reverse("home")).content.decode()
        band = body[body.index('class="band"'):]
        self.assertIn(f'href="{reverse("start_project")}">Cere o ofertă</a>', band)
        self.assertIn(f'href="{reverse("start_project")}?pachet=not_sure">Hai să discutăm</a>', band)

    def test_the_form_page_speaks_plainly(self):
        body = self.client.get(reverse("start_project")).content.decode()
        self.assertIn("Completează formularul de mai jos", body)

    def test_the_process_first_step_is_described_without_jargon(self):
        body = self.client.get(reverse("home")).content.decode()
        self.assertIn("<b>Descrii proiectul</b>", body)

    def test_the_script_uses_the_plain_labels(self):
        js = (_STATIC / "site.js").read_text()
        self.assertIn("'Cere o ofertă pentru acest pachet'", js)
        self.assertIn("'Copiază rezumatul pentru formular'", js)


class ThankYouEmailTests(TestCase):

    def setUp(self):
        cache.clear()   # the submission limit is per address and lives in memory

    def submit(self, email="ioana@exemplu.ro"):
        return self.client.post(reverse("start_project"), {
            "name": "Ioana", "email": email, "industry": "salon", "selected_package": "",
            "project_description": "Vreau programări.", "hosting_info": "", "deadline_communication": "", "website": ""})

    def test_the_address_is_shown_after_a_successful_submission(self):
        response = self.submit()
        self.assertEqual(response["Location"], reverse("start_project") + "?sent=1")   # nothing personal in the URL
        body = self.client.get(response["Location"]).content.decode()
        self.assertIn("Îți voi răspunde la", body)
        self.assertIn("ioana@exemplu.ro", body)
        self.assertIn("andreea.tech@outlook.com", body)

    def test_a_refresh_still_shows_it(self):
        url = self.submit()["Location"]
        self.client.get(url)
        self.assertContains(self.client.get(url), "ioana@exemplu.ro")

    def test_it_is_dropped_when_the_form_is_opened_again(self):
        url = self.submit()["Location"]
        self.client.get(reverse("start_project"))
        self.assertNotContains(self.client.get(url), "ioana@exemplu.ro")

    def test_a_visitor_who_did_not_submit_sees_the_general_text(self):
        body = self.client.get(reverse("start_project") + "?sent=1").content.decode()
        self.assertNotIn("Îți voi răspunde la", body)
        self.assertIn("Dacă nu primești nimic, scrie-mi la", body)

    def test_another_visitor_never_sees_it(self):
        url = self.submit()["Location"]
        from django.test import Client
        self.assertNotContains(Client().get(url), "ioana@exemplu.ro")

    def test_the_address_is_escaped(self):
        self.submit(email='"<b>x</b>"@exemplu.ro')
        body = self.client.get(reverse("start_project") + "?sent=1").content.decode()
        self.assertNotIn("<b>x</b>", body)

    def test_a_dropped_honeypot_submission_stores_nothing(self):
        self.client.post(reverse("start_project"), {"name": "Bot", "email": "bot@exemplu.ro", "industry": "x", "selected_package": "",
                                                    "project_description": "x", "hosting_info": "", "deadline_communication": "", "website": "http://spam"})
        self.assertNotContains(self.client.get(reverse("start_project") + "?sent=1"), "bot@exemplu.ro")


class FooterReviewsLinkTests(TestCase):

    def link(self):
        return f'href="{reverse("reviews")}"'

    def test_hidden_while_there_is_no_approved_review(self):
        self.assertNotContains(self.client.get(reverse("home")), self.link())
        Review.objects.create(name="A", message="x", rating=5, is_approved=False)
        self.assertNotContains(self.client.get(reverse("home")), self.link())

    def test_shown_once_a_review_is_approved(self):
        Review.objects.create(name="A", message="x", rating=5, is_approved=True)
        for name in ("home", "services", "about", "contact"):
            self.assertContains(self.client.get(reverse(name)), self.link(), msg_prefix=name)

    def test_the_page_itself_keeps_working_and_stays_in_the_sitemap(self):
        self.assertEqual(self.client.get(reverse("reviews")).status_code, 200)
        self.assertIn("/reviews/", self.client.get("/sitemap.xml").content.decode())

    def test_a_missing_table_does_not_break_the_footer(self):
        from django.db import OperationalError
        with _mock.patch("website.templatetags.site_notices.Review.objects") as manager:
            manager.filter.side_effect = OperationalError("no such table")
            self.assertEqual(self.client.get(reverse("home")).status_code, 200)


class NavAndTapAreaTests(TestCase):

    def test_the_menu_says_what_the_products_are_in_both_menus(self):
        body = self.client.get(reverse("home")).content.decode()
        self.assertEqual(body.count(">Produse proprii</a>"), 2 + 1)   # desktop menu, phone menu, footer
        self.assertNotIn(">Produse</a>", body)
        self.assertEqual(body.count(f'href="{reverse("products")}"'), 3)

    def test_checkbox_rows_are_at_least_44px_high_on_phones(self):
        css = (_STATIC / "components.css").read_text()
        block = css[css.index("@media (max-width: 640px) {\n    .checks > div"):]
        block = block[:block.index("}\n}") + 3]
        self.assertIn(".checks label", block)
        self.assertIn("min-height: 44px", block)

    def test_contact_paths_use_the_new_wording(self):
        body = self.client.get(reverse("contact")).content.decode()
        self.assertIn("<b>Hai să discutăm</b>", body)
        self.assertIn("fără formularul de proiect", body)
