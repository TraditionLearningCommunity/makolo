from __future__ import annotations

import asyncio
import socket


class SystemDnsResolver:
    """System DNS adapter.

    This is a preflight signal only. The Observateur must resolve again and
    validate the actual peer for every connection and redirect.
    """

    async def resolve(self, hostname: str):
        def _resolve():
            records = socket.getaddrinfo(
                hostname,
                None,
                type=socket.SOCK_STREAM,
            )
            addresses = []
            for record in records:
                address = record[4][0]
                if address not in addresses:
                    addresses.append(address)
            return tuple(addresses)

        return await asyncio.to_thread(_resolve)
