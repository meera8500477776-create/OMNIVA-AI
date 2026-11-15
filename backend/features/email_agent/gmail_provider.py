"""Live Gmail seams. No HTTP client is bundled or called by this feature adapter."""
from typing import Protocol
from .contracts import Email, ProviderUnavailable

GMAIL_SCOPES = ("https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.compose")

class TokenVault(Protocol):
    async def put_encrypted(self, user_id: str, token: bytes) -> None: ...
    async def delete(self, user_id: str) -> None: ...

class GmailTransport(Protocol):
    async def list_messages(self, query: str, limit: int) -> list[Email]: ...
    async def create_draft(self, email_id: str, body: str) -> str: ...
    async def send(self, draft_id: str, idempotency_key: str) -> str: ...

class LiveGmailProvider:
    def __init__(self, transport: GmailTransport | None = None, vault: TokenVault | None = None):
        self.transport, self.vault = transport, vault
    def require(self) -> GmailTransport:
        if self.transport is None or self.vault is None:
            raise ProviderUnavailable("Gmail live mode unavailable: OAuth transport and encrypted token vault are not configured")
        return self.transport
