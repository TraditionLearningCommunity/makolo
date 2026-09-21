from __future__ import annotations

import asyncio
import json
import socket

from asgiref.sync import sync_to_async
from crawlee.configuration import Configuration
from crawlee.storages import RequestQueue
from django.core.management.base import BaseCommand, CommandError

from core.logging_filters import redact_sensitive_text
from observer.browser_contracts import BrowserAcquisitionPolicy
from observer.django_browser import build_browser_render_acquisition
from observer.django_http import build_direct_http_acquisition
from observer.django_inbox import drain_crawlee_inbox
from observer.django_runtime import (
    claim_observations,
    execute_claim,
    observation_backlog,
    observation_backlog_all_profiles,
    recover_expired_observations,
)
from observer.errors import ObserverContractError
from observer.http_contracts import HttpAcquisitionPolicy
from observer.runtime_contracts import ObserverRuntimePolicy
from operations.emergency_controls import is_operational_control_enabled
from operations.models import OperationalControlCode, WorkerState
from operations.services import record_worker_heartbeat


class Command(BaseCommand):
    help = (
        "Lance le worker Observer : inbox, recovery et acquisition "
        "publique HTTP directe ou Browser/JS contrôlée."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--queue-name",
            required=True,
            help=(
                "Nom de la RequestQueue Crawlee déjà utilisée pour le handoff "
                "Prospecteur → Observateur."
            ),
        )
        parser.add_argument("--instance-id", default=socket.gethostname())
        parser.add_argument("--interval-seconds", type=float, default=5.0)
        parser.add_argument("--inbox-limit", type=int, default=100)
        parser.add_argument("--recovery-limit", type=int, default=100)
        parser.add_argument("--claim-limit", type=int, default=1)
        parser.add_argument("--lease-seconds", type=int, default=300)
        parser.add_argument("--recovery-retry-seconds", type=int, default=60)
        parser.add_argument(
            "--watch-interval-seconds",
            type=int,
            default=None,
            help=(
                "Cadence autonome de revisit en secondes. Absente par "
                "défaut : aucune cadence de production n'est inventée."
            ),
        )
        parser.add_argument(
            "--enable-http-acquisition",
            action="store_true",
            help=(
                "Active explicitement les connexions Internet HTTP du Lot 3. "
                "Sans ce flag, le worker reste control-plane uniquement."
            ),
        )
        parser.add_argument(
            "--enable-browser-acquisition",
            action="store_true",
            help=(
                "Active explicitement le profil Browser/JS public du Lot 4. "
                "Mutuellement exclusif avec --enable-http-acquisition."
            ),
        )
        parser.add_argument(
            "--http-user-agent",
            default=None,
            help=(
                "User-Agent opérateur explicite utilisé pour l'acquisition "
                "publique. Obligatoire avec toute acquisition HTTP/Browser."
            ),
        )
        parser.add_argument(
            "--robots-user-agent",
            default="MakoloObserver",
            help=(
                "Product token RFC 9309 utilisé pour robots.txt. "
                "Il doit être inclus dans --http-user-agent."
            ),
        )
        parser.add_argument(
            "--http-connect-timeout-seconds",
            type=float,
            default=10.0,
        )
        parser.add_argument(
            "--http-read-timeout-seconds",
            type=float,
            default=20.0,
        )
        parser.add_argument(
            "--http-max-observation-seconds",
            type=int,
            default=180,
        )
        parser.add_argument(
            "--http-max-redirects",
            type=int,
            default=5,
        )
        parser.add_argument(
            "--http-max-wire-bytes",
            type=int,
            default=8 * 1024 * 1024,
        )
        parser.add_argument(
            "--http-max-decoded-bytes",
            type=int,
            default=16 * 1024 * 1024,
        )
        parser.add_argument(
            "--robots-max-bytes",
            type=int,
            default=256 * 1024,
        )
        parser.add_argument(
            "--robots-cache-seconds",
            type=int,
            default=3600,
        )
        parser.add_argument(
            "--http-host-interval-seconds",
            type=float,
            default=1.0,
        )
        parser.add_argument(
            "--http-host-lease-seconds",
            type=int,
            default=240,
        )
        parser.add_argument(
            "--http-retry-seconds",
            type=int,
            default=60,
        )
        parser.add_argument(
            "--http-allowed-port",
            action="append",
            type=int,
            default=None,
            help=(
                "Port TCP HTTP(S) autorisé. Répéter l'option pour "
                "plusieurs ports. Par défaut : 80 et 443."
            ),
        )
        parser.add_argument(
            "--allow-https-to-http-redirect",
            action="store_true",
            help=(
                "Autorise explicitement un downgrade HTTPS→HTTP. "
                "Refusé par défaut."
            ),
        )
        parser.add_argument(
            "--browser-locale",
            default="en-US",
        )
        parser.add_argument(
            "--browser-viewport-width",
            type=int,
            default=1280,
        )
        parser.add_argument(
            "--browser-viewport-height",
            type=int,
            default=720,
        )
        parser.add_argument(
            "--browser-settle-timeout-seconds",
            type=int,
            default=5,
        )
        parser.add_argument(
            "--browser-max-requests",
            type=int,
            default=64,
        )
        parser.add_argument(
            "--browser-max-total-wire-bytes",
            type=int,
            default=24 * 1024 * 1024,
        )
        parser.add_argument(
            "--browser-max-total-decoded-bytes",
            type=int,
            default=32 * 1024 * 1024,
        )
        parser.add_argument(
            "--browser-max-rendered-dom-bytes",
            type=int,
            default=4 * 1024 * 1024,
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Exécute un seul cycle puis s'arrête proprement.",
        )

    def handle(self, *args, **options):
        queue_name = (options["queue_name"] or "").strip()
        if not queue_name:
            raise CommandError("--queue-name ne peut pas être vide.")
        if options["interval_seconds"] <= 0:
            raise CommandError("--interval-seconds doit être > 0.")
        http_enabled = bool(options["enable_http_acquisition"])
        browser_enabled = bool(options["enable_browser_acquisition"])
        if http_enabled and browser_enabled:
            raise CommandError(
                "--enable-http-acquisition et "
                "--enable-browser-acquisition sont mutuellement exclusifs."
            )
        acquisition_enabled = http_enabled or browser_enabled
        if acquisition_enabled and not (
            options["http_user_agent"] or ""
        ).strip():
            raise CommandError(
                "--http-user-agent est obligatoire avec une acquisition "
                "HTTP ou Browser."
            )
        for option_name in (
            "inbox_limit",
            "recovery_limit",
            "claim_limit",
            "lease_seconds",
            "recovery_retry_seconds",
            "http_max_observation_seconds",
            "http_max_wire_bytes",
            "http_max_decoded_bytes",
            "robots_max_bytes",
            "robots_cache_seconds",
            "http_host_lease_seconds",
            "http_retry_seconds",
            "browser_viewport_width",
            "browser_viewport_height",
            "browser_settle_timeout_seconds",
            "browser_max_requests",
            "browser_max_total_wire_bytes",
            "browser_max_total_decoded_bytes",
            "browser_max_rendered_dom_bytes",
        ):
            if options[option_name] < 1:
                raise CommandError(
                    f"--{option_name.replace('_', '-')} doit être >= 1."
                )
        allowed_ports = tuple(
            options["http_allowed_port"] or (80, 443)
        )
        if any(
            port < 1 or port > 65535
            for port in allowed_ports
        ):
            raise CommandError(
                "--http-allowed-port doit être compris entre 1 et 65535."
            )
        if acquisition_enabled and (
            options["lease_seconds"]
            <= options["http_max_observation_seconds"]
        ):
            raise CommandError(
                "--lease-seconds doit être strictement supérieur à "
                "--http-max-observation-seconds."
            )
        if options["http_max_redirects"] < 0:
            raise CommandError("--http-max-redirects doit être >= 0.")
        for option_name in (
            "http_connect_timeout_seconds",
            "http_read_timeout_seconds",
        ):
            if options[option_name] <= 0:
                raise CommandError(
                    f"--{option_name.replace('_', '-')} doit être > 0."
                )
        if options["http_host_interval_seconds"] < 0:
            raise CommandError(
                "--http-host-interval-seconds doit être >= 0."
            )
        if (
            options["watch_interval_seconds"] is not None
            and options["watch_interval_seconds"] < 1
        ):
            raise CommandError(
                "--watch-interval-seconds doit être >= 1."
            )

        http_policy = None
        browser_policy = None
        acquisition = None
        acquisition_mode = "observer-control-plane"
        acquisition_label = "disabled"

        if acquisition_enabled:
            try:
                http_policy = HttpAcquisitionPolicy(
                    user_agent=options["http_user_agent"],
                    robots_user_agent=options["robots_user_agent"],
                    connect_timeout_seconds=(
                        options["http_connect_timeout_seconds"]
                    ),
                    read_timeout_seconds=(
                        options["http_read_timeout_seconds"]
                    ),
                    max_observation_seconds=(
                        options["http_max_observation_seconds"]
                    ),
                    max_redirects=options["http_max_redirects"],
                    max_wire_bytes=options["http_max_wire_bytes"],
                    max_decoded_bytes=options["http_max_decoded_bytes"],
                    robots_max_bytes=options["robots_max_bytes"],
                    robots_cache_seconds=options["robots_cache_seconds"],
                    host_min_interval_seconds=(
                        options["http_host_interval_seconds"]
                    ),
                    host_lease_seconds=(
                        options["http_host_lease_seconds"]
                    ),
                    retry_seconds=options["http_retry_seconds"],
                    allowed_ports=allowed_ports,
                    allow_https_to_http_redirect=(
                        options["allow_https_to_http_redirect"]
                    ),
                )
                if browser_enabled:
                    browser_policy = BrowserAcquisitionPolicy(
                        http_policy=http_policy,
                        locale=options["browser_locale"],
                        viewport_width=options[
                            "browser_viewport_width"
                        ],
                        viewport_height=options[
                            "browser_viewport_height"
                        ],
                        settle_timeout_seconds=options[
                            "browser_settle_timeout_seconds"
                        ],
                        max_requests=options[
                            "browser_max_requests"
                        ],
                        max_total_wire_bytes=options[
                            "browser_max_total_wire_bytes"
                        ],
                        max_total_decoded_bytes=options[
                            "browser_max_total_decoded_bytes"
                        ],
                        max_rendered_dom_bytes=options[
                            "browser_max_rendered_dom_bytes"
                        ],
                    )
            except ObserverContractError as exc:
                raise CommandError(str(exc)) from exc

        if browser_policy is not None:
            runtime_policy = ObserverRuntimePolicy(
                profile_key=browser_policy.profile_key,
                profile_fingerprint=(
                    browser_policy.profile_fingerprint
                ),
                policy_fingerprint=(
                    browser_policy.policy_fingerprint
                ),
                lease_seconds=options["lease_seconds"],
                recovery_retry_seconds=(
                    options["recovery_retry_seconds"]
                ),
                watch_interval_seconds=(
                    options["watch_interval_seconds"]
                ),
            )
            acquisition = build_browser_render_acquisition(
                policy=browser_policy,
            )
            acquisition_mode = "observer-browser-render"
            acquisition_label = "browser_render_v1"
        elif http_policy is not None:
            runtime_policy = ObserverRuntimePolicy(
                profile_key="public-http",
                profile_fingerprint=http_policy.profile_fingerprint,
                policy_fingerprint=http_policy.policy_fingerprint,
                lease_seconds=options["lease_seconds"],
                recovery_retry_seconds=(
                    options["recovery_retry_seconds"]
                ),
                watch_interval_seconds=(
                    options["watch_interval_seconds"]
                ),
            )
            acquisition = build_direct_http_acquisition(
                policy=http_policy,
            )
            acquisition_mode = "observer-direct-http"
            acquisition_label = "direct_http_v1"
        else:
            runtime_policy = ObserverRuntimePolicy(
                lease_seconds=options["lease_seconds"],
                recovery_retry_seconds=(
                    options["recovery_retry_seconds"]
                ),
                watch_interval_seconds=(
                    options["watch_interval_seconds"]
                ),
            )

        stats = asyncio.run(
            self._run(
                queue_name=queue_name,
                instance_id=(
                    options["instance_id"] or socket.gethostname()
                ),
                interval_seconds=options["interval_seconds"],
                inbox_limit=options["inbox_limit"],
                recovery_limit=options["recovery_limit"],
                claim_limit=options["claim_limit"],
                policy=runtime_policy,
                acquisition=acquisition,
                acquisition_mode=acquisition_mode,
                acquisition_label=acquisition_label,
                once=bool(options["once"]),
            )
        )
        if stats is not None:
            self.stdout.write(
                self.style.SUCCESS(
                    json.dumps(stats, ensure_ascii=False, default=str)
                )
            )

    async def _heartbeat(self, **kwargs):
        return await sync_to_async(
            record_worker_heartbeat,
            thread_sensitive=True,
        )(**kwargs)

    async def _control_enabled(self):
        return await sync_to_async(
            is_operational_control_enabled,
            thread_sensitive=True,
        )(OperationalControlCode.OBSERVER)

    async def _run(
        self,
        *,
        queue_name,
        instance_id,
        interval_seconds,
        inbox_limit,
        recovery_limit,
        claim_limit,
        policy,
        acquisition,
        acquisition_mode,
        acquisition_label,
        once,
    ):
        request_queue = None
        last_stats = None
        while True:
            metadata = {
                "mode": acquisition_mode,
                "queue_name": queue_name,
                "acquisition": acquisition_label,
                "expected_interval_seconds": interval_seconds,
            }
            if acquisition is not None:
                metadata["profile_fingerprint"] = (
                    policy.profile_fingerprint
                )
                metadata["policy_fingerprint"] = (
                    policy.policy_fingerprint
                )
            enabled = await self._control_enabled()
            if not enabled:
                last_stats = {"operational_control": "disabled"}
                await self._heartbeat(
                    worker_name="observer",
                    instance_id=instance_id,
                    state=WorkerState.STOPPED,
                    metadata={**metadata, "last_stats": last_stats},
                    cycle_finished=True,
                )
            else:
                if request_queue is None:
                    configuration = Configuration(purge_on_start=False)
                    request_queue = await RequestQueue.open(
                        name=queue_name,
                        configuration=configuration,
                    )
                await self._heartbeat(
                    worker_name="observer",
                    instance_id=instance_id,
                    state=WorkerState.HEALTHY,
                    metadata=metadata,
                    cycle_started=True,
                )
                try:
                    inbox = await drain_crawlee_inbox(
                        request_queue,
                        limit=inbox_limit,
                    )
                    recovered = await sync_to_async(
                        recover_expired_observations,
                        thread_sensitive=True,
                    )(
                        policy=policy,
                        limit=recovery_limit,
                    )

                    outcomes = {
                        "claimed_observations": 0,
                        "observed": 0,
                        "not_modified": 0,
                        "failed": 0,
                    }
                    if acquisition is not None:
                        for _index in range(claim_limit):
                            if not await self._control_enabled():
                                break
                            claims = await sync_to_async(
                                claim_observations,
                                thread_sensitive=True,
                            )(
                                worker_id=instance_id,
                                policy=policy,
                                limit=1,
                            )
                            if not claims:
                                break
                            outcomes["claimed_observations"] += 1
                            observation = await sync_to_async(
                                execute_claim,
                                thread_sensitive=True,
                            )(
                                claims[0],
                                acquisition=acquisition,
                                policy=policy,
                            )
                            if observation.outcome in outcomes:
                                outcomes[observation.outcome] += 1

                    if acquisition is not None:
                        backlog = await sync_to_async(
                            observation_backlog,
                            thread_sensitive=True,
                        )(
                            policy=policy,
                        )
                    else:
                        backlog = await sync_to_async(
                            observation_backlog_all_profiles,
                            thread_sensitive=True,
                        )()
                    last_stats = {
                        "inbox_fetched": inbox.fetched,
                        "inbox_absorbed": inbox.absorbed,
                        "inbox_replayed": inbox.replayed,
                        "recovered_observations": recovered,
                        **outcomes,
                        "pending_handoffs": backlog.pending_handoffs,
                        "due_retries": backlog.due_retries,
                        "due_watches": backlog.due_watches,
                        "open_observations": backlog.open_observations,
                        "acquisition": acquisition_label,
                    }
                except Exception as exc:
                    await self._heartbeat(
                        worker_name="observer",
                        instance_id=instance_id,
                        state=WorkerState.DEGRADED,
                        last_error=redact_sensitive_text(str(exc)),
                        metadata=metadata,
                        cycle_finished=True,
                    )
                    raise
                await self._heartbeat(
                    worker_name="observer",
                    instance_id=instance_id,
                    state=WorkerState.HEALTHY,
                    metadata={**metadata, "last_stats": last_stats},
                    cycle_finished=True,
                )

            if once:
                if enabled:
                    await self._heartbeat(
                        worker_name="observer",
                        instance_id=instance_id,
                        state=WorkerState.STOPPED,
                        metadata={**metadata, "last_stats": last_stats},
                    )
                return last_stats
            await asyncio.sleep(interval_seconds)
