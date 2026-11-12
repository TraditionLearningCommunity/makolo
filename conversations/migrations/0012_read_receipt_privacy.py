from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("conversations", "0011_exchange_search_index")]
    operations = [migrations.AddField("conversationuserstate", "share_read_receipts", models.BooleanField(default=True))]
