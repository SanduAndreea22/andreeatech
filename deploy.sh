#!/usr/bin/env bash
# Run this on PythonAnywhere (in the andreeatech-venv console) after every
# push to main. Bundles the steps that must always run together — skipping
# collectstatic after a static-file change silently leaves the OLD CSS/JS
# live, since Whitenoise serves hashed files, not the source files directly.
set -e

git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

echo ""
echo "Deploy pulled + migrated + collected. Now reload the web app from the Web tab."
