import logging

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage
from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """WhiteNoise's hashing + compressing storage, minus one failure mode.

    The stock class raises ValueError (a 500 on every page that uses the file)
    when a template refers to a static file that `collectstatic` has not
    collected, for example after a `git pull` without running deploy.sh. Here
    the page still renders: the file is served under its plain name and a
    warning is logged, so the missing `collectstatic` shows up in the error log.
    Files that were collected keep their hashed names as usual.

    Only files that exist in the project's static folders get this treatment.
    A name that exists nowhere keeps the stock behaviour (ValueError): WhiteNoise
    relies on that signal when it probes file names at start-up, and a typo in a
    template should stay loud (tests catch it).
    """

    def url(self, name, force=False):
        try:
            return super().url(name, force)
        except ValueError:
            if not finders.find(name):
                raise
            logger.warning(
                "Static file %r is not in the manifest, serving it unhashed. Run `collectstatic`.", name
            )
            return StaticFilesStorage.url(self, name)
