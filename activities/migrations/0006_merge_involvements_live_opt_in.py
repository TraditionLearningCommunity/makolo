"""Join independent Activity involvement and Occurrence Live migration branches.

Both 0005 migrations are retained for already-deployed development databases.
No schema or data operation is required: Django executes both dependencies.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0005_activity_involvements"),
        ("activities", "0005_occurrence_live_opt_in"),
    ]

    operations = []
