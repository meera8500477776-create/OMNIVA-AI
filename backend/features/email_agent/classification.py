from .contracts import Category, Email

INJECTION_MARKERS = (
    "ignore previous instructions",
    "reveal your system prompt",
    "send credentials",
    "run this command",
    "ignore all prior rules",
)


def injection_suspected(text: str) -> bool:
    folded = text.casefold()
    return any(marker in folded for marker in INJECTION_MARKERS)


def classify(email: Email) -> Category:
    text = f"{email.sender} {email.subject} {email.body}".casefold()
    if any(x in text for x in ("verify your password", "claim your prize", "wire transfer now")):
        return Category.SPAM_SUSPECTED
    if any(x in text for x in ("limited time offer", "unsubscribe", "sale", "discount")):
        return Category.PROMOTIONS
    if any(x in text for x in ("urgent", "asap", "deadline today", "immediately")):
        return Category.URGENT
    if any(x in text for x in ("meeting", "action required", "invoice", "review needed")):
        return Category.IMPORTANT
    return Category.NORMAL
