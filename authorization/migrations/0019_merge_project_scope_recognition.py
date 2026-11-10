"""Reconcile independent Project and Recognition authority migration branches.

This merge has no operations: both 0018 migrations are additive and must
remain applied. No tables, facts, permissions or existing data are removed.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0018_project_scope"),
        ("authorization", "0018_recognition_permissions"),
    ]
    operations = []
