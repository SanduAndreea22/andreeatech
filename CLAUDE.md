# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Django-based personal portfolio / freelance-services site for Andreea Sandu (deployed at `andreeatech.pythonanywhere.com` on PythonAnywhere). Single Django app (`website`) inside a `config` project, serving marketing pages, a project portfolio, product pages, and lead-capture forms (contact, start-project, reviews).

## Commands

Activate the existing virtualenv before running anything (`venv/` is checked into the working tree):

```powershell
venv\Scripts\Activate.ps1
```

- Run dev server: `python manage.py runserver`
- Make migrations after model changes: `python manage.py makemigrations website`
- Apply migrations: `python manage.py migrate`
- Create a superuser (or use `DJANGO_SUPERUSER_NAME`/`DJANGO_SUPERUSER_PASSWORD`/`DJANGO_SUPERUSER_EMAIL` env vars): `python manage.py createsuperuser`
- Collect static files (whitenoise serves these in production): `python manage.py collectstatic`
- Django shell: `python manage.py shell`
- Tests: `python manage.py test` (test suite in `website/tests.py` is currently empty)

There is no linter/formatter config in the repo — don't assume `flake8`/`black`/`ruff` are wired in.

## Configuration

- Settings live in `config/settings.py` and read everything (SECRET_KEY, DEBUG, DATABASE_URL, superuser creds) from environment variables via `.env` (loaded with `python-dotenv`). A `.env` file exists locally but is not committed.
- `DATABASE_URL` set → Postgres via `dj_database_url`; unset → falls back to local `db.sqlite3`.
- `DEBUG=True` env var required for local media file serving and to avoid the HTTPS-redirect/secure-cookie settings that are forced on whenever `DEBUG` is false (PythonAnywhere terminates TLS in front of the app, so `SECURE_PROXY_SSL_HEADER` trusts its `X-Forwarded-Proto` header).
- Static files use Whitenoise with `CompressedManifestStaticFilesStorage` — after changing/adding files under `static/`, run `collectstatic` or hashed filenames in `staticfiles/` will be stale. On PythonAnywhere this means re-running `collectstatic` in a Bash console after every deploy, then reloading the web app from the Web tab.
- `Procfile` (`gunicorn config.wsgi`) is a leftover from an earlier Render-based deploy plan — PythonAnywhere doesn't read it; the live app is served through PythonAnywhere's own WSGI config pointing at `config.wsgi.application`.
- Outbound email (lead notifications from Contact / Start a Project / Reviews) defaults to the console backend; set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` plus `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`/`ADMIN_EMAIL` in `.env` to actually send.

## Architecture

- `config/` — Django project shell: settings, root `urls.py` (mounts `admin/` and includes `website.urls` at `/`), WSGI/ASGI entrypoints.
- `website/` — the only app; all models, views, forms, and templates live here.
  - `models.py` has four models: `Project` (portfolio case studies — auto-slugged from title on save, has `problem`/`solution`/`outcome` as CKEditor rich-text fields, and a comma-separated `tech_stack` string exposed via `tech_list()`), `ContactMessage` (the detailed "start a project" lead form, with an `industry` choice field and a comma-joined `required_features`), `ContactMessageSimple` (the lightweight `/contact/` form), and `Review` (testimonials, gated by `is_approved` before showing on `/reviews/`).
  - `views.py` and `forms.py` are written as several concatenated code blocks (each with its own imports) rather than one clean module — new views/forms are typically appended in the same style rather than refactored into separate files.
  - Multi-choice form fields (`StartProjectForm.required_features`) are stored as a single comma-separated `CharField` on the model, not a M2M — views manually `", ".join(...)` the cleaned list before saving. Follow this pattern rather than introducing a real many-to-many for similar fields.
  - `projects_list` view pulls one `is_featured` project (ordered by `order`, then newest) to display prominently, then lists the rest excluding that pk.
  - Admin (`admin.py`) uses `list_editable` on the "moderation" flags (`is_read`, `is_approved`, `is_featured`/`order`) so those are toggled directly from the changelist.
- `templates/base.html` is the single site-wide layout: loads Tailwind via the CDN `<script>` tag (not a build pipeline) plus a small block of hand-written CSS variables/utility classes, and `static/website/style.css` for the rest. All page templates extend this and fill `{% block content %}`. Nav links are hardcoded in `base.html` — adding a new page means adding both the `urls.py` entry and a nav link here (desktop + mobile menu).
- `ckeditor` (django-ckeditor) is installed for the `Project` model's rich-text fields only.
- Media uploads (project images) go to `media/projects/`, served locally only when `DEBUG=True` (see `config/urls.py`).
