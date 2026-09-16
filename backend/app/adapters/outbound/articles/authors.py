from app.core.content.articles.application.errors import ArticleAuthorError
from app.core.users.public import UserReader


class UserArticleAuthors:
    def __init__(self, users: UserReader):
        self.users = users

    def system_id(self) -> int:
        user_id = self.users.get_system_author_id()
        if user_id is None:
            raise ArticleAuthorError(
                "Systemautor fehlt. Bitte Datenbankmigrationen ausführen."
            )
        return user_id

    def ensure_editor(self, user_id: int) -> None:
        user = self.users.get_public(user_id)
        if (
            user is None
            or not user.is_active
            or user.is_system
            or not {"ADMIN", "EDITOR"}.intersection(user.roles)
        ):
            raise ArticleAuthorError("Ein aktiver ADMIN oder EDITOR ist erforderlich.")
