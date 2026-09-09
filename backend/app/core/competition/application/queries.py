from typing import Protocol


class RegistrationReportReader(Protocol):
    def read(self) -> tuple[list[dict], list[dict]]: ...


class GetRegistrationReport:
    def __init__(self, reader: RegistrationReportReader):
        self.reader = reader

    def execute(self) -> tuple[list[dict], list[dict]]:
        return self.reader.read()
