# Generated by Django 5.1.3 on 2025-01-03 07:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_remove_sociallink_display_name_displayname'),
    ]

    operations = [
        migrations.AddField(
            model_name='experience',
            name='context',
            field=models.TextField(blank=True, null=True),
        ),
    ]
