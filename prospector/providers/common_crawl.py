from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Mapping, Optional, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from prospector.errors import (
    ProspectorContractError,
    ProspectorSourceError,
    ProspectorSourceRateLimitError,
)
from prospector.source_contracts import (
    IndexedResource,
    ProspectingMission,
    SourceBatch,
    SourceCheckpoint,
)

COLLECTIONS_URL = "https://index.commoncrawl.org/collinfo.json"
INDEX_ORIGIN = "https://index.commoncrawl.org"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_MAX_REQUESTS_PER_RUN = 12
DEFAULT_PAGE_SIZE_BLOCKS = 1


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: str


class HttpTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: int,
    ) -> HttpResponse:
        ...


class UrllibHttpTransport:
    """Small stdlib transport. PX4 adds destination-security policy."""

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: int,
    ) -> HttpResponse:
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return HttpResponse(
                    status=int(response.status),
                    body=response.read().decode("utf-8"),
                )
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return HttpResponse(status=int(exc.code), body=body)
        except URLError as exc:
            raise ProspectorSourceError(
                f"Common Crawl request failed: {exc.reason}"
            ) from exc


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y%m%d%H%M%S")
    except (TypeError, ValueError) as exc:
        raise ProspectorContractError(
            f"Common Crawl returned invalid timestamp {value!r}"
        ) from exc
    return parsed.replace(tzinfo=timezone.utc)


def _path_filter_regex(path_terms: Sequence[str]) -> str:
    escaped = [re.escape(term) for term in path_terms if term]
    if not escaped:
        raise ProspectorContractError(
            "Common Crawl TLD discovery requires at least one path term"
        )
    # Terms are URL-token selectors, not arbitrary substrings. In particular,
    # "formation" must not match "information". RE2-compatible boundaries are
    # expressed with URL separators instead of look-around assertions.
    separators = r"[-/:?&=#._~%+]"
    return (
        r".*" + separators
        + r"(?:" + "|".join(escaped) + r")"
        + r"(?:" + separators + r".*|$)"
    )


class CommonCrawlIndexSource:
    """Bounded candidate discovery using Common Crawl's public CDXJ index.

    The adapter discovers URLs already present in Common Crawl. It does not
    download page bodies, infer business meaning, or assert that a URL is useful.
    """

    name = "common_crawl_cdxj"

    def __init__(
        self,
        *,
        user_agent: str,
        transport: Optional[HttpTransport] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_requests_per_run: int = DEFAULT_MAX_REQUESTS_PER_RUN,
        request_interval_seconds: float = 0.0,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        user_agent = (user_agent or "").strip()
        if not user_agent:
            raise ProspectorContractError(
                "Common Crawl requires an explicit descriptive user_agent"
            )
        self.user_agent = user_agent
        self.transport = transport or UrllibHttpTransport()
        self.timeout_seconds = max(int(timeout_seconds), 1)
        self.max_requests_per_run = max(int(max_requests_per_run), 1)
        try:
            interval = float(request_interval_seconds)
        except (TypeError, ValueError) as exc:
            raise ProspectorContractError(
                "request_interval_seconds must be numeric"
            ) from exc
        if not math.isfinite(interval) or interval < 0:
            raise ProspectorContractError(
                "request_interval_seconds must be finite and non-negative"
            )
        if not callable(sleeper):
            raise ProspectorContractError("sleeper must be callable")
        self.request_interval_seconds = interval
        self.sleeper = sleeper
        self._request_started = False
        self._request_lock = asyncio.Lock()

    @property
    def _headers(self) -> Mapping[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, application/x-ndjson, text/plain",
        }

    async def _get(self, url: str) -> HttpResponse:
        # One Common Crawl source instance never issues concurrent requests.
        # PX8 live pilots additionally inject a positive interval.
        async with self._request_lock:
            if self._request_started and self.request_interval_seconds > 0:
                await self.sleeper(self.request_interval_seconds)
            response = await asyncio.to_thread(
                self.transport.get,
                url,
                headers=self._headers,
                timeout_seconds=self.timeout_seconds,
            )
            self._request_started = True
            return response

    async def _latest_collection(self) -> str:
        response = await self._get(COLLECTIONS_URL)
        if response.status in {429, 503}:
            raise ProspectorSourceRateLimitError(
                f"Common Crawl collections request returned HTTP {response.status}; "
                "stop the live run and retry later"
            )
        if response.status != 200:
            raise ProspectorSourceError(
                f"Common Crawl collections request returned HTTP {response.status}"
            )
        try:
            payload = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise ProspectorContractError(
                "Common Crawl collections response is not valid JSON"
            ) from exc
        if not isinstance(payload, list) or not payload:
            raise ProspectorContractError(
                "Common Crawl collections response is empty"
            )
        collection_id = str(payload[0].get("id", "")).strip()
        if not collection_id:
            raise ProspectorContractError(
                "Common Crawl collection is missing its id"
            )
        return collection_id

    def _selectors(self, mission: ProspectingMission) -> tuple[tuple[str, str], ...]:
        if not mission.path_terms:
            raise ProspectorContractError(
                "Common Crawl PX2 discovery requires path_terms to avoid broad TLD scans"
            )
        if not mission.host_tlds:
            raise ProspectorContractError(
                "Common Crawl PX2 discovery requires at least one host_tld"
            )
        media_types = mission.media_types or ("text/html",)
        return tuple(
            (tld, media_type)
            for tld in mission.host_tlds
            for media_type in media_types
        )

    def _query_url(
        self,
        *,
        collection_id: str,
        tld: str,
        media_type: str,
        path_terms: Sequence[str],
        page: int,
    ) -> str:
        params = [
            ("url", f"*.{tld}/*"),
            ("output", "json"),
            ("page", str(page)),
            ("pageSize", str(DEFAULT_PAGE_SIZE_BLOCKS)),
            ("filter", "status:200"),
            ("filter", f"=mime:{media_type}"),
            ("filter", f"~url:{_path_filter_regex(path_terms)}"),
            (
                "fields",
                "timestamp,url,mime,status,digest,filename,offset,length",
            ),
        ]
        return f"{INDEX_ORIGIN}/{collection_id}-index?{urlencode(params)}"

    @staticmethod
    def _parse_records(
        body: str,
        *,
        collection_id: str,
    ) -> tuple[IndexedResource, ...]:
        records = []
        for line_number, line in enumerate(body.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProspectorContractError(
                    f"Common Crawl NDJSON line {line_number} is invalid"
                ) from exc
            locator = str(item.get("url", "")).strip()
            timestamp = str(item.get("timestamp", "")).strip()
            if not locator or not timestamp:
                continue
            status_raw = item.get("status")
            status_code = int(status_raw) if status_raw not in {None, ""} else None
            filename = str(item.get("filename", "")).strip()
            offset = str(item.get("offset", "")).strip()
            length = str(item.get("length", "")).strip()
            digest = str(item.get("digest", "")).strip()
            source_ref = ":".join(
                part
                for part in (collection_id, filename, offset, length, digest)
                if part
            )
            records.append(
                IndexedResource(
                    provider="common_crawl",
                    locator=locator,
                    observed_at=_parse_timestamp(timestamp),
                    source_revision=collection_id,
                    source_ref=source_ref or f"{collection_id}:{line_number}",
                    status_code=status_code,
                    mime_type=str(item.get("mime", "")).strip() or None,
                    attributes={
                        "archive_filename": filename,
                        "archive_offset": offset,
                        "archive_length": length,
                        "digest": digest,
                    },
                )
            )
        return tuple(records)

    async def discover(
        self,
        mission: ProspectingMission,
        *,
        checkpoint: Optional[SourceCheckpoint] = None,
    ) -> SourceBatch:
        selectors = self._selectors(mission)
        requests_used = 0
        if checkpoint is None:
            collection_id = await self._latest_collection()
            requests_used += 1
            selector_index = 0
            page = 0
            offset = 0
        elif checkpoint.exhausted:
            latest = await self._latest_collection()
            requests_used += 1
            if latest == checkpoint.source_revision:
                return SourceBatch(
                    source_name=self.name,
                    source_revision=checkpoint.source_revision,
                    records=(),
                    next_cursor=checkpoint.cursor,
                    exhausted=True,
                )
            collection_id = latest
            selector_index = 0
            page = 0
            offset = 0
        else:
            collection_id = checkpoint.source_revision
            selector_index = int(checkpoint.cursor.get("selector_index", 0))
            page = int(checkpoint.cursor.get("page", 0))
            offset = int(checkpoint.cursor.get("offset", 0))

        collected = []

        while (
            selector_index < len(selectors)
            and len(collected) < mission.max_candidates
            and requests_used < self.max_requests_per_run
        ):
            tld, media_type = selectors[selector_index]
            response = await self._get(
                self._query_url(
                    collection_id=collection_id,
                    tld=tld,
                    media_type=media_type,
                    path_terms=mission.path_terms,
                    page=page,
                )
            )
            requests_used += 1

            if response.status == 400:
                selector_index += 1
                page = 0
                offset = 0
                continue
            if response.status in {429, 503}:
                raise ProspectorSourceRateLimitError(
                    f"Common Crawl index request returned HTTP {response.status}; "
                    "stop the live run and retry later"
                )
            if response.status != 200:
                raise ProspectorSourceError(
                    f"Common Crawl index request returned HTTP {response.status}"
                )

            page_records = self._parse_records(
                response.body,
                collection_id=collection_id,
            )
            if not page_records:
                selector_index += 1
                page = 0
                offset = 0
                continue

            remaining = mission.max_candidates - len(collected)
            available = page_records[offset:]
            consumed = available[:remaining]
            collected.extend(consumed)
            offset += len(consumed)

            if offset >= len(page_records):
                page += 1
                offset = 0

        exhausted = selector_index >= len(selectors)
        deduplicated = []
        seen = set()
        for record in collected:
            if record.locator in seen:
                continue
            seen.add(record.locator)
            deduplicated.append(record)

        return SourceBatch(
            source_name=self.name,
            source_revision=collection_id,
            records=tuple(deduplicated),
            next_cursor={
                "selector_index": selector_index,
                "page": page,
                "offset": offset,
            },
            exhausted=exhausted,
        )
