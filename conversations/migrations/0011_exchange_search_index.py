from django.db import migrations


def create_index(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        schema_editor.execute("CREATE INDEX conv_entry_body_search_idx ON conversations_pointexchangeentry "
                              "USING gin (UPPER(body) gin_trgm_ops) WHERE moderation_state = 'visible'")


def drop_index(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP INDEX IF EXISTS conv_entry_body_search_idx")
        # pg_trgm may be used by other owners; rollback never drops it.


class Migration(migrations.Migration):
    dependencies = [("conversations", "0010_entry_references")]
    operations = [migrations.RunPython(create_index, drop_index)]
