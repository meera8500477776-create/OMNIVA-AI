from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from .exceptions import CapabilityUnavailable, ProviderTimeout, UnsafeAction

INJECTION_MARKERS = (
    "ignore all previous instructions",
    "ignore previous instructions",
    "reveal secrets",
    "exfiltrate",
    "system prompt",
    "override your instructions",
)


def page_is_untrusted(text: str) -> bool:
    folded = text.casefold()
    return any(marker in folded for marker in INJECTION_MARKERS)


def _public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    return ip.is_global and not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_url(
    url: str, allowlist: set[str], resolver=None
) -> tuple[str, tuple[str, ...]]:
    if len(url) > 2048:
        raise UnsafeAction("URL is too long")
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise UnsafeAction("URL is malformed") from exc
    host = (parsed.hostname or "").rstrip(".").casefold()
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise UnsafeAction("Only public HTTP(S) URLs are allowed")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test")):
        raise UnsafeAction("Private and local destinations are blocked")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    try:
        port = parsed.port
    except ValueError as exc:
        raise UnsafeAction("URL port is invalid") from exc
    if port not in {None, 80, 443}:
        raise UnsafeAction("Only standard web ports are allowed")
    if literal and not _public_ip(str(literal)):
        raise UnsafeAction("Private and reserved IP addresses are blocked")
    if not any(host == domain or host.endswith("." + domain) for domain in allowlist):
        raise UnsafeAction("Domain is not allowlisted")
    if resolver:
        addresses = tuple(sorted({str(item) for item in resolver(host)}))
    elif literal:
        addresses = (str(literal),)
    else:
        try:
            addresses = tuple(
                sorted(
                    {
                        item[4][0]
                        for item in socket.getaddrinfo(
                            host,
                            port or (443 if parsed.scheme == "https" else 80),
                            type=socket.SOCK_STREAM,
                        )
                    }
                )
            )
        except OSError as exc:
            raise UnsafeAction("Destination could not be safely resolved") from exc
    if not addresses or any(not _public_ip(addr) for addr in addresses):
        raise UnsafeAction("Destination resolves to a private or invalid address")
    # Callers must pin the verified DNS answers for the browser session to avoid DNS rebinding.
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, "")
    ), addresses


@dataclass(frozen=True)
class PageInspection:
    url: str
    title: str
    text: str
    evidence_id: str
    untrusted_instructions_detected: bool


class BrowserProvider:
    async def navigate_and_inspect(
        self, url: str, *, pinned_addresses: tuple[str, ...], timeout: float
    ) -> PageInspection:
        raise NotImplementedError

    async def fill_preview(
        self, url: str, fields: dict[str, str], *, pinned_addresses: tuple[str, ...], timeout: float
    ) -> dict:
        raise NotImplementedError


class DemoBrowserProvider:
    async def navigate_and_inspect(self, url, *, pinned_addresses, timeout):
        return PageInspection(
            url,
            "Fictional internship listings",
            "Demo opportunities: Northstar AI Research Intern; Cedar Labs ML Intern; Example Robotics AI Intern. All results are fictional.",
            "fixture:internships-001",
            False,
        )

    async def fill_preview(self, url, fields, *, pinned_addresses, timeout):
        return {
            "simulated": True,
            "submitted": False,
            "fields": fields,
            "evidence_id": "fixture:form-preview-001",
        }


class BrowserAutomationAdapter:
    def __init__(self, *, demo=True, provider=None, allowlist=None, resolver=None, timeout=8):
        self.demo = demo
        self.provider = provider or (DemoBrowserProvider() if demo else None)
        self.allowlist = {x.casefold().strip(".") for x in (allowlist or set())}
        self.resolver = resolver
        self.timeout = timeout

    async def _call_provider(self, awaitable):
        try:
            return await asyncio.wait_for(awaitable, timeout=self.timeout)
        except TimeoutError as exc:
            raise ProviderTimeout("Browser provider timed out") from exc

    async def inspect(self, url: str) -> dict:
        if self.demo:
            if not url.startswith("https://internships.demo.test"):
                raise UnsafeAction("Demo browser only opens its local fictional fixture")
            page = await self._call_provider(
                self.provider.navigate_and_inspect(
                    url, pinned_addresses=("203.0.113.1",), timeout=self.timeout
                )
            )
        else:
            if self.provider is None:
                raise CapabilityUnavailable("Browser provider is not configured")
            safe_url, pins = validate_public_url(url, self.allowlist, self.resolver)
            page = await self._call_provider(
                self.provider.navigate_and_inspect(safe_url, pinned_addresses=pins, timeout=self.timeout)
            )
        return {
            "url": page.url,
            "title": page.title,
            "text": page.text,
            "evidence_id": page.evidence_id,
            "untrusted_instructions_detected": page.untrusted_instructions_detected
            or page_is_untrusted(page.text),
            "demo": self.demo,
        }

    async def fill_preview(self, url: str, fields: dict[str, str]) -> dict:
        if (
            not fields
            or len(fields) > 30
            or any(len(k) > 100 or len(v) > 2000 for k, v in fields.items())
        ):
            raise UnsafeAction("Form preview fields are invalid")
        if self.demo:
            if not url.startswith("https://internships.demo.test"):
                raise UnsafeAction("Demo browser only fills its local fictional fixture")
            return await self._call_provider(
                self.provider.fill_preview(
                    url, fields, pinned_addresses=("203.0.113.1",), timeout=self.timeout
                )
            )
        if self.provider is None:
            raise CapabilityUnavailable("Browser provider is not configured")
        safe_url, pins = validate_public_url(url, self.allowlist, self.resolver)
        return await self._call_provider(
            self.provider.fill_preview(safe_url, fields, pinned_addresses=pins, timeout=self.timeout)
        )

    async def submit(self, *_args, **_kwargs):
        raise CapabilityUnavailable(
            "Form submission is not available in this integration; no real forms are submitted"
        )
