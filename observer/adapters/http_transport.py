from __future__ import annotations

import http.client
import socket
import ssl
from urllib.parse import urlsplit, urlunsplit

from observer.http_contracts import HttpExchange, HttpTransportFailure


class SystemHttpResolver:
    """Resolve immediately before each connection.

    The acquisition layer validates every returned address and the transport
    connects to the selected literal IP, avoiding a second DNS lookup.
    """

    def resolve(self, hostname: str) -> tuple[str, ...]:
        try:
            records = socket.getaddrinfo(
                hostname,
                None,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise HttpTransportFailure("security.dns_unresolved") from exc
        addresses = []
        for record in records:
            address = record[4][0]
            if address not in addresses:
                addresses.append(address)
        if not addresses:
            raise HttpTransportFailure("security.dns_unresolved")
        return tuple(addresses)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(
        self,
        host: str,
        *,
        port: int,
        connect_ip: str,
        connect_timeout: float,
        read_timeout: float,
    ) -> None:
        super().__init__(
            host,
            port=port,
            timeout=connect_timeout,
        )
        self._connect_ip = connect_ip
        self._read_timeout = read_timeout

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._connect_ip, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock.settimeout(self._read_timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        *,
        port: int,
        connect_ip: str,
        connect_timeout: float,
        read_timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(
            host,
            port=port,
            timeout=connect_timeout,
            context=context,
        )
        self._connect_ip = connect_ip
        self._read_timeout = read_timeout

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._connect_ip, self.port),
            self.timeout,
            self.source_address,
        )
        raw_socket.settimeout(self._read_timeout)
        try:
            self.sock = self._context.wrap_socket(
                raw_socket,
                server_hostname=self.host,
            )
        except Exception:
            raw_socket.close()
            raise


class PinnedStdlibHttpTransport:
    """Small HTTP/1.1 transport with DNS pinning and bounded body capture."""

    def __init__(self, *, ssl_context: ssl.SSLContext | None = None) -> None:
        self.ssl_context = ssl_context or ssl.create_default_context()

    def request(
        self,
        *,
        url: str,
        connect_ip: str,
        headers: dict[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_wire_bytes: int,
    ) -> HttpExchange:
        parts = urlsplit(url)
        hostname = parts.hostname
        if not hostname:
            raise HttpTransportFailure("security.malformed_locator")
        try:
            port = parts.port
        except ValueError as exc:
            raise HttpTransportFailure(
                "security.malformed_locator"
            ) from exc
        if port is None:
            port = 443 if parts.scheme == "https" else 80

        path = parts.path or "/"
        request_target = urlunsplit(
            ("", "", path, parts.query, "")
        )
        connection = None
        try:
            if parts.scheme == "https":
                connection = _PinnedHTTPSConnection(
                    hostname,
                    port=port,
                    connect_ip=connect_ip,
                    connect_timeout=connect_timeout_seconds,
                    read_timeout=read_timeout_seconds,
                    context=self.ssl_context,
                )
            elif parts.scheme == "http":
                connection = _PinnedHTTPConnection(
                    hostname,
                    port=port,
                    connect_ip=connect_ip,
                    connect_timeout=connect_timeout_seconds,
                    read_timeout=read_timeout_seconds,
                )
            else:
                raise HttpTransportFailure(
                    "security.unsupported_locator"
                )

            connection.request(
                "GET",
                request_target,
                headers=headers,
            )
            response = connection.getresponse()
            peer_ip = connect_ip
            if connection.sock is not None:
                peer_ip = connection.sock.getpeername()[0]

            raw_headers: dict[str, str] = {}
            for key, value in response.getheaders():
                normalized = key.lower()
                if normalized in raw_headers:
                    raw_headers[normalized] = (
                        raw_headers[normalized] + ", " + value
                    )
                else:
                    raw_headers[normalized] = value

            declared_length = raw_headers.get("content-length")
            if declared_length:
                try:
                    length = int(declared_length)
                except ValueError as exc:
                    raise HttpTransportFailure(
                        "http.invalid_content_length"
                    ) from exc
                if length < 0:
                    raise HttpTransportFailure(
                        "http.invalid_content_length"
                    )
                if length > max_wire_bytes:
                    raise HttpTransportFailure(
                        "http.response_too_large"
                    )

            chunks = []
            total = 0
            while True:
                chunk = response.read(
                    min(64 * 1024, max_wire_bytes - total + 1)
                )
                if not chunk:
                    break
                total += len(chunk)
                if total > max_wire_bytes:
                    raise HttpTransportFailure(
                        "http.response_too_large"
                    )
                chunks.append(chunk)

            body = b"".join(chunks)
            return HttpExchange(
                status=response.status,
                headers=raw_headers,
                body=body,
                peer_ip=peer_ip,
                wire_bytes=len(body),
            )
        except HttpTransportFailure:
            raise
        except (socket.timeout, TimeoutError) as exc:
            raise HttpTransportFailure("http.timeout") from exc
        except ssl.SSLError as exc:
            raise HttpTransportFailure("http.tls_error") from exc
        except http.client.HTTPException as exc:
            raise HttpTransportFailure(
                "http.protocol_error"
            ) from exc
        except OSError as exc:
            raise HttpTransportFailure(
                "http.network_error"
            ) from exc
        finally:
            if connection is not None:
                connection.close()
