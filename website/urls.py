from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('services/', views.services, name='services'),
    path('services/restaurants/', views.services_restaurants, name='services_restaurants'),
    path('services/appointments/', views.services_appointments, name='services_appointments'),
    path('products/', views.products, name='products'),
    path('products/planner/', views.planner_product, name='planner_product'),
    path('products/budget/', views.budget_product, name='budget_product'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('start-project/', views.start_project, name='start_project'),
    path('faq/', views.faq, name='faq'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('reviews/', views.reviews, name='reviews'),
    path("projects/", views.projects_list, name="projects"),
    path("projects/<slug:slug>/", views.project_detail, name="project_detail"),

]
