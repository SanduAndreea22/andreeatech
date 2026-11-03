from collections import Counter
from html.parser import HTMLParser

from django.core.management.base import BaseCommand

from website.models import Project
from website.sanitize import ALLOWED_ATTRIBUTES, ALLOWED_TAGS, ALLOWED_URL_SCHEMES, sanitize_html

FIELDS = ("problem", "solution", "outcome")

# Removed things that are only presentation: the project will look different.
FORMATTING = {"font", "center", "big", "small", "tt", "mark", "address", "section", "article", "figure",
              "figcaption", "label", "dl", "dt", "dd", "u", "ins", "del", "kbd", "samp", "var", "cite", "abbr"}
# Removed things that are active or risky: removing them is the point.
UNSAFE = {"script", "style", "iframe", "object", "embed", "form", "input", "button", "textarea", "select",
          "meta", "link", "base", "svg", "math", "noscript", "template", "applet", "frame", "frameset",
          "audio", "video", "canvas", "source", "track", "title", "head"}


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = Counter()
        self.attrs = Counter()
        self.bad_urls = Counter()

    def _start(self, tag, attrs):
        self.tags[tag] += 1
        for name, value in attrs:
            self.attrs[f"{tag}[{name}]"] += 1
            if name in ("href", "src") and value:
                cleaned = "".join(ch for ch in value if ch.isprintable() and not ch.isspace()).lower()
                head, sep, _ = cleaned.partition(":")
                if sep and head not in ALLOWED_URL_SCHEMES and "/" not in head and "?" not in head and "#" not in head:
                    self.bad_urls[head + ":"] += 1

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs)


def _collect(html):
    collector = _Collector()
    collector.feed(html or "")
    collector.close()
    return collector


class Command(BaseCommand):
    help = (
        "Read-only report: what the public-page HTML filter would remove from the rich-text "
        "fields (problem, solution, outcome) of every project. Changes nothing in the database."
    )

    def add_arguments(self, parser):
        parser.add_argument("--show-diff", action="store_true",
                            help="Also print the start of the original and of the filtered text for each changed field.")

    def handle(self, *args, **options):
        projects = list(Project.objects.all())
        removed_tags, removed_attrs, bad_urls = Counter(), Counter(), Counter()
        changed = []

        for project in projects:
            for field in FIELDS:
                original = getattr(project, field) or ""
                before, after = _collect(original), _collect(sanitize_html(original))
                tags = before.tags - after.tags
                attrs = Counter({k: v for k, v in (before.attrs - after.attrs).items()
                                 if k.split("[")[0] not in tags})
                urls = before.bad_urls
                if tags or attrs or urls:
                    removed_tags.update(tags)
                    removed_attrs.update(attrs)
                    bad_urls.update(urls)
                    changed.append((project, field, tags, attrs, urls, original))

        total = len(projects) * len(FIELDS)
        self.stdout.write(f"Rich-text audit (read-only). Projects: {len(projects)}, fields checked: {total}.")
        self.stdout.write(f"Fields the filter leaves exactly as they are: {total - len(changed)}.")
        self.stdout.write(f"Fields where it removes something: {len(changed)}.")
        if not changed:
            self.stdout.write(self.style.SUCCESS("Nothing to remove: every project keeps its current look."))
            return

        unsafe = {t: n for t, n in removed_tags.items() if t in UNSAFE}
        formatting = {t: n for t, n in removed_tags.items() if t not in UNSAFE}
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Active or risky content that will be removed (this is what the filter is for):"))
        self.stdout.write("  tags: " + (", ".join(f"<{t}> x{n}" for t, n in sorted(unsafe.items())) or "none"))
        self.stdout.write("  URL schemes: " + (", ".join(f"{s} x{n}" for s, n in sorted(bad_urls.items())) or "none"))
        event_attrs = {k: v for k, v in removed_attrs.items() if k.split("[")[1].startswith("on")}
        self.stdout.write("  event handlers (onclick, onerror, ...): " + (", ".join(f"{k} x{v}" for k, v in sorted(event_attrs.items())) or "none"))
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Presentation that will change (text stays, the styling goes):"))
        other_attrs = {k: v for k, v in removed_attrs.items() if k not in event_attrs}
        self.stdout.write("  tags: " + (", ".join(f"<{t}> x{n}" for t, n in sorted(formatting.items())) or "none"))
        self.stdout.write("  attributes: " + (", ".join(f"{k} x{v}" for k, v in sorted(other_attrs.items())) or "none"))
        self.stdout.write("")
        self.stdout.write("Per project:")
        for project, field, tags, attrs, urls, original in changed:
            parts = [f"<{t}> x{n}" for t, n in sorted(tags.items())] + [f"{k} x{v}" for k, v in sorted(attrs.items())] \
                    + [f"{s} link x{n}" for s, n in sorted(urls.items())]
            self.stdout.write(f"  {project.slug} / {field}: removes " + ", ".join(parts))
            if options["show_diff"]:
                self.stdout.write(f"      before: {original[:240]!r}")
                self.stdout.write(f"      after : {sanitize_html(original)[:240]!r}")
        self.stdout.write("")
        self.stdout.write(f"Allowed tags: {', '.join(sorted(ALLOWED_TAGS))}.")
