from app.core.auth.application.dto import CurrentUserQuery
from app.core.auth.application.ports import Tokens
from app.core.auth.domain.session import AuthenticationError
from app.core.users.public import UserDetails, UserReader


class GetCurrentUser:
    def __init__(self, users: UserReader, tokens: Tokens):
        self.users = users
        self.tokens = tokens

    def execute(self, query: CurrentUserQuery) -> UserDetails:
        user_id = self.tokens.decode_access(query.access_token)
        if user_id is None:
            raise AuthenticationError("Ungültiges oder abgelaufenes Token")
        user = self.users.get_public(user_id)
        if user is None:
            raise AuthenticationError("Benutzer nicht gefunden")
        if not user.is_active:
            raise AuthenticationError("Benutzer ist deaktiviert")
        return user
