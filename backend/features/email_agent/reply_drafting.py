from .contracts import Draft, Email, Tone

def draft_reply(email: Email, tone: Tone = Tone.PROFESSIONAL, *, demo: bool = True) -> Draft:
    openers = {Tone.PROFESSIONAL: "Hello,", Tone.FRIENDLY: "Hi there,", Tone.CONCISE: "Hello,", Tone.FORMAL: "Dear sender,"}
    closers = {Tone.PROFESSIONAL: "Best regards,", Tone.FRIENDLY: "Thanks,", Tone.CONCISE: "Regards,", Tone.FORMAL: "Yours sincerely,"}
    return Draft(email.id, f"{openers[tone]}\n\nThank you for your message about {email.subject[:100]}. I’ll review it and follow up.\n\n{closers[tone]}\n[Your name]", tone, demo)
