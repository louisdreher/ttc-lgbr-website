from sqlmodel import SQLModel


class ArticleCreate(SQLModel):
    title: str
    teaser: str
    content: str

class ArticleUpdate(SQLModel):
    title: str | None = None
    teaser: str | None = None
    content: str | None = None