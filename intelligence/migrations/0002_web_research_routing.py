from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intelligence", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="providerconnection",
            name="protocol",
            field=models.CharField(
                choices=[
                    ("openai_compatible", "OpenAI-compatible"),
                    ("openai_responses_web", "OpenAI Responses Web"),
                    ("tavily_search", "Tavily Search"),
                    ("exa_search", "Exa Search"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="providerconnection",
            name="default_model",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AlterField(
            model_name="intelligenceroute",
            name="capability",
            field=models.CharField(
                choices=[
                    ("text_generate", "text_generate"),
                    ("structured_generate", "structured_generate"),
                    ("embed", "embed"),
                    ("rerank", "rerank"),
                    ("web_research", "web_research"),
                ],
                max_length=32,
            ),
        ),
    ]
