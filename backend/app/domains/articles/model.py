from datetime import datetime
from sqlmodel import SQLModel, Field

class Article(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    title: str
    slug: str
    teaser: str
    content: str

    image_url: str | None = None

    published: bool = Field(default=False)

    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime