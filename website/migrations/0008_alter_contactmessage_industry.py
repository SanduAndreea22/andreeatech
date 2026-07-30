# Align project inquiry categories with the services offered.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("website", "0007_review")]

    operations = [
        migrations.AlterField(
            model_name="contactmessage",
            name="industry",
            field=models.CharField(
                choices=[
                    ("hospitality", "Hospitality"),
                    ("ecommerce", "E-commerce"),
                    ("service_business", "Service Business"),
                    ("saas", "SaaS / Tech"),
                    ("other", "Other"),
                ],
                max_length=50,
            ),
        ),
    ]
