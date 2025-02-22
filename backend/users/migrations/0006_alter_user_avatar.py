# Generated by Django 4.2.9 on 2025-01-17 18:43

from django.db import migrations, models
import users.models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0005_merge_20250117_1820"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="avatar",
            field=models.ImageField(
                blank=True, null=True, upload_to=users.models.user_avatar_path
            ),
        ),
    ]
