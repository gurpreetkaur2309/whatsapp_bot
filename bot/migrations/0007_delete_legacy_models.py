"""Drop the original Route and Booking models.

Both tables are empty (verified: 0 rows each), so nothing is lost. They are
deleted in their own migration rather than being mutated into the new schema so
Django's autodetector cannot mistake the same-named replacements for renames.

Booking is removed first — it holds the FK to Route.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bot", "0006_delete_user"),
    ]

    operations = [
        migrations.DeleteModel(name="Booking"),
        migrations.DeleteModel(name="Route"),
    ]
