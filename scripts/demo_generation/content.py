"""Audit contenu lie au metier, sans creer de posts ni medias orphelins."""
def main(argv=None):
    import django
    django.setup()
    from django.apps import apps
    for label in (
        "preparation.ActivityResource",
        "presentations.ActivityPresentation",
        "presentations.PresentationAsset",
        "presentations.PresentationMediaUse",
        "social.Contribution",
        "topics.ActivityTopic",
    ):
        print("CONTENT",label,apps.get_model(label).objects.count())
    print("Aucune ecriture : Presentation represente le contenu, ne le possede pas.")
