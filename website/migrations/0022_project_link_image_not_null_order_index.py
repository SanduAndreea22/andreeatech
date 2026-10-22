import django.core.validators
import website.models
from django.db import migrations, models


def backfill_null_strings(apps, schema_editor):
    # link/image are moving from null=True to the string-based default of
    # "" means empty — existing NULL rows must be converted first or the
    # NOT NULL constraint below fails to apply.
    Project = apps.get_model("website", "Project")
    Project.objects.filter(link__isnull=True).update(link="")
    Project.objects.filter(image__isnull=True).update(image="")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("website", "0021_project_category_project_portfolio_pdf_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_null_strings, noop_reverse),
        migrations.AlterField(
            model_name="project",
            name="link",
            field=models.URLField(blank=True),
        ),
        migrations.AlterField(
            model_name="project",
            name="image",
            field=models.ImageField(
                blank=True,
                upload_to="projects/",
                validators=[website.models.validate_image_max_size],
            ),
        ),
        migrations.AlterField(
            model_name="project",
            name="order",
            field=models.IntegerField(default=0, db_index=True),
        ),
        migrations.AlterField(
            model_name="certification",
            name="order",
            field=models.IntegerField(default=0, db_index=True),
        ),
        migrations.AlterField(
            model_name="project",
            name="portfolio_pdf",
            field=models.FileField(
                blank=True,
                null=True,
                help_text="PDF descărcabil (ex. un concept/portofoliu demonstrativ) — opțional. Apare ca buton de descărcare pe pagina proiectului.",
                upload_to="project_files/",
                validators=[
                    django.core.validators.FileExtensionValidator(["pdf"]),
                    website.models.validate_pdf_max_size,
                    website.models.validate_pdf_content,
                ],
            ),
        ),
    ]
