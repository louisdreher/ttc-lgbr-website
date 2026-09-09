from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


class ArgonPasswords:
    def __init__(self):
        self.hasher = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self.hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self.hasher.verify(password, password_hash)
        except UnknownHashError:
            return False
