from django.shortcuts import render
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse


def _notify_admin(subject, message):
    if settings.ADMIN_EMAIL:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [settings.ADMIN_EMAIL], fail_silently=True)


def home(request):
    return render(request, 'website/home.html')


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def services(request):
    return render(request, 'website/services.html')


def services_restaurants(request):
    return render(request, 'website/services_restaurants.html')


def services_appointments(request):
    return render(request, 'website/services_appointments.html')


def products(request):
    return render(request, 'website/products.html')


def planner_product(request):
    return render(request, 'website/planner_product.html')


def budget_product(request):
    return render(request, 'website/budget_product.html')

from django.shortcuts import render, get_object_or_404
from .models import Project


def projects_list(request):
    featured = Project.objects.filter(is_featured=True).order_by("order", "-created_at").first()
    # Show the selected project prominently, then show every remaining project.
    # Previously, additional projects marked as featured were hidden completely.
    projects = Project.objects.exclude(pk=featured.pk).order_by("order", "-created_at") if featured else Project.objects.all().order_by("order", "-created_at")
    return render(request, "website/projects_list.html", {
        "featured": featured,
        "projects": projects
    })


def project_detail(request, slug):
    project = get_object_or_404(Project, slug=slug)
    return render(request, "website/project_detail.html", {
        "project": project
    })

from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import StartProjectForm


def start_project(request):
    if request.method == "POST":
        form = StartProjectForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("website"):
                # Honeypot tripped — pretend success, save nothing.
                return redirect("start_project")

            obj = form.save(commit=False)

            # convert list to comma-separated string
            features = form.cleaned_data["required_features"]
            obj.required_features = ", ".join(features)

            obj.save()
            _notify_admin(
                "New project brief — andreeatech",
                f"Name: {obj.name}\nEmail: {obj.email}\nIndustry: {obj.get_industry_display()}\n\n{obj.project_description}"
            )
            messages.success(request, "Request received! I'll review your brief and get back to you within 24 hours.")
            return redirect("start_project")
    else:
        form = StartProjectForm()

    return render(request, "website/start_project.html", {
        "form": form
    })

from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ContactForm


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("website"):
                # Honeypot tripped — pretend success, save nothing.
                return redirect("contact")

            obj = form.save()
            _notify_admin(
                "New contact message — andreeatech",
                f"From: {obj.name} ({obj.email})\n\n{obj.message}"
            )
            messages.success(request, "Your message has been sent successfully.")
            return redirect("contact")
    else:
        form = ContactForm()

    return render(request, "website/contact.html", {
        "form": form
    })


def faq(request):
    return render(request, "website/faq.html")


def privacy_policy(request):
    return render(request, "website/privacy_policy.html")

from django.shortcuts import render, redirect
from .models import Review
from .forms import ReviewForm


def reviews(request):

    reviews = Review.objects.filter(is_approved=True)

    form = ReviewForm()

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("website"):
                # Honeypot tripped — pretend success, save nothing.
                return redirect("reviews")

            obj = form.save()
            _notify_admin(
                "New review (pending approval) — andreeatech",
                f"{obj.name} ({obj.company or 'no company'}) - {obj.rating} stars\n\n{obj.message}"
            )
            return redirect("reviews")

    return render(request, "website/reviews.html", {
        "reviews": reviews,
        "form": form
    })
