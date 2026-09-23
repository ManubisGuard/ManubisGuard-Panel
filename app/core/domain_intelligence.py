import asyncio
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

import aiohttp

from app.models.domain_intelligence import (
    DomainDNSResult,
    DomainHTTPProbe,
    DomainIntelligenceResult,
)
from app.models.settings import ManagedDomain


DNS_QUERY_TYPES = ("A", "AAAA", "CNAME", "NS")
_DNS_TYPE_CODES = {"A": 1, "NS": 2, "CNAME": 5, "AAAA": 28}
_DOH_URL = "https://cloudflare-dns.com/dns-query"


class DomainIntelligence:
    """Non-invasive domain discovery and reachability inspection.

    DNS is resolved through DNS-over-HTTPS and HTTP probing follows redirects.
    No arbitrary port scanning is performed.
    """

    def __init__(
        self,
        *,
        timeout: float = 8.0,
        max_redirects: int = 5,
        doh_url: str = _DOH_URL,
        session_factory: Callable[..., Awaitable[aiohttp.ClientSession]] | None = None,
    ):
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.doh_url = doh_url
        self._session_factory = session_factory

    async def inspect(self, domain: str) -> DomainIntelligenceResult:
        normalized = ManagedDomain(id="domain-intelligence", domain=domain).domain
        if normalized.startswith("*."):
            raise ValueError("Wildcard domains cannot be inspected directly.")
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        if self._session_factory is not None:
            session = await self._session_factory(timeout=timeout)
            close_session = True
        else:
            session = aiohttp.ClientSession(timeout=timeout)
            close_session = True

        try:
            dns = await self._resolve_dns(session, normalized)
            http, https = await asyncio.gather(
                self._probe(session, f"http://{normalized}"),
                self._probe(session, f"https://{normalized}"),
            )
            return DomainIntelligenceResult.now(normalized, dns, http, https)
        finally:
            if close_session:
                await session.close()

    async def _resolve_dns(self, session: aiohttp.ClientSession, domain: str) -> DomainDNSResult:
        values: dict[str, list[str]] = {query_type: [] for query_type in DNS_QUERY_TYPES}

        async def query(query_type: str):
            try:
                async with session.get(
                    self.doh_url,
                    params={"name": domain, "type": query_type},
                    headers={"Accept": "application/dns-json"},
                ) as response:
                    if response.status != 200:
                        return
                    payload = await response.json(content_type=None)
                    for answer in payload.get("Answer", []):
                        if answer.get("type") != _DNS_TYPE_CODES[query_type]:
                            continue
                        value = str(answer.get("data", "")).rstrip(".")
                        if value and value not in values[query_type]:
                            values[query_type].append(value)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                return

        await asyncio.gather(*(query(query_type) for query_type in DNS_QUERY_TYPES))

        return DomainDNSResult(
            a=sorted(values["A"]),
            aaaa=sorted(values["AAAA"]),
            cname=values["CNAME"][0] if values["CNAME"] else None,
            nameservers=sorted(values["NS"]),
        )

    async def _probe(self, session: aiohttp.ClientSession, url: str) -> DomainHTTPProbe:
        try:
            async with session.get(
                url,
                allow_redirects=True,
                max_redirects=self.max_redirects,
                headers={"User-Agent": "PasarGuard-DomainIntelligence/1.0"},
            ) as response:
                history = [str(item.url) for item in response.history]
                return DomainHTTPProbe(
                    url=url,
                    reachable=True,
                    status_code=response.status,
                    final_url=str(response.url),
                    redirect_chain=history,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            return DomainHTTPProbe(url=url, error=type(exc).__name__)

    @staticmethod
    def is_https_url(url: str) -> bool:
        return urlparse(url).scheme.lower() == "https"

    @staticmethod
    async def resolve_local_addresses(domain: str) -> tuple[list[str], list[str]]:
        """Optional local resolver helper for environments without DoH."""
        loop = asyncio.get_running_loop()
        infos = await loop.run_in_executor(
            None,
            lambda: socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM),
        )
        ipv4 = sorted({info[4][0] for info in infos if info[0] == socket.AF_INET})
        ipv6 = sorted({info[4][0] for info in infos if info[0] == socket.AF_INET6})
        return ipv4, ipv6
