from urllib.parse import urljoin

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.social_providers import SOCIAL_PROVIDER_SPECS, social_provider_statuses


class Command(BaseCommand):
    help = "Affiche l'état des providers sociaux Makolo sans exposer leurs secrets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--require-all",
            action="store_true",
            help="Retourne une erreur si un provider retenu n'est pas configuré.",
        )

    def handle(self, *args, **options):
        statuses = {item["id"]: item for item in social_provider_statuses()}
        base_url = (settings.MAKOLO_PUBLIC_BASE_URL or "").rstrip("/") + "/"
        missing = []

        for spec in SOCIAL_PROVIDER_SPECS:
            configured = bool(statuses[spec.id]["configured"])
            state = "configured" if configured else "missing"
            callback = urljoin(base_url, spec.callback_path.lstrip("/")) if base_url != "/" else spec.callback_path
            self.stdout.write(f"{spec.name}: {state} | callback={callback}")
            if not configured:
                missing.append(spec.name)

        if options["require_all"] and missing:
            raise CommandError(
                "Providers sociaux non configurés: " + ", ".join(missing)
            )
