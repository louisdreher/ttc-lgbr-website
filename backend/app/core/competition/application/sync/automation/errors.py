class ReloadMatchNotFoundError(ValueError):
    def __init__(self):
        super().__init__("Spiel nicht gefunden.")


class MatchReloadConflictError(ValueError):
    pass
