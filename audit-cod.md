# Audit cod — Andreea Tech (Django)

**Site:** https://andreeastech.pythonanywhere.com/
**Stack:** Django 6.0.2, sqlite local / Postgres (Neon) în producție via `dj_database_url`, Whitenoise, django-ckeditor
**Fișiere verificate:** `config/settings.py`, `config/urls.py`, `website/models.py`, `website/forms.py`, `website/views.py`, `website/admin.py`, `website/sitemaps.py`, `templates/base.html`, `templates/404.html`, `templates/500.html`, `.gitignore`

---

## OK

- **Secrete și config prin env vars** — `SECRET_KEY`, `DEBUG`, `DATABASE_URL` vin exclusiv din `.env` (`settings.py:15-17,69`), fără fallback hardcodat care ar putea scăpa pe un deploy prost configurat.
- **CSRF activ peste tot** — middleware-ul e prezent, `CSRF_TRUSTED_ORIGINS` e setat corect pentru domeniul de producție (`settings.py:40,127`), toate cele 3 formulare publice sunt `ModelForm` cu `{% csrf_token %}`; zero `@csrf_exempt` în tot codul.
- **Honeypot consecvent** pe `StartProjectForm`, `ContactForm`, `ReviewForm` (`forms.py`), verificat (nu salvat) în fiecare view corespunzător — protecție anti-spam simplă dar corect implementată de trei ori la fel.
- **Cookie-uri/SSL condiționate corect de `DEBUG`** — `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` pornesc doar în producție (`settings.py:149-153`), cu `SECURE_PROXY_SSL_HEADER` potrivit pentru proxy-ul PythonAnywhere.
- **Pagini 404/500 proprii, pe brand** — niciun risc ca un vizitator să vadă vreodată pagina de debug Django.
- **Zero SQL brut** — tot accesul la DB trece prin ORM (niciun `.raw()`/`.extra()`), deci suprafața pentru SQL injection e practic nulă.
- **Generare slug fără coliziuni** — `Project.save()` (`models.py:31-40`) gestionează corect duplicatele cu sufix incremental și exclude `self` la update.
- **`.gitignore` corect** — `.env`, `db.sqlite3`, `venv/`, `staticfiles/` nu ajung niciodată în repo.

---

## De reparat urgent

1. **Tailwind încărcat din CDN în producție** (`templates/base.html:26`) — `cdn.tailwindcss.com` e marcat oficial de Tailwind ca „not for production": recompilează tot CSS-ul din JS la fiecare încărcare, fără purge, blocant în `<head>`, pe fiecare pagină a site-ului. Fix: build local (CLI/PostCSS) și servire prin Whitenoise ca restul static-urilor.
2. **[REZOLVAT]** **`django.views.static.serve` înregistrat necondiționat** pentru `/media/` și `/static/` (`config/urls.py:22-25`), fără gate pe `DEBUG` — contrazice chiar comentariul din CLAUDE.md („served locally only when DEBUG=True"). Django documentează explicit că acest view nu a trecut printr-un audit de securitate/performanță. `/static/` e oricum interceptat de Whitenoise înainte să ajungă aici (deci rută moartă acolo), dar pentru `/media/` chiar el servește fișierele live, neaudit. Fix: gate explicit cu `if settings.DEBUG:` sau mută media pe Whitenoise/storage extern.
3. **[REZOLVAT]** **Nicio configurare `ADMINS`/`LOGGING`** — cu `DEBUG=False`, o excepție 500 pe live nu ajunge nicăieri (fără email, fără log structurat). Combinat cu `fail_silently=True` pe toate notificările de lead (`views.py:13`), un eșec SMTP înseamnă cereri de proiect pierdute silențios, fără urmă. Fix: adaugă `ADMINS` + un `LOGGING` minim, sau loghează explicit excepția din `_notify_admin`.
4. **[REZOLVAT]** **Zero rate-limiting/CAPTCHA pe cele 3 formulare publice** (contact, start-project, reviews) — honeypot-ul oprește bot-uri naive, nu un script care POST-ează direct pe endpoint. Fără throttling, oricine poate umple baza de date și declanșa emailuri nelimitate către `ADMIN_EMAIL`. Fix minim: `django-ratelimit` pe cele 3 view-uri.
5. **[REZOLVAT]** **`reviews` fără confirmare vizuală după submit** (`views.py:138-161`) — spre deosebire de `contact`/`start_project`, acest view nu apelează `messages.success(...)`; vizitatorul e redirecționat fără niciun feedback că recenzia a fost înregistrată.

---

## Îmbunătățiri opționale

- `django-ckeditor` bundlează CKEditor 4.22.1, semnalat chiar de Django (`ckeditor.W001`) cu vulnerabilități nepatch-uite — folosit doar din admin (staff-only), deci risc redus, dar merită migrare la un moment potrivit.
- `psycopg2-binary` în producție — recomandat oficial doar pentru development; pentru producție, Django recomandă `psycopg2` compilat din sursă.
- Lipsește `SECURE_HSTS_SECONDS` — SSL redirect e forțat, dar fără HSTS prima cerere HTTP tot poate fi interceptată înainte de redirect.
- **[REZOLVAT]** Câmpuri `TextField` fără `max_length` (`project_description`, `message` etc.) — un vizitator poate trimite un payload arbitrar de mare printr-un formular public; un `MaxLengthValidator` rezonabil ar preveni abuzul de stocare.
- **[REZOLVAT]** `admin.py:19` — un `import` plasat la mijlocul fișierului în loc de la început; funcționează, dar rupe convenția PEP8.
- **[REZOLVAT]** `website/sitemaps.py` nu include `about` și `privacy_policy` — nimic critic, dar sunt pagini publice care lipsesc din `sitemap.xml`.
