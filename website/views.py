from django.shortcuts import render

def home(request):
    return render(request, 'website/home.html')

def services(request):
    return render(request, 'website/services.html')

from django.shortcuts import render, get_object_or_404
from .models import Project


def projects_list(request):
    featured = Project.objects.filter(is_featured=True).first()
    projects = Project.objects.filter(is_featured=False)
    return render(request, "website/projects_list.html", {
        "featured": featured,
        "projects": projects
    })


def project_detail(request, slug):
    project = get_object_or_404(Project, slug=slug)
    return render(request, "website/project_detail.html", {
        "project": project
    })

from django.shortcuts import render
from .forms import StartProjectForm


def start_project(request):
    success = False

    if request.method == "POST":
        form = StartProjectForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)

            # convert list to comma-separated string
            features = form.cleaned_data["required_features"]
            obj.required_features = ", ".join(features)

            obj.save()
            success = True
            form = StartProjectForm()
    else:
        form = StartProjectForm()

    return render(request, "website/start_project.html", {
        "form": form,
        "success": success
    })

from django.shortcuts import render
from .forms import ContactForm


def contact(request):
    success = False

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            success = True
            form = ContactForm()
    else:
        form = ContactForm()

    return render(request, "website/contact.html", {
        "form": form,
        "success": success
    })


def faq(request):
    return render(request, "website/faq.html")

from django.shortcuts import render, redirect
from .models import Review
from .forms import ReviewForm


def reviews(request):

    reviews = Review.objects.filter(is_approved=True)

    form = ReviewForm()

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("reviews")

    return render(request, "website/reviews.html", {
        "reviews": reviews,
        "form": form
    })