import logging

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse

from .forms import ContactForm, ReviewForm, StartProjectForm
from .models import Certification, ContactMessage, Project, Review
from .packages import PACKAGES

logger = logging.getLogger(__name__)


def _notify_admin(subject, message):
    if settings.ADMIN_EMAIL:
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [settings.ADMIN_EMAIL], fail_silently=False)
        except Exception:
            logger.exception("Failed to send admin notification email: %s", subject)


def _client_ip(request):
    # The LAST entry is the one PythonAnywhere's proxy itself appended
    # (closest hop to us), so it's the one a client can't forge by sending
    # their own X-Forwarded-For header — taking the first entry would let
    # spammers rotate a fake IP on every request and dodge the rate limit.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _rate_limited(request, form_name, limit=5, window_seconds=3600):
    """Simple per-IP submission cap for public forms. Returns True if the
    caller has already hit the limit and the submission should be dropped.

    Uses Django's default in-memory cache, which lives inside a single
    process — correct as long as the app runs on one worker (true today on
    PythonAnywhere's free tier). If this ever moves to a multi-process/
    multi-server setup, switch CACHES to a shared backend (Redis/Memcached)
    or the limit won't be enforced consistently across workers.
    """
    key = f"ratelimit:{form_name}:{_client_ip(request)}"
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, window_seconds)
    return False


def home(request):
    return render(request, 'website/home.html', {"packages": PACKAGES})


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def products(request):
    return render(request, 'website/products.html')


def planner_product(request):
    return render(request, 'website/planner_product.html')


def budget_product(request):
    return render(request, 'website/budget_product.html')


def projects_list(request):
    # Every project marked as featured gets its own prominent card, in order;
    # everything else shows in the regular grid below.
    featured_projects = Project.objects.filter(is_featured=True).order_by("order", "-created_at")
    projects = Project.objects.exclude(is_featured=True).order_by("order", "-created_at")
    return render(request, "website/projects_list.html", {
        "featured_projects": featured_projects,
        "projects": projects
    })


def project_detail(request, slug):
    project = get_object_or_404(Project, slug=slug)
    image_path = project.image.url if project.image else static("website/poza_me.JPG")
    return render(request, "website/project_detail.html", {
        "project": project,
        "share_image_url": request.build_absolute_uri(image_path),
    })


def start_project(request):
    if request.method == "POST":
        form = StartProjectForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("website"):
                # Honeypot tripped — pretend success, save nothing.
                return redirect("start_project")

            if _rate_limited(request, "start_project"):
                messages.error(request, "Ai trimis mai multe cereri într-un timp scurt. Te rog încearcă din nou peste puțin timp.")
                return redirect("start_project")

            obj = form.save(commit=False)

            # convert list to comma-separated string
            features = form.cleaned_data["required_features"]
            obj.required_features = ", ".join(features)

            obj.save()
            _notify_admin(
                "New project brief — andreeatech",
                f"Name: {obj.name}\nEmail: {obj.email}\nIndustry: {obj.industry}\nPachet: {obj.get_selected_package_display() if obj.selected_package else 'nespecificat'}\n\n{obj.project_description}"
            )
            messages.success(request, "Cerere primită! Îți analizez brief-ul și revin cu un răspuns în maximum 24 de ore.")
            return redirect(f"{reverse('start_project')}?sent=1")
    else:
        initial = {}
        package = request.GET.get("pachet")
        if package in dict(ContactMessage.PACKAGE_CHOICES):
            initial["selected_package"] = package
            if package == "automation_only":
                initial["required_features"] = ["automation", "ai_agent"]
        form = StartProjectForm(initial=initial)

    return render(request, "website/start_project.html", {
        "form": form,
        "just_submitted": request.GET.get("sent") == "1",
    })


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("website"):
                # Honeypot tripped — pretend success, save nothing.
                return redirect("contact")

            if _rate_limited(request, "contact"):
                messages.error(request, "Ai trimis mai multe mesaje într-un timp scurt. Te rog încearcă din nou peste puțin timp.")
                return redirect("contact")

            obj = form.save()
            _notify_admin(
                "New contact message — andreeatech",
                f"From: {obj.name} ({obj.email})\n\n{obj.message}"
            )
            messages.success(request, "Mesajul tău a ajuns la mine — răspund cât pot de repede.")
            return redirect("contact")
    else:
        form = ContactForm()

    return render(request, "website/contact.html", {
        "form": form
    })


def about(request):
    certifications = Certification.objects.all()
    return render(request, "website/about.html", {
        "certifications": certifications
    })


def faq(request):
    return render(request, "website/faq.html")


def privacy_policy(request):
    return render(request, "website/privacy_policy.html")


def reviews(request):

    reviews = Review.objects.filter(is_approved=True)

    form = ReviewForm()

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("website"):
                # Honeypot tripped — pretend success, save nothing.
                return redirect("reviews")

            if _rate_limited(request, "reviews"):
                messages.error(request, "Ai trimis mai multe recenzii într-un timp scurt. Te rog încearcă din nou peste puțin timp.")
                return redirect("reviews")

            obj = form.save()
            _notify_admin(
                "New review (pending approval) — andreeatech",
                f"{obj.name} ({obj.company or 'no company'}) - {obj.rating} stars\n\n{obj.message}"
            )
            messages.success(request, "Mulțumesc pentru recenzie! Va apărea pe site după ce o aprob.")
            return redirect("reviews")

    return render(request, "website/reviews.html", {
        "reviews": reviews,
        "form": form
    })
