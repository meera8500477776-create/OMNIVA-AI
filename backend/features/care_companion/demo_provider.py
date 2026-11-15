from .contracts import PersonaId
from .personas import PERSONAS


class DemoCompanion:
    def reply(self, persona: PersonaId, text: str, locale: str = "en") -> str:
        PERSONAS[persona]
        if locale.casefold().startswith("te"):
            return "డెమో సంభాషణ: మీ మాట విన్నాను. మీకు ఎలా సహాయం చేయగలను?"
        return (
            f"[DEMO · AI companion] I hear you. {text[:180]} Tell me a little more if you’d like."
        )

    def greeting(self, persona: PersonaId) -> str:
        return "[DEMO · AI companion] " + PERSONAS[persona].greeting
