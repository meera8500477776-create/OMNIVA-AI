from .contracts import Email

def summarize(email: Email, max_chars: int = 220) -> str:
    """Deterministic extractive preview; email text is always treated as untrusted data."""
    text = " ".join(email.body.split())
    if not text:
        return f"No message text. Subject: {email.subject[:100]}"
    return text[:max_chars].rstrip() + ("…" if len(text) > max_chars else "")
