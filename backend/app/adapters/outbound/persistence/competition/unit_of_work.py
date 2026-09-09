class SqlCompetitionUnitOfWork:
    """Open a session only for the write phase, after external requests finish."""

    def __init__(
        self, session_factory, repository_factory, events_factory, players_factory
    ):
        self.session_factory = session_factory
        self.repository_factory = repository_factory
        self.players_factory = players_factory
        self.events_factory = events_factory

    def __enter__(self):
        self.session = self.session_factory()
        self._committed = False
        try:
            self.repository = self.repository_factory(self.session)
            self.players = self.players_factory(self.session)
            self.events = self.events_factory(self.session)
        except Exception:
            self.session.close()
            raise
        return self

    def commit(self):
        self.session.commit()
        self._committed = True

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is not None or not self._committed:
                self.session.rollback()
        finally:
            self.session.close()
