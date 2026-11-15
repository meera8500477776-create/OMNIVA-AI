class ConsentMemory:
    def __init__(self):
        self.enabled = False
        self.items = []

    def enable(self, consent: bool):
        if not consent:
            raise PermissionError("Explicit memory consent required")
        self.enabled = True

    def remember(self, item: str):
        if self.enabled:
            self.items.append(item[:500])

    def delete_all(self):
        self.items.clear()
        self.enabled = False
