from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from django.contrib.sitemaps.views import sitemap
from website.sitemaps import StaticViewSitemap, ProjectSitemap
from website.views import robots_txt

sitemaps = {
    "static": StaticViewSitemap,
    "projects": ProjectSitemap,
}

urlpatterns = [
    # Moved off the default /admin/ path — django-axes already blocks
    # brute force here, this just keeps it off the generic scanner lists.
    path('panou-admin/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('', include('website.urls')),  # links your site
    # Whitenoise only serves STATIC_ROOT, not MEDIA_ROOT, and PythonAnywhere's
    # static-file mapping for /media/ lives in its dashboard, not in this repo
    # — easy to forget and silently 404 in production. Traffic here is a
    # handful of project/certification images, not high-volume uploads, so
    # serving it directly is an acceptable trade-off for not depending on an
    # out-of-repo config step (see audit-cod.md).
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
