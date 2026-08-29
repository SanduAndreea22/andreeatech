# Andreea Tech — context & standing rules

Portfolio/freelance site for Andreea Sandu (andreeastech.pythonanywhere.com),
built with Django. Read this before making assumptions about business
context, audience, or workflow.

## Business positioning — do not assume otherwise

- **Positioning: "Antreprenori care vor să-și ducă business-ul la
  următorul nivel."** Generic small-business/entrepreneur audience — NOT
  restricted to restaurants/cafenele/saloane/clinici. That narrower niche
  is outdated; it still shows up inside her own saved audit prompt
  templates (PROMPT 1-5, pasted repeatedly in conversations) — the
  templates are stale, don't treat their CONTEXT line as current fact.
  Cross-check against actual site copy (home.html hero already says
  "antreprenori", not a specific niche) before repeating old framing.
- Keep every trust/marketing claim strictly grounded in what's actually
  true and verifiable on the live site right now — never propose or
  build a feature that implies a track record (review counts, ratings,
  "X proiecte livrate" style stats, etc.) beyond what's genuinely there.
  Ask her before adding anything of that kind, rather than assuming.

(This section is intentionally general — this repo is public on GitHub,
so avoid writing specifics here that read as a weakness to a visitor
browsing the source. Ask Andreea directly if you need the real numbers.)

## Standing technical rules

- **No `style=""` attributes or `<style>` tags anywhere in HTML.**
  Everything visual goes in `static/website/style.css`. This is a hard,
  frequently-repeated rule — don't add inline styles even for quick fixes.
- Run the Django test suite before every push (`python manage.py test`
  with `DEBUG=True SECRET_KEY=...` env vars — see below for the venv).
- Commit and push directly to `main`. No PR workflow for this project
  unless explicitly asked.
- Deploy (she runs this manually on PythonAnywhere after every push):
  `cd ~/andreeatech && workon andreeatech-venv && git pull origin main &&
  python manage.py collectstatic --noinput`, then Reload from the Web tab.
- **PythonAnywhere free tier cannot send outbound email at all.** Don't
  build or suggest features that rely on `send_mail`/`mail_admins`
  actually delivering (lead notifications, error alerts) — they will
  silently no-op. `LOGGING` in `config/settings.py` intentionally does
  NOT wire up `mail_admins` for this reason; errors are only visible in
  PythonAnywhere's own error log.
- Admin panel lives at `/panou-admin/`, not the Django default `/admin/`
  (moved deliberately — see git history).
- Current theme is **dark** (see `:root` in `style.css`) — this followed
  a period of back-and-forth with a light theme in a parallel session.
  Don't revert to light without an explicit request.
- She previously declined a floating call/WhatsApp button on mobile
  ("nu vreau să sune toți nebunii") — don't re-suggest it.

## Dev/test setup

Project needs Python 3.12; sandbox default may be older. Tests run
against local sqlite (never the real Postgres), from repo root:
```
DEBUG=True SECRET_KEY=test-secret-key-for-ci python manage.py test
```
