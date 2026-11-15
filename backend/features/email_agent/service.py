import asyncio
import hashlib
import hmac
import secrets
import time
from .classification import classify, injection_suspected
from .contracts import ApprovalRequired, DuplicateSend, Email, EmailView, ProviderUnavailable, Tone
from .reply_drafting import draft_reply
from .summarization import summarize
from .gmail_provider import LiveGmailProvider
from .demo_provider import DemoEmailProvider

class OAuthState:
    """Single-use signed state bound to an app session; production persistence belongs to Phase 6."""
    def __init__(self, secret: bytes, ttl: int = 300): self.secret, self.ttl, self._used = secret, ttl, set()
    def issue(self, session_id: str, now: int | None = None) -> str:
        expiry = (now or int(time.time())) + self.ttl
        nonce = secrets.token_urlsafe(16)
        payload = f"{session_id}:{expiry}:{nonce}"
        sig = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}:{sig}"
    def consume(self, value: str, session_id: str, now: int | None = None) -> bool:
        try: owner, expiry, nonce, sig = value.rsplit(":", 3); expiry = int(expiry)
        except (ValueError, TypeError): return False
        payload = f"{owner}:{expiry}:{nonce}"
        expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        key = hashlib.sha256(value.encode()).hexdigest()
        valid = hmac.compare_digest(sig, expected) and owner == session_id and expiry >= (now or int(time.time())) and key not in self._used
        if valid: self._used.add(key)
        return valid

class EmailAgent:
    def __init__(self, *, demo: bool = True, live: LiveGmailProvider | None = None, timeout: float = 4.0):
        self.demo, self.live, self.timeout = demo, live or LiveGmailProvider(), timeout
        self.disabled = False; self._approvals: dict[str, tuple[str, str]] = {}; self._sent: dict[str, str] = {}; self.activity: list[dict[str,str]] = []
        if not demo: self.live.require()
    async def inbox(self) -> list[EmailView]:
        if self.demo: emails = DemoEmailProvider().emails
        else: emails = await asyncio.wait_for(self.live.require().list_messages("", 50), self.timeout)
        return [EmailView(e, classify(e), summarize(e), injection_suspected(e.body), ("review", "draft-reply")) for e in emails]
    def draft(self, email: Email, tone: Tone = Tone.PROFESSIONAL):
        if injection_suspected(email.body): self.activity.append({"event":"untrusted-instructions-flagged","email_id":email.id})
        return draft_reply(email, tone, demo=self.demo)
    def request_send_approval(self, user_id: str, draft_id: str) -> str:
        token = secrets.token_urlsafe(24); self._approvals[token] = (user_id, draft_id); return token
    async def send_approved(self, user_id: str, approval: str, idempotency_key: str) -> str:
        if self.disabled: raise ProviderUnavailable("Email automation is emergency-disabled")
        approved = self._approvals.get(approval)
        if not approved or approved[0] != user_id: raise ApprovalRequired("A valid, user-bound approval is required")
        if not idempotency_key: raise ValueError("An idempotency key is required")
        if idempotency_key in self._sent: raise DuplicateSend("This idempotency key has already been used")
        self._approvals.pop(approval)
        if self.demo:
            result = f"demo-simulated:{approved[1]}"
        else:
            provider = self.live.require()
            result = await asyncio.wait_for(provider.send(approved[1], idempotency_key), self.timeout)
        self._sent[idempotency_key] = result
        self.activity.append({"event":"email-sent","draft_id":approved[1],"idempotency_key":idempotency_key})
        return result
