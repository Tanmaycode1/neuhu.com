# Generated by Django 4.2.9 on 2025-02-03 21:30

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0008_notification"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Notification",
        ),
    ]
