from app.core.competition.application.sync.ports import RegistrationReportReader


class GetRegistrationReport:
    def __init__(self, reader: RegistrationReportReader):
        self.reader = reader

    def execute(self) -> tuple[list[dict], list[dict]]:
        return self.reader.read()
