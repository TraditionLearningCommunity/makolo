from __future__ import annotations

import asyncio
import json
import socket

from asgiref.sync import sync_to_async
from crawlee.configuration import Configuration
from crawlee.storages import RequestQueue
from django.core.management.base import BaseCommand, CommandError

from core.logging_filters import redact_sensitive_text
from observer.django_inbox import drain_crawlee_inbox
from observer.django_runtime import (
    recover_expired_observations,
    schedule_due_observations,
)
from observer.runtime_contracts import ObserverRuntimePolicy
from operations.emergency_controls import is_operational_control_enabled
from operations.models import OperationalControlCode, WorkerState
from operations.services import record_worker_heartbeat


class Command(BaseCommand):
    help = (
        "Lance le worker de contrôle Observer (inbox, scheduling, recovery). "
        "Le Lot 2 n'exécute encore aucune acquisition réseau."
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
        parser.add_argument("--schedule-limit", type=int, default=100)
        parser.add_argument("--recovery-limit", type=int, default=100)
        parser.add_argument("--lease-seconds", type=int, default=300)
        parser.add_argument("--recovery-retry-seconds", type=int, default=60)
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
        for option_name in (
            "inbox_limit",
            "schedule_limit",
            "recovery_limit",
            "lease_seconds",
            "recovery_retry_seconds",
        ):
            if options[option_name] < 1:
                raise CommandError(f"--{option_name.replace('_', '-')} doit être >= 1.")

        policy = ObserverRuntimePolicy(
            lease_seconds=options["lease_seconds"],
            recovery_retry_seconds=options["recovery_retry_seconds"],
        )
        stats = asyncio.run(
            self._run(
                queue_name=queue_name,
                instance_id=options["instance_id"] or socket.gethostname(),
                interval_seconds=options["interval_seconds"],
                inbox_limit=options["inbox_limit"],
                schedule_limit=options["schedule_limit"],
                recovery_limit=options["recovery_limit"],
                policy=policy,
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

    async def _run(
        self,
        *,
        queue_name,
        instance_id,
        interval_seconds,
        inbox_limit,
        schedule_limit,
        recovery_limit,
        policy,
        once,
    ):
        request_queue = None
        last_stats = None
        while True:
            metadata = {
                "mode": "observer-control-plane",
                "queue_name": queue_name,
                "acquisition": "unconfigured_lot2",
                "expected_interval_seconds": interval_seconds,
            }
            enabled = await sync_to_async(
                is_operational_control_enabled,
                thread_sensitive=True,
            )(OperationalControlCode.OBSERVER)
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
                    # A named queue must never be purged merely because the
                    # Observer opens it.
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
                    scheduled = await sync_to_async(
                        schedule_due_observations,
                        thread_sensitive=True,
                    )(
                        policy=policy,
                        limit=schedule_limit,
                    )
                    last_stats = {
                        "inbox_fetched": inbox.fetched,
                        "inbox_absorbed": inbox.absorbed,
                        "inbox_replayed": inbox.replayed,
                        "recovered_observations": recovered,
                        "scheduled_observations": len(scheduled),
                        "acquisition": "not_configured",
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
