from __future__ import annotations

import ssl
from unittest import TestCase
from unittest.mock import patch

from observer.adapters.http_transport import (
    PinnedStdlibHttpTransport,
    SystemHttpResolver,
    _PinnedHTTPConnection,
    _PinnedHTTPSConnection,
)
from observer.http_contracts import HttpTransportFailure


GLOBAL_IP = "93.184.216.34"


class FakeSocket:
    def __init__(self, peer=GLOBAL_IP):
        self.peer = peer
        self.timeouts = []
        self.closed = False

    def settimeout(self, value):
        self.timeouts.append(value)

    def getpeername(self):
        return (self.peer, 443)

    def close(self):
        self.closed = True


class FakeSslContext:
    verify_mode = ssl.CERT_REQUIRED
    check_hostname = True

    def __init__(self):
        self.calls = []
        self.wrapped = FakeSocket()

    def wrap_socket(self, raw_socket, *, server_hostname):
        self.calls.append((raw_socket, server_hostname))
        return self.wrapped


class FakeResponse:
    def __init__(self, *, status=200, headers=(), body=b""):
        self.status = status
        self._headers = list(headers)
        self.body = body
        self.offset = 0

    def getheaders(self):
        return list(self._headers)

    def read(self, size):
        if self.offset >= len(self.body):
            return b""
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class FakeConnection:
    response = None
    created = []

    def __init__(self, host, **kwargs):
        self.host = host
        self.kwargs = kwargs
        self.requests = []
        self.sock = FakeSocket(peer=kwargs["connect_ip"])
        self.closed = False
        type(self).created.append(self)

    def connect(self):
        return None

    def request(self, method, target, headers):
        self.requests.append((method, target, dict(headers)))

    def getresponse(self):
        return type(self).response

    def close(self):
        self.closed = True


class PinnedHttpTransportTests(TestCase):
    def test_http_connection_uses_literal_validated_ip(self):
        raw_socket = FakeSocket()
        with patch(
            "observer.adapters.http_transport.socket.create_connection",
            return_value=raw_socket,
        ) as create_connection:
            connection = _PinnedHTTPConnection(
                "example.test",
                port=80,
                connect_ip=GLOBAL_IP,
                connect_timeout=3,
                read_timeout=4,
            )
            connection.connect()

        create_connection.assert_called_once_with(
            (GLOBAL_IP, 80),
            3,
            None,
        )
        self.assertIs(connection.sock, raw_socket)
        self.assertEqual(raw_socket.timeouts, [4])

    def test_https_pins_ip_but_keeps_hostname_for_tls_sni(self):
        raw_socket = FakeSocket()
        context = FakeSslContext()
        with patch(
            "observer.adapters.http_transport.socket.create_connection",
            return_value=raw_socket,
        ) as create_connection:
            connection = _PinnedHTTPSConnection(
                "example.test",
                port=443,
                connect_ip=GLOBAL_IP,
                connect_timeout=3,
                read_timeout=4,
                context=ssl.create_default_context(),
            )
            connection._context = context
            connection.connect()

        create_connection.assert_called_once_with(
            (GLOBAL_IP, 443),
            3,
            None,
        )
        self.assertEqual(
            context.calls,
            [(raw_socket, "example.test")],
        )
        self.assertIs(connection.sock, context.wrapped)

    def test_system_resolver_deduplicates_answers(self):
        resolver = SystemHttpResolver()
        records = [
            (2, 1, 6, "", (GLOBAL_IP, 0)),
            (2, 1, 6, "", (GLOBAL_IP, 0)),
            (2, 1, 6, "", ("1.1.1.1", 0)),
        ]
        with patch(
            "observer.adapters.http_transport.socket.getaddrinfo",
            return_value=records,
        ):
            addresses = resolver.resolve("example.test")

        self.assertEqual(addresses, (GLOBAL_IP, "1.1.1.1"))

    def test_transport_deadline_caps_repeated_reads(self):
        FakeConnection.created = []
        FakeConnection.response = FakeResponse(
            status=200,
            headers=[],
            body=b"hello",
        )
        transport = PinnedStdlibHttpTransport()
        monotonic_values = iter([0.0, 0.0, 0.4, 1.1])
        with (
            patch(
                "observer.adapters.http_transport._PinnedHTTPConnection",
                FakeConnection,
            ),
            patch(
                "observer.adapters.http_transport.time.monotonic",
                side_effect=lambda: next(monotonic_values),
            ),
        ):
            with self.assertRaises(HttpTransportFailure) as ctx:
                transport.request(
                    url="http://example.test/resource",
                    connect_ip=GLOBAL_IP,
                    headers={"User-Agent": "test"},
                    connect_timeout_seconds=1,
                    read_timeout_seconds=1,
                    max_wire_bytes=10,
                    total_timeout_seconds=1,
                )

        self.assertEqual(ctx.exception.code, "http.timeout")
        self.assertTrue(FakeConnection.created[0].closed)

    def test_transport_refuses_declared_body_larger_than_budget(self):
        FakeConnection.created = []
        FakeConnection.response = FakeResponse(
            status=200,
            headers=[("Content-Length", "11")],
            body=b"hello world",
        )
        transport = PinnedStdlibHttpTransport()
        with patch(
            "observer.adapters.http_transport._PinnedHTTPConnection",
            FakeConnection,
        ):
            with self.assertRaises(HttpTransportFailure) as ctx:
                transport.request(
                    url="http://example.test/resource",
                    connect_ip=GLOBAL_IP,
                    headers={"User-Agent": "test"},
                    connect_timeout_seconds=1,
                    read_timeout_seconds=1,
                    max_wire_bytes=10,
                )

        self.assertEqual(ctx.exception.code, "http.response_too_large")
        self.assertTrue(FakeConnection.created[0].closed)

    def test_transport_stops_chunked_body_at_budget(self):
        FakeConnection.created = []
        FakeConnection.response = FakeResponse(
            status=200,
            headers=[],
            body=b"hello world",
        )
        transport = PinnedStdlibHttpTransport()
        with patch(
            "observer.adapters.http_transport._PinnedHTTPConnection",
            FakeConnection,
        ):
            with self.assertRaises(HttpTransportFailure) as ctx:
                transport.request(
                    url="http://example.test/resource",
                    connect_ip=GLOBAL_IP,
                    headers={"User-Agent": "test"},
                    connect_timeout_seconds=1,
                    read_timeout_seconds=1,
                    max_wire_bytes=10,
                )

        self.assertEqual(ctx.exception.code, "http.response_too_large")
